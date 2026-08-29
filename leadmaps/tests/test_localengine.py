"""The local engine: driving the scraper CLI as a subprocess."""

import json
import os
import stat
import time
from pathlib import Path

import pytest

from app.config import Settings
from app.engine import EngineError, ScrapeSpec
from app.localengine import LocalEngine, parse_results


def make_settings(tmp_path, **extra) -> Settings:
    defaults = dict(
        engine_mode="local",
        engine_workdir=str(tmp_path / "jobs"),
        engine_job_timeout=30,
        engine_concurrency=2,
    )
    defaults.update(extra)
    return Settings(**defaults)


def stub_scraper(tmp_path, body: str) -> str:
    """A fake scraper honouring the real CLI contract (-input, -results, -json)."""
    script = tmp_path / "stub-scraper"
    script.write_text(body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


WRITES_TWO_ROWS = """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
out = args[args.index("-results") + 1]
query = open(args[args.index("-input") + 1]).read().strip()
depth = int(args[args.index("-depth") + 1])
json.dump(
    [{"title": f"{query} #{i}", "phone": "+1 555 0100"} for i in range(depth * 2)],
    open(out, "w"),
)
"""

FAILS_LOUDLY = """#!/usr/bin/env python3
import sys
print("playwright: browser not installed", file=sys.stderr)
sys.exit(1)
"""

WRITES_THEN_FAILS = """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
out = args[args.index("-results") + 1]
json.dump([{"title": "Partial"}], open(out, "w"))
print("interrupted", file=sys.stderr)
sys.exit(2)
"""

SLEEPS_FOREVER = """#!/usr/bin/env python3
import time
time.sleep(600)
"""


def wait_for(engine, job_id, timeout=20.0):
    """Poll until the run leaves the running state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = engine.fetch(job_id)
        if job.status != "running":
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished")


def test_a_successful_scrape_returns_rows(tmp_path):
    engine = LocalEngine(
        make_settings(tmp_path, engine_binary=stub_scraper(tmp_path, WRITES_TWO_ROWS))
    )
    job = wait_for(engine, engine.submit(ScrapeSpec(keyword="cafes in Oslo", max_depth=3)))

    assert job.status == "completed"
    assert job.result_count == 6
    assert job.results[0]["title"] == "cafes in Oslo #0"


def test_a_scrape_starts_out_running(tmp_path):
    engine = LocalEngine(
        make_settings(tmp_path, engine_binary=stub_scraper(tmp_path, SLEEPS_FOREVER))
    )
    assert engine.fetch(engine.submit(ScrapeSpec(keyword="cafes"))).status == "running"


def test_a_failing_scraper_surfaces_its_last_error_line(tmp_path):
    engine = LocalEngine(
        make_settings(tmp_path, engine_binary=stub_scraper(tmp_path, FAILS_LOUDLY))
    )
    job = wait_for(engine, engine.submit(ScrapeSpec(keyword="cafes")))

    assert job.status == "failed"
    assert "browser not installed" in job.error


def test_rows_written_before_a_crash_are_kept(tmp_path):
    # The scraper can die partway having already written usable rows; those
    # rows are the customer's data and must not be thrown away.
    engine = LocalEngine(
        make_settings(tmp_path, engine_binary=stub_scraper(tmp_path, WRITES_THEN_FAILS))
    )
    job = wait_for(engine, engine.submit(ScrapeSpec(keyword="cafes")))

    assert job.status == "completed"
    assert job.result_count == 1


def test_a_timeout_is_reported_not_hung(tmp_path):
    engine = LocalEngine(
        make_settings(
            tmp_path,
            engine_binary=stub_scraper(tmp_path, SLEEPS_FOREVER),
            engine_job_timeout=1,
        )
    )
    job = wait_for(engine, engine.submit(ScrapeSpec(keyword="cafes")))

    assert job.status == "failed"
    assert "too long" in job.error


def test_an_unknown_job_is_reported_rather_than_hanging(tmp_path):
    engine = LocalEngine(make_settings(tmp_path, engine_binary=stub_scraper(tmp_path, "#!/bin/sh\n")))
    with pytest.raises(EngineError, match="restarted"):
        engine.fetch("local_does_not_exist")


def test_a_missing_binary_is_caught_before_launching(tmp_path):
    engine = LocalEngine(make_settings(tmp_path, engine_binary="/no/such/scraper"))
    with pytest.raises(EngineError, match="does not exist"):
        engine.submit(ScrapeSpec(keyword="cafes"))


# --- Command construction ---------------------------------------------------


def build(tmp_path, spec, **extra):
    engine = LocalEngine(make_settings(tmp_path, engine_binary="/bin/true", **extra))
    job_dir = tmp_path / "d"
    job_dir.mkdir(exist_ok=True)
    return engine._build_argv(spec, job_dir, job_dir / "q.txt", job_dir / "r.json")


def test_command_carries_the_core_flags(tmp_path):
    argv = build(tmp_path, ScrapeSpec(keyword="cafes", lang="de", max_depth=7))

    assert "-json" in argv
    assert argv[argv.index("-depth") + 1] == "7"
    assert argv[argv.index("-lang") + 1] == "de"
    # Without this the scraper waits for more input and never exits.
    assert "-exit-on-inactivity" in argv


def test_email_flag_is_only_added_when_requested(tmp_path):
    assert "-email" not in build(tmp_path, ScrapeSpec(keyword="cafes"))
    assert "-email" in build(tmp_path, ScrapeSpec(keyword="cafes", extract_emails=True))


def test_radius_is_converted_from_km_to_metres(tmp_path):
    # The app talks kilometres; the scraper CLI takes metres.
    argv = build(tmp_path, ScrapeSpec(keyword="cafes", radius=5.0))
    assert argv[argv.index("-radius") + 1] == "5000"


def test_geo_and_zoom_travel_together(tmp_path):
    argv = build(tmp_path, ScrapeSpec(keyword="cafes", geo_coordinates="53.4,-2.2", zoom=14))
    assert argv[argv.index("-geo") + 1] == "53.4,-2.2"
    assert argv[argv.index("-zoom") + 1] == "14"


def test_proxies_are_passed_through(tmp_path):
    argv = build(tmp_path, ScrapeSpec(keyword="cafes"), engine_proxies="http://user:pw@host:8080")
    assert argv[argv.index("-proxies") + 1] == "http://user:pw@host:8080"


def test_docker_is_used_when_no_binary_is_configured(tmp_path):
    engine = LocalEngine(make_settings(tmp_path, engine_binary=""))
    job_dir = tmp_path / "d"
    job_dir.mkdir(exist_ok=True)
    argv = engine._build_argv(
        ScrapeSpec(keyword="cafes"), job_dir, job_dir / "q.txt", job_dir / "r.json"
    )

    assert argv[0] == "docker"
    assert f"{job_dir}:/data" in argv
    # Paths must be container-side, not host-side.
    assert argv[argv.index("-input") + 1] == "/data/queries.txt"
    assert argv[argv.index("-results") + 1] == "/data/results.json"


# --- Output parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        '[{"title": "A"}, {"title": "B"}]',      # JSON array
        '{"title": "A"}\n{"title": "B"}',        # newline delimited
        '{"title": "A"}{"title": "B"}',          # concatenated
        '{"title": "A"},\n{"title": "B"},',      # trailing commas
    ],
)
def test_every_plausible_json_shape_parses(tmp_path, body):
    path = tmp_path / "results.json"
    path.write_text(body)
    assert [row["title"] for row in parse_results(path)] == ["A", "B"]


def test_empty_or_missing_output_is_not_an_error(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("")
    assert parse_results(empty) == []
    assert parse_results(tmp_path / "absent.json") == []


# --- Through the whole app --------------------------------------------------


def test_a_real_subprocess_scrape_flows_through_the_dashboard(tmp_path, monkeypatch):
    """Signup, search, poll and export, driving an actual subprocess."""
    import importlib

    from app.config import get_settings

    binary = stub_scraper(tmp_path, WRITES_TWO_ROWS)

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/e2e.db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("ENGINE_MODE", "local")
    monkeypatch.setenv("ENGINE_BINARY", binary)
    monkeypatch.setenv("ENGINE_WORKDIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")

    import app.db
    importlib.reload(app.db)
    import app.deps
    importlib.reload(app.deps)
    for name in ("app.routes.marketing", "app.routes.auth", "app.routes.dashboard",
                 "app.routes.api_v1", "app.routes.webhooks", "app.main"):
        importlib.reload(importlib.import_module(name))

    from app.engine import reset_local_engine
    reset_local_engine()

    from fastapi.testclient import TestClient

    from app.main import app as fresh_app

    try:
        with TestClient(fresh_app, follow_redirects=True) as client:
            client.post(
                "/signup",
                data={"email": "real@example.com", "password": "a-good-long-password"},
            )
            response = client.post(
                "/app/search", data={"keyword": "cafes in Oslo", "max_depth": "2"}
            )
            job_id = response.url.path.rsplit("/", 1)[-1]

            # The subprocess runs asynchronously; poll the job page.
            for _ in range(100):
                body = client.get(f"/app/jobs/{job_id}").text
                if "badge-completed" in body:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("the search never completed")

            assert "cafes in Oslo #0" in body

            csv_body = client.get(f"/app/jobs/{job_id}/export.csv").text
            lines = csv_body.strip().splitlines()
            assert len(lines) == 5  # header + 4 rows (depth 2 x 2)
            assert "cafes in Oslo #0" in csv_body

            # And the leads were metered against the plan.
            assert "96 leads left" in client.get("/app").text
    finally:
        reset_local_engine()
        get_settings.cache_clear()
