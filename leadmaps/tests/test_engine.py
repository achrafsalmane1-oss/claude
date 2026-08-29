"""The adapter between this app and the google-maps-scraper engine."""

import httpx
import pytest

from app.engine import (
    EngineError,
    HTTPEngine,
    MockEngine,
    ScrapeSpec,
    normalise_status,
)


def make_engine(handler) -> HTTPEngine:
    """An HTTPEngine whose requests are served by ``handler`` in-process."""
    engine = HTTPEngine("http://engine.test", "engine-key")
    transport = httpx.MockTransport(handler)
    engine._client = lambda: httpx.Client(  # noqa: SLF001 - test seam
        transport=transport,
        base_url="http://engine.test",
        headers={"X-API-Key": "engine-key"},
    )
    return engine


def test_payload_matches_the_engine_contract():
    spec = ScrapeSpec(
        keyword="dentists in Manchester",
        lang="en",
        max_depth=3,
        extract_emails=True,
        geo_coordinates="53.48,-2.24",
        zoom=14,
        radius=5.0,
    )
    payload = spec.to_payload()

    # The engine names the email flag "email", not "extract_emails".
    assert payload["email"] is True
    assert payload["keyword"] == "dentists in Manchester"
    assert payload["max_depth"] == 3
    assert payload["geo_coordinates"] == "53.48,-2.24"
    assert payload["zoom"] == 14
    assert payload["radius"] == 5.0


def test_optional_fields_are_omitted_when_unset():
    payload = ScrapeSpec(keyword="cafes").to_payload()
    assert "geo_coordinates" not in payload
    assert "zoom" not in payload
    assert "fast_mode" not in payload


def test_submit_returns_the_engine_job_id():
    def handler(request):
        assert request.url.path == "/api/v1/scrape"
        assert request.headers["X-API-Key"] == "engine-key"
        return httpx.Response(202, json={"job_id": "abc123", "status": "pending"})

    assert make_engine(handler).submit(ScrapeSpec(keyword="cafes")) == "abc123"


def test_submit_surfaces_the_engine_error_message():
    def handler(request):
        return httpx.Response(400, json={"message": "keyword is required"})

    with pytest.raises(EngineError, match="keyword is required"):
        make_engine(handler).submit(ScrapeSpec(keyword="cafes"))


def test_submit_fails_loudly_when_no_job_id_comes_back():
    def handler(request):
        return httpx.Response(202, json={"status": "pending"})

    with pytest.raises(EngineError, match="no job id"):
        make_engine(handler).submit(ScrapeSpec(keyword="cafes"))


def test_an_unreachable_engine_raises_engine_error():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(EngineError, match="could not reach"):
        make_engine(handler).submit(ScrapeSpec(keyword="cafes"))


def test_fetch_normalises_results():
    def handler(request):
        assert request.url.path == "/api/v1/jobs/abc123"
        return httpx.Response(
            200,
            json={
                "job_id": "abc123",
                "status": "completed",
                "result_count": 2,
                "results": [{"title": "One"}, {"title": "Two"}],
            },
        )

    job = make_engine(handler).fetch("abc123")
    assert job.status == "completed"
    assert job.result_count == 2
    assert [row["title"] for row in job.results] == ["One", "Two"]


def test_fetch_tolerates_a_null_results_field():
    def handler(request):
        return httpx.Response(200, json={"status": "running", "results": None})

    job = make_engine(handler).fetch("abc123")
    assert job.status == "running"
    assert job.results == []


def test_missing_job_raises():
    def handler(request):
        return httpx.Response(404, json={"message": "job not found"})

    with pytest.raises(EngineError, match="not found"):
        make_engine(handler).fetch("nope")


@pytest.mark.parametrize(
    ("engine_status", "expected"),
    [
        ("pending", "queued"),
        ("available", "queued"),
        ("scheduled", "queued"),
        ("retryable", "queued"),
        ("running", "running"),
        ("completed", "completed"),
        ("discarded", "failed"),
        ("cancelled", "cancelled"),
        ("something-new", "queued"),
    ],
)
def test_engine_states_map_onto_our_vocabulary(engine_status, expected):
    assert normalise_status(engine_status) == expected


def test_mock_engine_is_deterministic():
    """A fresh engine must produce the same rows, so demos and tests are stable."""
    spec = ScrapeSpec(keyword="cafes in Oslo", max_depth=2)

    first_engine = MockEngine()
    first = first_engine.fetch(first_engine.submit(spec)).results

    second_engine = MockEngine()
    second = second_engine.fetch(second_engine.submit(spec)).results

    assert first == second


def test_mock_engine_returns_one_page_worth_of_rows_per_depth():
    engine = MockEngine()
    job = engine.fetch(engine.submit(ScrapeSpec(keyword="cafes", max_depth=3)))
    assert job.result_count == 60


def test_mock_engine_only_returns_emails_when_asked():
    engine = MockEngine()
    without = engine.fetch(engine.submit(ScrapeSpec(keyword="cafes"))).results
    with_emails = engine.fetch(
        engine.submit(ScrapeSpec(keyword="cafes", extract_emails=True))
    ).results
    assert without[0]["emails"] == []
    assert with_emails[0]["emails"]
