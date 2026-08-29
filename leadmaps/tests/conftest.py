"""Test fixtures. Each test gets a throwaway SQLite database."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import pytest

# Settings are read at import time, so the environment must be set up first.
_TMPDIR = tempfile.mkdtemp(prefix="leadmaps-tests-")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENGINE_MODE", "mock")
os.environ.setdefault("PUBLIC_URL", "http://testserver")

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient backed by a fresh database."""
    db_path = tmp_path / "test.db"

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("ENGINE_MODE", "mock")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")

    # The db module binds an engine at import time; rebuild it for this test.
    import app.db as db_module
    import importlib

    importlib.reload(db_module)

    import app.deps as deps_module
    importlib.reload(deps_module)

    for name in ("app.routes.marketing", "app.routes.auth", "app.routes.dashboard",
                 "app.routes.api_v1", "app.routes.webhooks", "app.main"):
        importlib.reload(importlib.import_module(name))

    from app.main import app as fresh_app

    with TestClient(fresh_app, follow_redirects=True) as test_client:
        yield test_client

    get_settings.cache_clear()


@pytest.fixture()
def account(client):
    """A signed-in account on the free plan."""
    response = client.post(
        "/signup",
        data={
            "email": "owner@example.com",
            "password": "a-good-long-password",
            "company_name": "Example Co",
        },
    )
    assert response.status_code == 200
    return client


def upgrade(client, plan_code: str) -> None:
    """Move the signed-in account onto ``plan_code`` (billing is disabled in tests)."""
    response = client.get(f"/app/billing/checkout?plan={plan_code}")
    assert response.status_code == 200


def mint_key(client) -> str:
    response = client.post("/app/api-keys", data={"name": "test"})
    match = re.search(r"lm_live_[A-Za-z0-9_\-]+", response.text)
    assert match, "no API key was returned"
    return match.group(0)


def job_id_from(response) -> str:
    match = re.search(r"/app/jobs/([0-9a-f]{32})", response.text)
    if match:
        return match.group(1)
    match = re.search(r"([0-9a-f]{32})", str(response.url))
    assert match, "could not find a job id"
    return match.group(1)
