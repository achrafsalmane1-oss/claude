"""Adapters to the scraping engine.

The engine is `google-maps-scraper` running in SaaS mode. It exposes a small
REST surface (``POST /api/v1/scrape``, ``GET /api/v1/jobs/{id}``) guarded by an
``X-API-Key`` header. This module is the only place that knows about it, so the
rest of the app can be developed and tested against :class:`MockEngine`.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.config import Settings


class EngineError(Exception):
    """The engine could not accept or report on a job."""


@dataclass
class ScrapeSpec:
    keyword: str
    lang: str = "en"
    max_depth: int = 1
    extract_emails: bool = False
    geo_coordinates: str = ""
    zoom: int = 0
    radius: float = 0.0
    fast_mode: bool = False
    timeout: int = 300

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "keyword": self.keyword,
            "lang": self.lang,
            "max_depth": self.max_depth,
            "email": self.extract_emails,
            "timeout": self.timeout,
        }
        if self.geo_coordinates:
            payload["geo_coordinates"] = self.geo_coordinates
        if self.zoom:
            payload["zoom"] = self.zoom
        if self.radius:
            payload["radius"] = self.radius
        if self.fast_mode:
            payload["fast_mode"] = True
        return payload


@dataclass
class EngineJob:
    """Engine-side job state, normalised to this app's status vocabulary."""

    job_id: str
    status: str
    result_count: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


# The engine (River queue) uses its own state names; map them onto ours.
_STATUS_MAP = {
    "pending": "queued",
    "available": "queued",
    "scheduled": "queued",
    "retryable": "queued",
    "running": "running",
    "completed": "completed",
    "failed": "failed",
    "discarded": "failed",
    "cancelled": "cancelled",
}


def normalise_status(raw: str) -> str:
    return _STATUS_MAP.get((raw or "").lower(), "queued")


class Engine(Protocol):
    def submit(self, spec: ScrapeSpec) -> str: ...

    def fetch(self, engine_job_id: str) -> EngineJob: ...


class HTTPEngine:
    """Talks to a real google-maps-scraper SaaS deployment."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            headers={"X-API-Key": self._api_key, "Content-Type": "application/json"},
        )

    def submit(self, spec: ScrapeSpec) -> str:
        try:
            with self._client() as client:
                response = client.post("/api/v1/scrape", json=spec.to_payload())
        except httpx.HTTPError as exc:
            raise EngineError(f"could not reach the scraping engine: {exc}") from exc

        if response.status_code >= 400:
            raise EngineError(_engine_message(response))

        job_id = response.json().get("job_id", "")
        if not job_id:
            raise EngineError("engine accepted the job but returned no job id")
        return job_id

    def fetch(self, engine_job_id: str) -> EngineJob:
        try:
            with self._client() as client:
                response = client.get(f"/api/v1/jobs/{engine_job_id}")
        except httpx.HTTPError as exc:
            raise EngineError(f"could not reach the scraping engine: {exc}") from exc

        if response.status_code == 404:
            raise EngineError("job not found on the engine")
        if response.status_code >= 400:
            raise EngineError(_engine_message(response))

        body = response.json()
        results = body.get("results") or []
        if not isinstance(results, list):
            results = []
        return EngineJob(
            job_id=engine_job_id,
            status=normalise_status(body.get("status", "")),
            result_count=int(body.get("result_count") or len(results)),
            results=results,
            error=body.get("error", "") or "",
        )


def _engine_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"engine returned HTTP {response.status_code}"
    return body.get("message") or body.get("error") or f"engine returned HTTP {response.status_code}"


class MockEngine:
    """A deterministic stand-in for the scraping engine.

    Jobs complete immediately with plausible, seeded results. This keeps the
    whole product demoable and testable without a running Go engine, and it is
    the default in development.
    """

    _CATEGORIES = [
        "Dentist", "Plumber", "Law firm", "Coffee shop", "Gym",
        "Accountant", "Hair salon", "Auto repair", "Real estate agency", "Bakery",
    ]
    _STREETS = ["Main St", "Oak Ave", "High St", "Market St", "Park Rd", "Church Ln"]
    _SUFFIXES = ["& Co", "Group", "Partners", "Services", "Studio", "Works", "Collective"]

    def __init__(self, results_per_page: int = 20) -> None:
        self._results_per_page = results_per_page
        self._jobs: dict[str, EngineJob] = {}

    def submit(self, spec: ScrapeSpec) -> str:
        seed = hashlib.sha256(
            f"{spec.keyword}|{spec.lang}|{spec.max_depth}".encode("utf-8")
        ).hexdigest()
        job_id = f"mock_{seed[:16]}"
        count = max(1, spec.max_depth) * self._results_per_page
        results = self._generate(spec, seed, count)
        self._jobs[job_id] = EngineJob(
            job_id=job_id,
            status="completed",
            result_count=len(results),
            results=results,
        )
        return job_id

    def fetch(self, engine_job_id: str) -> EngineJob:
        job = self._jobs.get(engine_job_id)
        if job is None:
            raise EngineError("job not found on the engine")
        return job

    def _generate(self, spec: ScrapeSpec, seed: str, count: int) -> list[dict[str, Any]]:
        rng = random.Random(seed)
        city = spec.keyword.split(" in ")[-1].strip().title() or "Springfield"
        base_term = spec.keyword.split(" in ")[0].strip().title() or "Business"
        rows = []
        for index in range(count):
            name = f"{city.split()[0]} {base_term} {rng.choice(self._SUFFIXES)} {index + 1}"
            slug = name.lower().replace(" ", "").replace("&", "and")[:24]
            rows.append(
                {
                    "title": name,
                    "category": rng.choice(self._CATEGORIES),
                    "address": f"{rng.randint(1, 999)} {rng.choice(self._STREETS)}, {city}",
                    "phone": f"+1 555 {rng.randint(100, 999)} {rng.randint(1000, 9999)}",
                    "web_site": f"https://{slug}.example.com",
                    "review_count": rng.randint(0, 480),
                    "review_rating": round(rng.uniform(3.0, 5.0), 1),
                    "latitude": round(rng.uniform(-90, 90), 6),
                    "longtitude": round(rng.uniform(-180, 180), 6),
                    "link": f"https://maps.google.com/?cid={rng.getrandbits(48)}",
                    "emails": [f"hello@{slug}.example.com"] if spec.extract_emails else [],
                }
            )
        return rows


def build_engine(settings: Settings) -> Engine:
    if settings.engine_mode == "http":
        return HTTPEngine(
            base_url=settings.engine_url,
            api_key=settings.engine_api_key,
            timeout=settings.engine_timeout,
        )
    return MockEngine()
