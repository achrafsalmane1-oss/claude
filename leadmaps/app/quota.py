"""Credit accounting and plan enforcement.

One credit equals one lead row delivered. Jobs reserve an estimate up front so
a single deep search cannot overrun the plan, then the reservation is
reconciled against the real count when the engine reports back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Job, UsageEvent, User
from app.plans import Plan, get_plan

# Google Maps returns roughly this many places per pagination page. Used only to
# size the up-front reservation; the ledger is corrected to the real count when
# the job finishes.
RESULTS_PER_PAGE = 20


class QuotaError(Exception):
    """Raised when an account may not perform the requested action."""

    def __init__(self, message: str, *, code: str = "quota_exceeded") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class UsageSummary:
    plan: Plan
    period: str
    used: int
    included: int

    @property
    def remaining(self) -> int:
        return max(self.included - self.used, 0)

    @property
    def percent_used(self) -> int:
        if self.included <= 0:
            return 100
        return min(int(round(self.used / self.included * 100)), 100)

    @property
    def is_exhausted(self) -> bool:
        return self.remaining <= 0


def current_period(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def usage_for(session: Session, account: Account, period: str | None = None) -> UsageSummary:
    period = period or current_period()
    plan = get_plan(account.plan_code)
    used = session.scalar(
        select(func.coalesce(func.sum(UsageEvent.credits), 0)).where(
            UsageEvent.account_id == account.id,
            UsageEvent.period == period,
        )
    )
    return UsageSummary(plan=plan, period=period, used=int(used or 0), included=plan.monthly_credits)


def estimate_credits(max_depth: int) -> int:
    """Credits to hold for a search of ``max_depth`` pages."""
    return max(1, max_depth) * RESULTS_PER_PAGE


def seats_used(session: Session, account: Account) -> int:
    return int(
        session.scalar(select(func.count(User.id)).where(User.account_id == account.id)) or 0
    )


def active_job_count(session: Session, account: Account) -> int:
    return int(
        session.scalar(
            select(func.count(Job.id)).where(
                Job.account_id == account.id,
                Job.status.in_(("queued", "running")),
            )
        )
        or 0
    )


def check_can_submit(
    session: Session,
    account: Account,
    *,
    max_depth: int,
    extract_emails: bool,
    source: str,
    max_concurrent: int,
) -> int:
    """Validate a pending search against the account's plan.

    Returns the number of credits to reserve. Raises :class:`QuotaError` with a
    customer-facing message when the search may not run.
    """
    plan = get_plan(account.plan_code)

    if account.is_delinquent:
        raise QuotaError(
            "Your last payment failed. Update your card to keep scraping.",
            code="payment_required",
        )

    if source == "api" and not plan.api_access:
        raise QuotaError(
            f"API access is not included in the {plan.name} plan. Upgrade to Starter or above.",
            code="upgrade_required",
        )

    if extract_emails and not plan.email_enrichment:
        raise QuotaError(
            f"Email enrichment is not included in the {plan.name} plan. Upgrade to Growth or above.",
            code="upgrade_required",
        )

    if max_depth > plan.max_depth:
        raise QuotaError(
            f"The {plan.name} plan allows up to {plan.max_depth} pages per search.",
            code="upgrade_required",
        )

    if active_job_count(session, account) >= max_concurrent:
        raise QuotaError(
            f"You already have {max_concurrent} searches running. Wait for one to finish.",
            code="too_many_jobs",
        )

    summary = usage_for(session, account)
    if summary.is_exhausted:
        raise QuotaError(
            f"You have used all {summary.included:,} leads included this month. "
            "Upgrade your plan to keep going.",
            code="quota_exceeded",
        )

    # Never reserve more than what is actually left, so a customer with 40
    # credits left can still run a search and get 40 leads.
    return min(estimate_credits(max_depth), summary.remaining)


def reserve(session: Session, account: Account, job: Job, credits: int) -> UsageEvent:
    event = UsageEvent(
        account_id=account.id,
        job_id=job.id,
        period=current_period(),
        kind="reserved",
        credits=credits,
    )
    session.add(event)
    # Flush now: the session runs with autoflush off, and reconcile/release look
    # the reservation up by query.
    session.flush()
    return event


def reserved_credits(session: Session, job: Job) -> int:
    """How many credits are being held for ``job``. 0 when nothing is held."""
    event = session.scalar(select(UsageEvent).where(UsageEvent.job_id == job.id))
    return int(event.credits) if event is not None else 0


def reconcile(session: Session, job: Job, actual_credits: int) -> None:
    """Settle a job's reservation against the real number of leads returned."""
    event = session.scalar(select(UsageEvent).where(UsageEvent.job_id == job.id))
    if event is None:
        # Defensive: a job with no reservation still gets billed for what it used.
        session.add(
            UsageEvent(
                account_id=job.account_id,
                job_id=job.id,
                period=current_period(),
                kind="consumed",
                credits=max(actual_credits, 0),
            )
        )
        return
    event.kind = "consumed"
    event.credits = max(actual_credits, 0)


def release(session: Session, job: Job) -> None:
    """Zero out a reservation for a job that produced nothing billable."""
    event = session.scalar(select(UsageEvent).where(UsageEvent.job_id == job.id))
    if event is not None:
        event.kind = "consumed"
        event.credits = 0
