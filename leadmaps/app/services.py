"""Domain services: signup, job submission, syncing and CSV export."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import quota
from app.config import Settings
from app.engine import Engine, EngineError, ScrapeSpec
from app.models import Account, ApiKey, Job, User, utcnow
from app.plans import DEFAULT_PLAN, get_plan
from app.security import generate_api_key, hash_api_key, hash_password

# Columns exported to CSV, in the order a sales team wants to read them.
CSV_COLUMNS = [
    ("title", "business_name"),
    ("category", "category"),
    ("address", "address"),
    ("phone", "phone"),
    ("web_site", "website"),
    ("emails", "emails"),
    ("review_rating", "rating"),
    ("review_count", "review_count"),
    ("latitude", "latitude"),
    ("longtitude", "longitude"),
    ("link", "google_maps_url"),
]


class SignupError(Exception):
    """Signup could not proceed (e.g. the email is already registered)."""


def normalise_email(email: str) -> str:
    return email.strip().lower()


def find_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == normalise_email(email)))


def create_account_with_owner(
    session: Session,
    *,
    email: str,
    password: str,
    company_name: str = "",
    full_name: str = "",
    plan_code: str = DEFAULT_PLAN,
) -> User:
    """Register a new tenant and its first (owner) seat."""
    email = normalise_email(email)
    if find_user_by_email(session, email) is not None:
        raise SignupError("An account with that email already exists.")

    account = Account(
        name=company_name.strip() or email.split("@")[0],
        plan_code=plan_code,
        subscription_status="trialing" if plan_code == DEFAULT_PLAN else "none",
    )
    session.add(account)
    session.flush()

    user = User(
        account_id=account.id,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        role="owner",
    )
    session.add(user)
    session.flush()
    return user


def create_api_key(session: Session, account: Account, name: str) -> tuple[ApiKey, str]:
    """Mint a key for ``account``. Returns the record and the one-time plaintext."""
    plaintext, prefix, key_hash = generate_api_key()
    record = ApiKey(
        account_id=account.id,
        name=name.strip() or "Default key",
        prefix=prefix,
        key_hash=key_hash,
    )
    session.add(record)
    session.flush()
    return record, plaintext


def resolve_api_key(session: Session, plaintext: str) -> ApiKey | None:
    """Look up an active key by its plaintext value."""
    if not plaintext:
        return None
    record = session.scalar(
        select(ApiKey).where(ApiKey.key_hash == hash_api_key(plaintext))
    )
    if record is None or not record.is_active:
        return None
    record.last_used_at = utcnow()
    return record


def submit_job(
    session: Session,
    engine: Engine,
    settings: Settings,
    *,
    account: Account,
    keyword: str,
    lang: str = "en",
    max_depth: int = 1,
    extract_emails: bool = False,
    geo_coordinates: str = "",
    zoom: int = 0,
    radius: float = 0.0,
    fast_mode: bool = False,
    created_by: str = "",
    source: str = "dashboard",
) -> Job:
    """Validate, meter and dispatch a search.

    Raises :class:`~app.quota.QuotaError` if the plan disallows it, or
    :class:`~app.engine.EngineError` if the engine will not take the job.
    """
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("Enter what you want to search for.")

    max_depth = max(1, min(int(max_depth or 1), 100))

    reserved = quota.check_can_submit(
        session,
        account,
        max_depth=max_depth,
        extract_emails=extract_emails,
        source=source,
        max_concurrent=settings.max_concurrent_jobs,
    )

    job = Job(
        account_id=account.id,
        created_by=created_by,
        source=source,
        keyword=keyword,
        lang=lang or "en",
        max_depth=max_depth,
        geo_coordinates=geo_coordinates,
        zoom=zoom,
        radius=radius,
        fast_mode=fast_mode,
        extract_emails=extract_emails,
        status="queued",
    )
    session.add(job)
    session.flush()

    quota.reserve(session, account, job, reserved)

    spec = ScrapeSpec(
        keyword=keyword,
        lang=job.lang,
        max_depth=max_depth,
        extract_emails=extract_emails,
        geo_coordinates=geo_coordinates,
        zoom=zoom,
        radius=radius,
        fast_mode=fast_mode,
    )

    try:
        job.engine_job_id = engine.submit(spec)
    except EngineError:
        # The customer is not charged for a job the engine never accepted.
        quota.release(session, job)
        job.status = "failed"
        job.error = "The scraping engine is unavailable. Please try again shortly."
        job.completed_at = utcnow()
        session.flush()
        raise

    session.flush()
    return job


def sync_job(session: Session, engine: Engine, job: Job) -> Job:
    """Refresh ``job`` from the engine and settle its credits when it finishes."""
    if job.is_terminal or not job.engine_job_id:
        return job

    try:
        remote = engine.fetch(job.engine_job_id)
    except EngineError:
        # Transient engine trouble must not corrupt job state; try again later.
        return job

    previous_status = job.status
    job.status = remote.status
    job.result_count = remote.result_count
    job.error = remote.error

    if previous_status == "queued" and job.status == "running" and job.started_at is None:
        job.started_at = utcnow()

    if job.status == "completed":
        # Deliver at most what was reserved, so an unexpectedly large result set
        # cannot push the account past its monthly allowance.
        allowance = quota.reserved_credits(session, job) or (
            job.max_depth * quota.RESULTS_PER_PAGE
        )
        rows = remote.results[:allowance]
        job.results_json = json.dumps(rows)
        job.result_count = len(rows)
        job.completed_at = utcnow()
        if job.started_at is None:
            job.started_at = job.completed_at
        quota.reconcile(session, job, job.result_count)
    elif job.status in {"failed", "cancelled"}:
        job.completed_at = utcnow()
        quota.release(session, job)

    session.flush()
    return job


def sync_open_jobs(session: Session, engine: Engine, account: Account) -> None:
    """Refresh every non-terminal job on the account."""
    open_jobs = session.scalars(
        select(Job).where(
            Job.account_id == account.id,
            Job.status.in_(("queued", "running")),
        )
    ).all()
    for job in open_jobs:
        sync_job(session, engine, job)


def job_results(job: Job) -> list[dict[str, Any]]:
    if not job.results_json:
        return []
    try:
        data = json.loads(job.results_json)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def results_to_csv(rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([header for _, header in CSV_COLUMNS])
    for row in rows:
        writer.writerow([_csv_value(row.get(source)) for source, _ in CSV_COLUMNS])
    return buffer.getvalue()


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value if item)
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def csv_filename(job: Job) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in job.keyword.lower())
    safe = "-".join(part for part in safe.split("-") if part)[:60] or "leads"
    stamp = (job.created_at or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return f"{safe}-{stamp}.csv"
