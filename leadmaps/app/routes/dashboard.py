"""The signed-in customer dashboard."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select

from app import billing, quota, services
from app.deps import EngineDep, PrincipalDep, SessionDep, SettingsDep, render
from app.engine import EngineError
from app.models import ApiKey, Job, utcnow
from app.plans import PLANS, listed_plans
from app.quota import QuotaError
from app.routes.marketing import page_context

router = APIRouter(prefix="/app")

LANGUAGES = [
    ("en", "English"), ("es", "Spanish"), ("fr", "French"), ("de", "German"),
    ("it", "Italian"), ("pt", "Portuguese"), ("nl", "Dutch"), ("pl", "Polish"),
    ("tr", "Turkish"), ("ar", "Arabic"), ("ja", "Japanese"), ("zh-CN", "Chinese"),
]

PAGE_SIZE = 25
PREVIEW_ROWS = 50


def app_context(request, settings, principal, session, **extra) -> dict:
    usage = quota.usage_for(session, principal.account)
    context = page_context(
        request,
        settings,
        principal.user,
        account=principal.account,
        plan=principal.plan,
        usage=usage,
        billing_enabled=settings.billing_enabled,
    )
    context.update(extra)
    return context


@router.get("", response_class=HTMLResponse)
def dashboard(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    engine: EngineDep,
    principal: PrincipalDep,
    keyword: str = "",
    error: str = "",
    notice: str = "",
):
    services.sync_open_jobs(session, engine, principal.account)
    session.commit()

    recent = session.scalars(
        select(Job)
        .where(Job.account_id == principal.account.id)
        .order_by(Job.created_at.desc())
        .limit(6)
    ).all()
    total = session.scalar(
        select(func.count(Job.id)).where(Job.account_id == principal.account.id)
    )

    return render(
        "dashboard.html",
        app_context(
            request, settings, principal, session,
            active="search",
            recent_jobs=recent,
            job_count=int(total or 0),
            languages=LANGUAGES,
            prefill_keyword=keyword,
            default_depth=min(3, principal.plan.max_depth),
            error=error,
            notice=notice,
        ),
    )


@router.post("/search")
def submit_search(
    settings: SettingsDep,
    session: SessionDep,
    engine: EngineDep,
    principal: PrincipalDep,
    keyword: Annotated[str, Form()],
    max_depth: Annotated[int, Form()] = 1,
    lang: Annotated[str, Form()] = "en",
    extract_emails: Annotated[str, Form()] = "",
    geo_coordinates: Annotated[str, Form()] = "",
    zoom: Annotated[str, Form()] = "",
    radius: Annotated[str, Form()] = "",
):
    try:
        job = services.submit_job(
            session,
            engine,
            settings,
            account=principal.account,
            keyword=keyword,
            lang=lang,
            max_depth=max_depth,
            extract_emails=bool(extract_emails),
            geo_coordinates=geo_coordinates.strip(),
            zoom=_as_int(zoom),
            radius=_as_float(radius),
            created_by=principal.user.id if principal.user else "",
            source="dashboard",
        )
    except (QuotaError, ValueError) as exc:
        session.commit()
        return _redirect_with("/app", error=str(exc))
    except EngineError:
        session.commit()
        return _redirect_with(
            "/app", error="The scraping engine is unavailable right now. Please try again shortly."
        )

    services.sync_job(session, engine, job)
    session.commit()
    return RedirectResponse(f"/app/jobs/{job.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    engine: EngineDep,
    principal: PrincipalDep,
    page: int = 1,
):
    services.sync_open_jobs(session, engine, principal.account)
    session.commit()

    page = max(page, 1)
    rows = session.scalars(
        select(Job)
        .where(Job.account_id == principal.account.id)
        .order_by(Job.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
    ).all()

    return render(
        "jobs.html",
        app_context(
            request, settings, principal, session,
            active="jobs",
            jobs=rows[:PAGE_SIZE],
            page=page,
            has_more=len(rows) > PAGE_SIZE,
        ),
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    engine: EngineDep,
    principal: PrincipalDep,
    job_id: str,
):
    job = _owned_job(session, principal, job_id)
    if job is None:
        return _not_found(request, settings, principal, session)

    services.sync_job(session, engine, job)
    session.commit()

    return render(
        "job_detail.html",
        app_context(
            request, settings, principal, session,
            active="jobs",
            job=job,
            rows=services.job_results(job)[:PREVIEW_ROWS],
        ),
    )


@router.get("/jobs/{job_id}/export.csv")
def export_csv(
    session: SessionDep, principal: PrincipalDep, job_id: str
):
    job = _owned_job(session, principal, job_id)
    if job is None:
        return Response("Not found", status_code=status.HTTP_404_NOT_FOUND)

    csv_body = services.results_to_csv(services.job_results(job))
    return Response(
        content=csv_body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{services.csv_filename(job)}"'
        },
    )


@router.get("/api-keys", response_class=HTMLResponse)
def api_keys_page(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    principal: PrincipalDep,
    new_key: str = "",
    error: str = "",
):
    keys = session.scalars(
        select(ApiKey)
        .where(ApiKey.account_id == principal.account.id)
        .order_by(ApiKey.created_at.desc())
    ).all()
    return render(
        "api_keys.html",
        app_context(
            request, settings, principal, session,
            active="keys", keys=keys, new_key=new_key, error=error,
        ),
    )


@router.post("/api-keys")
def create_key(
    session: SessionDep,
    principal: PrincipalDep,
    name: Annotated[str, Form()] = "",
):
    if not principal.plan.api_access:
        return _redirect_with(
            "/app/api-keys",
            error=f"API access is not included in the {principal.plan.name} plan.",
        )

    _, plaintext = services.create_api_key(session, principal.account, name)
    session.commit()
    return _redirect_with("/app/api-keys", new_key=plaintext)


@router.post("/api-keys/{key_id}/revoke")
def revoke_key(session: SessionDep, principal: PrincipalDep, key_id: str):
    key = session.scalar(
        select(ApiKey).where(
            ApiKey.id == key_id, ApiKey.account_id == principal.account.id
        )
    )
    if key is not None and key.is_active:
        key.revoked_at = utcnow()
        session.commit()
    return RedirectResponse("/app/api-keys", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/billing", response_class=HTMLResponse)
def billing_page(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    principal: PrincipalDep,
    checkout: str = "",
    error: str = "",
    plan: str = "",
):
    notice = ""
    if checkout == "success":
        notice = "Payment received — your new plan is active."
    elif checkout == "cancelled":
        notice = "Checkout cancelled. Nothing has been charged."
    if plan in PLANS and plan != principal.account.plan_code:
        notice = notice or f"Pick {PLANS[plan].name} below to finish upgrading."

    return render(
        "billing.html",
        app_context(
            request, settings, principal, session,
            active="billing",
            plans=listed_plans(),
            current_plan_code=principal.account.plan_code,
            plan_cta_url="/app/billing/checkout?plan=",
            notice=notice,
            error=error,
        ),
    )


@router.get("/billing/checkout")
def checkout(
    settings: SettingsDep,
    session: SessionDep,
    principal: PrincipalDep,
    plan: str,
):
    if plan not in PLANS:
        return _redirect_with("/app/billing", error="Unknown plan.")

    if not settings.billing_enabled:
        # Development mode: apply the plan directly so the flow is exercisable.
        billing.apply_plan_without_payment(session, principal.account, plan)
        session.commit()
        return _redirect_with(
            "/app/billing",
            notice=f"Switched to {PLANS[plan].name} (billing is disabled in this environment).",
        )

    if PLANS[plan].is_free:
        billing.apply_plan_without_payment(session, principal.account, plan)
        session.commit()
        return RedirectResponse("/app/billing", status_code=status.HTTP_303_SEE_OTHER)

    try:
        link = billing.create_checkout_session(
            settings, session, principal.account, plan_code=plan, email=principal.email
        )
    except billing.BillingError as exc:
        session.commit()
        return _redirect_with("/app/billing", error=str(exc))

    session.commit()
    return RedirectResponse(link.url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/billing/portal")
def portal(settings: SettingsDep, principal: PrincipalDep):
    if not settings.billing_enabled:
        return _redirect_with("/app/billing", error="Billing is not configured.")
    try:
        link = billing.create_portal_session(settings, principal.account)
    except billing.BillingError as exc:
        return _redirect_with("/app/billing", error=str(exc))
    return RedirectResponse(link.url, status_code=status.HTTP_303_SEE_OTHER)


# --- helpers ---------------------------------------------------------------


def _owned_job(session, principal, job_id: str) -> Job | None:
    return session.scalar(
        select(Job).where(Job.id == job_id, Job.account_id == principal.account.id)
    )


def _not_found(request, settings, principal, session):
    return render(
        "error.html",
        app_context(
            request, settings, principal, session,
            code=404, message="We could not find that search on your account.",
        ),
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _redirect_with(path: str, **params: str) -> RedirectResponse:
    from urllib.parse import urlencode

    query = urlencode({key: value for key, value in params.items() if value})
    target = f"{path}?{query}" if query else path
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)


def _as_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
