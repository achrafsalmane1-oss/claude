"""Run the google-maps-scraper CLI directly, for real data with no queue.

The scraper's CLI mode needs no database, no admin UI and no provisioning
wizard: it takes a file of queries, scrapes, and writes JSON. This engine drives
one subprocess per search on a background thread.

Good for a single box and modest volume. Past that, move to a full
google-maps-scraper SaaS deployment and set ``ENGINE_MODE=http`` — that gives
you a real queue, retries and horizontal workers.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import Settings
from app.engine import EngineError, EngineJob, ScrapeSpec
from app.log import logger

# The CLI takes a radius in metres; the rest of this app talks kilometres.
METRES_PER_KM = 1000


@dataclass
class _Run:
    """One in-flight or finished scrape."""

    job_id: str
    output: Path
    status: str = "running"
    error: str = ""
    results: list[dict[str, Any]] = field(default_factory=list)


class LocalEngine:
    """Drives the scraper binary (or its Docker image) as a subprocess."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._workdir = Path(settings.engine_workdir).resolve()
        self._workdir.mkdir(parents=True, exist_ok=True)
        self._runs: dict[str, _Run] = {}
        self._lock = threading.Lock()

    # --- Engine protocol ------------------------------------------------

    def submit(self, spec: ScrapeSpec) -> str:
        self._preflight()

        job_id = f"local_{uuid.uuid4().hex[:16]}"
        job_dir = self._workdir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        query_file = job_dir / "queries.txt"
        query_file.write_text(spec.keyword + "\n", encoding="utf-8")
        output = job_dir / "results.json"

        run = _Run(job_id=job_id, output=output)
        with self._lock:
            self._runs[job_id] = run

        argv = self._build_argv(spec, job_dir, query_file, output)
        logger.info("starting local scrape %s: %s", job_id, " ".join(argv))

        thread = threading.Thread(
            target=self._run, args=(run, argv), name=f"scrape-{job_id}", daemon=True
        )
        thread.start()
        return job_id

    def fetch(self, engine_job_id: str) -> EngineJob:
        with self._lock:
            run = self._runs.get(engine_job_id)

        if run is None:
            # A restart loses in-flight runs; report it rather than hanging.
            raise EngineError(
                "this search was lost when the server restarted; please run it again"
            )

        return EngineJob(
            job_id=run.job_id,
            status=run.status,
            result_count=len(run.results),
            results=run.results,
            error=run.error,
        )

    # --- Internals -------------------------------------------------------

    def _preflight(self) -> None:
        """Fail fast, with a message that says how to fix it."""
        if self._settings.engine_binary:
            if not Path(self._settings.engine_binary).exists():
                raise EngineError(
                    f"ENGINE_BINARY points at {self._settings.engine_binary}, "
                    "which does not exist."
                )
            return

        if shutil.which("docker") is None:
            raise EngineError(
                "Neither ENGINE_BINARY nor Docker is available. Install Docker, "
                "or set ENGINE_BINARY to a google-maps-scraper binary."
            )

    def _build_argv(
        self, spec: ScrapeSpec, job_dir: Path, query_file: Path, output: Path
    ) -> list[str]:
        settings = self._settings

        if settings.engine_binary:
            argv = [settings.engine_binary]
            in_path, out_path = str(query_file), str(output)
        else:
            # Mount the job directory so the container reads and writes in place.
            argv = [
                "docker", "run", "--rm",
                "-v", f"{job_dir}:/data",
                settings.engine_docker_image,
            ]
            in_path, out_path = "/data/queries.txt", "/data/results.json"

        argv += [
            "-input", in_path,
            "-results", out_path,
            "-json",
            "-depth", str(spec.max_depth),
            "-lang", spec.lang or "en",
            "-c", str(max(1, settings.engine_concurrency)),
            # Without this the scraper waits for more input and never exits.
            "-exit-on-inactivity", "3m",
        ]

        if spec.extract_emails:
            argv.append("-email")
        if spec.geo_coordinates:
            argv += ["-geo", spec.geo_coordinates]
            if spec.zoom:
                argv += ["-zoom", str(spec.zoom)]
        if spec.radius:
            argv += ["-radius", str(int(spec.radius * METRES_PER_KM))]
        if spec.fast_mode:
            argv.append("-fast-mode")
        if settings.engine_proxies:
            argv += ["-proxies", settings.engine_proxies]

        return argv

    def _run(self, run: _Run, argv: list[str]) -> None:
        try:
            completed = subprocess.run(  # noqa: S603 - argv is built, never shell
                argv,
                capture_output=True,
                text=True,
                timeout=self._settings.engine_job_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            run.status = "failed"
            run.error = "The search took too long and was stopped."
            logger.warning("local scrape %s timed out", run.job_id)
            return
        except OSError as exc:
            run.status = "failed"
            run.error = f"Could not start the scraper: {exc}"
            logger.error("local scrape %s could not start: %s", run.job_id, exc)
            return

        # The scraper can exit non-zero having still written usable rows, so
        # read the output first and only fail if there is nothing to show.
        rows = parse_results(run.output)

        if rows:
            run.results = rows
            run.status = "completed"
            logger.info("local scrape %s produced %d rows", run.job_id, len(rows))
            return

        if completed.returncode != 0:
            run.status = "failed"
            run.error = _tail(completed.stderr) or "The scraper exited with an error."
            logger.warning(
                "local scrape %s failed (rc=%s): %s",
                run.job_id, completed.returncode, run.error,
            )
            return

        # Ran cleanly but found nothing — a legitimate empty result.
        run.status = "completed"
        run.results = []


def parse_results(path: Path) -> list[dict[str, Any]]:
    """Read the scraper's JSON output.

    Tolerates a JSON array, newline-delimited objects, or concatenated objects,
    so an upstream change of writer does not silently produce empty lists.
    """
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return []

    if not text:
        return []

    # A single JSON document: either an array of rows or one row.
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(loaded, list):
            return [row for row in loaded if isinstance(row, dict)]
        return [loaded] if isinstance(loaded, dict) else []

    # Newline-delimited objects.
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    if rows:
        return rows

    # Concatenated objects with no separator: {...}{...}
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        try:
            row, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            break
        if isinstance(row, dict):
            rows.append(row)
        index = end
        while index < len(text) and text[index] in " \t\r\n,":
            index += 1
    return rows


def _tail(stderr: str, limit: int = 400) -> str:
    """The last useful line of scraper output, for the customer-facing error."""
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    return lines[-1][:limit] if lines else ""
