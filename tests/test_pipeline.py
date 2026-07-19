"""End-to-end tests for the Colddrops send pipeline (dry-run mode)."""
import os
import tempfile

os.environ["COLDDROPS_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.pop("ELEVENLABS_API_KEY", None)
os.environ.pop("DROPCOWBOY_TEAM_ID", None)
os.environ.pop("DROPCOWBOY_SECRET", None)

from fastapi.testclient import TestClient  # noqa: E402
from server import providers  # noqa: E402
from server.main import app  # noqa: E402

client = TestClient(app)


def test_health_dry_run():
    d = client.get("/api/health").json()
    assert d["ok"] and d["mode"] == "dry_run"


def test_script_merge():
    d = client.post("/api/script/preview", json={
        "script": "Hey {{first_name}} from {{company}}, {{missing_one}}!",
        "contact": {"first_name": "Kevin", "company": "SaaS Integrator"},
    }).json()
    assert d["text"] == "Hey Kevin from SaaS Integrator, [missing_one]!"
    assert d["missing"] == ["missing_one"]


def test_full_send_pipeline():
    camp = client.post("/api/campaigns", json={
        "name": "Test blast",
        "script": "Hey {{first_name}}, it's Alex. Call me back.",
    }).json()
    cid = camp["id"]

    r = client.post(f"/api/campaigns/{cid}/contacts", json={"contacts": [
        {"first_name": "Kevin", "company": "SaaS Integrator", "mobile": "+1 (832) 837-9384"},
        {"first_name": "NoPhone", "company": "Ghost Co"},
        {"first_name": "OptedOut", "company": "DNC Inc", "mobile": "+1 555 000 1111"},
    ]})
    assert r.json()["contact_count"] == 3

    assert client.post("/api/suppressions", json={"phone": "+1 555 000 1111"}).json()["suppressed"]

    d = client.post(f"/api/campaigns/{cid}/send", json={}).json()
    assert d == {"campaign_id": cid, "mode": "dry_run", "queued": 1,
                 "skipped_no_mobile": 1, "skipped_suppressed": 1}

    # TestClient runs background tasks before returning, so the drop is processed
    detail = client.get(f"/api/campaigns/{cid}").json()
    assert detail["drop_stats"] == {"delivered": 1}
    statuses = {c["first_name"]: c["status"] for c in detail["contacts"]}
    assert statuses["Kevin"] == "delivered"
    assert statuses["OptedOut"] == "suppressed"
    assert statuses["NoPhone"] == "queued"

    # a real audio artifact was rendered
    audio = [f for f in providers.AUDIO_DIR.iterdir() if f.name.startswith(f"cd_{cid}_")]
    assert audio and audio[0].stat().st_size > 1000


def test_webhook_updates_status():
    # find the delivered drop's foreign_id via campaign detail -> drops table isn't exposed,
    # so send a fresh one-contact campaign and flip it to failed via webhook
    cid = client.post("/api/campaigns", json={"name": "Hook", "script": "Hi {{first_name}}"}).json()["id"]
    client.post(f"/api/campaigns/{cid}/contacts", json={"contacts": [
        {"first_name": "Hooked", "mobile": "+1 999 222 3333"}]})
    client.post(f"/api/campaigns/{cid}/send", json={})
    import sqlite3
    conn = sqlite3.connect(os.environ["COLDDROPS_DB"]); conn.row_factory = sqlite3.Row
    fid = conn.execute("SELECT foreign_id FROM drops WHERE campaign_id=?", (cid,)).fetchone()[0]
    d = client.post("/api/webhooks/dropcowboy", json={"foreign_id": fid, "status": "failed"}).json()
    assert d["status"] == "failed"
    assert client.get(f"/api/campaigns/{cid}").json()["drop_stats"] == {"failed": 1}
    assert client.post("/api/webhooks/dropcowboy", json={"foreign_id": "nope", "status": "x"}).status_code == 404
