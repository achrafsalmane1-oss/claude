"""Customer-facing REST API, authenticated with an API key."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import quota, services
from app.deps import ApiPrincipalDep, EngineDep, SessionDep, SettingsDep
from app.engine import EngineError
from app.models import Job
from app.quota import QuotaError

router = APIRouter(prefix="/api/v1", tags=["searches"])

# Quota problems map onto distinct HTTP codes so clients can react correctly.
_QUOTA_STATUS = {
    "payment_required": status.HTTP_402_PAYMENT_REQUIRED,
    "quota_exceeded": status.HTTP_402_PAYMENT_REQUIRED,
    "upgrade_required": status.HTTP_403_FORBIDDEN,
    "too_many_jobs": status.HTTP_429_TOO_MANY_REQUESTS,
}


class SearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=500, examples=["dentists in Manchester"])
    lang: str = Field("en", max_length=10)
    max_depth: int = Field(1, ge=1, le=100)
    extract_emails: bool = False
    geo_coordinates: str = Field("", max_length=60)
    zoom: int = Field(0, ge=0, le=21)
    radius: float = Field(0.0, ge=0)
    fast_mode: bool = False


class SearchSummary(BaseModel):
    id: str
    status: str
    keyword: str
    lang: str
    max_depth: int
    result_count: int
    source: str
    error: str = ""
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SearchDetail(SearchSummary):
    results: list[dict] | None = None


class SearchListResponse(BaseModel):
    searches: list[SearchSummary]
    limit: int
    offset: int
    has_more: bool


class UsageResponse(BaseModel):
    plan: str
    period: str
    included: int
    used: int
    remaining: int


def _summary(job: Job) -> SearchSummary:
    return SearchSummary(
        id=job.id,
        status=job.status,
        keyword=job.keyword,
        lang=job.lang,
        max_depth=job.max_depth,
        result_count=job.result_count,
        source=job.source,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _quota_http(exc: QuotaError) -> HTTPException:
    return HTTPException(
        status_code=_QUOTA_STATUS.get(exc.code, status.HTTP_402_PAYMENT_REQUIRED),
        detail={"error": exc.code, "message": exc.message},
    )


@router.post("/searches", response_model=SearchDetail, status_code=status.HTTP_202_ACCEPTED)
def create_search(
    payload: SearchRequest,
    settings: SettingsDep,
    session: SessionDep,
    engine: EngineDep,
    principal: ApiPrincipalDep,
):
    """Queue a new search. Returns the created search with its id."""
    try:
        job = services.submit_job(
            session,
            engine,
            settings,
            account=principal.account,
            keyword=payload.keyword,
            lang=payload.lang,
            max_depth=payload.max_depth,
            extract_emails=payload.extract_emails,
            geo_coordinates=payload.geo_coordinates,
            zoom=payload.zoom,
            radius=payload.radius,
            fast_mode=payload.fast_mode,
            source="api",
        )
    except QuotaError as exc:
        session.commit()
        raise _quota_http(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except EngineError as exc:
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The scraping engine is temporarily unavailable.",
        ) from exc

    services.sync_job(session, engine, job)
    session.commit()
    return SearchDetail(**_summary(job).model_dump(), results=None)


@router.get("/searches", response_model=SearchListResponse)
def list_searches(
    session: SessionDep,
    engine: EngineDep,
    principal: ApiPrincipalDep,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List searches on your account, newest first."""
    services.sync_open_jobs(session, engine, principal.account)
    session.commit()

    rows = session.scalars(
        select(Job)
        .where(Job.account_id == principal.account.id)
        .order_by(Job.created_at.desc())
        .offset(offset)
        .limit(limit + 1)
    ).all()

    return SearchListResponse(
        searches=[_summary(job) for job in rows[:limit]],
        limit=limit,
        offset=offset,
        has_more=len(rows) > limit,
    )


@router.get("/searches/{search_id}", response_model=SearchDetail)
def get_search(
    search_id: str,
    session: SessionDep,
    engine: EngineDep,
    principal: ApiPrincipalDep,
    include_results: bool = True,
):
    """Fetch one search, with its results once it has completed."""
    job = _require_job(session, principal, search_id)
    services.sync_job(session, engine, job)
    session.commit()

    results = services.job_results(job) if include_results else None
    return SearchDetail(**_summary(job).model_dump(), results=results)


@router.get(
    "/searches/{search_id}/results.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV of the results"}},
)
def get_search_csv(
    search_id: str,
    session: SessionDep,
    engine: EngineDep,
    principal: ApiPrincipalDep,
):
    """Download the results of a search as CSV."""
    job = _require_job(session, principal, search_id)
    services.sync_job(session, engine, job)
    session.commit()

    return Response(
        content=services.results_to_csv(services.job_results(job)),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{services.csv_filename(job)}"'
        },
    )


@router.delete("/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_search(search_id: str, session: SessionDep, principal: ApiPrincipalDep):
    """Delete a search and its stored results. Credits already used are not refunded."""
    job = _require_job(session, principal, search_id)
    session.delete(job)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/usage", response_model=UsageResponse)
def get_usage(session: SessionDep, principal: ApiPrincipalDep):
    """Your plan and lead consumption for the current period."""
    summary = quota.usage_for(session, principal.account)
    return UsageResponse(
        plan=summary.plan.code,
        period=summary.period,
        included=summary.included,
        used=summary.used,
        remaining=summary.remaining,
    )


def _require_job(session, principal, search_id: str) -> Job:
    job = session.scalar(
        select(Job).where(Job.id == search_id, Job.account_id == principal.account.id)
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such search on this account."
        )
    return job
