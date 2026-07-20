"""End-to-end tests for Colddrops: auth, scoping, send pipeline, usage caps, CSV."""
import os
import tempfile

os.environ["COLDDROPS_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["VOICE_BACKEND"] = "chime"      # offline, deterministic
os.environ["DELIVERY_BACKEND"] = "dry_run"
for k in ("ELEVENLABS_API_KEY", "TELNYX_API_KEY", "TELNYX_CONNECTION_ID", "TELNYX_FROM_NUMBER"):
    os.environ.pop(k, None)

import sqlite3  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from server import auth, providers  # noqa: E402
from server.main import app  # noqa: E402

client = TestClient(app)


def signup(email, pw="password123"):
    r = client.post("/api/auth/signup", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_health_public():
    d = client.get("/api/health").json()
    assert d["ok"] and d["mode"] == "dry_run"


def test_auth_required():
    assert client.get("/api/campaigns").status_code == 401
    assert client.post("/api/campaigns", json={"name": "x"}).status_code == 401


def test_signup_login_me():
    h = signup("founder@acme.com")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["email"] == "founder@acme.com"
    assert me["usage"] == {"plan": "starter", "cap": 1000, "used": 0, "remaining": 1000}
    # wrong password rejected, right one works
    assert client.post("/api/auth/login", json={"email": "founder@acme.com", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "founder@acme.com", "password": "password123"}).status_code == 200


def test_script_merge():
    h = signup("s@acme.com")
    d = client.post("/api/script/preview", headers=h, json={
        "script": "Hey {{first_name}} from {{company}}, {{missing_one}}!",
        "contact": {"first_name": "Kevin", "company": "SaaS Integrator"}}).json()
    assert d["text"] == "Hey Kevin from SaaS Integrator, [missing_one]!"
    assert d["missing"] == ["missing_one"]


def test_workspace_isolation():
    a = signup("a@x.com")
    b = signup("b@y.com")
    cid = client.post("/api/campaigns", headers=a, json={"name": "A's", "script": "hi"}).json()["id"]
    # B cannot see or open A's campaign
    assert client.get(f"/api/campaigns/{cid}", headers=b).status_code == 404
    assert cid not in [c["id"] for c in client.get("/api/campaigns", headers=b).json()["campaigns"]]


def test_full_send_pipeline_and_csv():
    h = signup("send@acme.com")
    cid = client.post("/api/campaigns", headers=h, json={
        "name": "Test blast", "script": "Hey {{first_name}}, it's Alex. Call me back."}).json()["id"]
    client.post(f"/api/campaigns/{cid}/contacts", headers=h, json={"contacts": [
        {"first_name": "Kevin", "company": "SaaS Integrator", "mobile": "+1 (832) 837-9384"},
        {"first_name": "NoPhone", "company": "Ghost Co"},
        {"first_name": "OptedOut", "company": "DNC Inc", "mobile": "+1 555 000 1111"}]})
    client.post("/api/suppressions", headers=h, json={"phone": "+1 555 000 1111"})

    d = client.post(f"/api/campaigns/{cid}/send", headers=h, json={}).json()
    assert d["queued"] == 1 and d["skipped_no_mobile"] == 1 and d["skipped_suppressed"] == 1
    assert d["usage"]["used"] == 1

    detail = client.get(f"/api/campaigns/{cid}", headers=h).json()
    assert detail["drop_stats"] == {"delivered": 1}
    statuses = {c["first_name"]: c["status"] for c in detail["contacts"]}
    assert statuses == {"Kevin": "delivered", "NoPhone": "queued", "OptedOut": "suppressed"}

    # CSV export
    r = client.get(f"/api/campaigns/{cid}/contacts.csv", headers=h)
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    assert "first_name" in r.text and "Kevin" in r.text

    audio = [f for f in providers.AUDIO_DIR.iterdir() if f.name.startswith(f"cd_{cid}_")]
    assert audio and audio[0].stat().st_size > 1000


def test_plan_cap_enforced():
    h = signup("cap@acme.com")
    # force a tiny cap by switching plan directly
    conn = sqlite3.connect(os.environ["COLDDROPS_DB"])
    conn.execute("UPDATE workspaces SET plan='starter'")
    conn.commit()
    # shrink cap for the test
    auth.PLAN_CAPS["starter"] = 2
    try:
        cid = client.post("/api/campaigns", headers=h, json={"name": "cap", "script": "Hi {{first_name}}"}).json()["id"]
        client.post(f"/api/campaigns/{cid}/contacts", headers=h, json={"contacts": [
            {"first_name": f"P{i}", "mobile": f"+1 415 555 12{i:02d}"} for i in range(5)]})
        d = client.post(f"/api/campaigns/{cid}/send", headers=h, json={}).json()
        assert d["queued"] == 2 and d["hit_plan_cap"] is True
        assert client.get("/api/usage", headers=h).json()["remaining"] == 0
    finally:
        auth.PLAN_CAPS["starter"] = 1000


def test_ab_variants_and_analytics():
    h = signup("ab@acme.com")
    cid = client.post("/api/campaigns", headers=h, json={
        "name": "A/B test", "script": "Variant A {{first_name}}",
        "variants": ["Variant B {{first_name}}"]}).json()["id"]
    client.post(f"/api/campaigns/{cid}/contacts", headers=h, json={"contacts": [
        {"first_name": f"P{i}", "mobile": f"+1 415 555 70{i:02d}"} for i in range(4)]})
    client.post(f"/api/campaigns/{cid}/send", headers=h, json={})
    # contacts alternate between variant 0 and 1
    detail = client.get(f"/api/campaigns/{cid}", headers=h).json()
    variants_assigned = sorted(c["variant"] for c in detail["contacts"])
    assert variants_assigned == [0, 0, 1, 1]
    # mark one B-variant contact as called back
    b_contact = [c for c in detail["contacts"] if c["variant"] == 1][0]["id"]
    client.post(f"/api/contacts/{b_contact}/callback", headers=h)
    a = client.get(f"/api/campaigns/{cid}/analytics", headers=h).json()
    assert [v["variant"] for v in a["variants"]] == ["A", "B"]
    assert a["variants"][0]["sent"] == 2 and a["variants"][1]["callbacks"] == 1
    assert a["winner"] == "B"


def test_team_invite_and_join():
    owner = signup("owner@team.com")
    inv = client.post("/api/team/invite", headers=owner, json={"email": "mate@team.com"}).json()
    assert "invite_token" in inv and inv["email"] == "mate@team.com"
    # pending invite shows for the workspace
    t = client.get("/api/team", headers=owner).json()
    assert len(t["members"]) == 1 and t["pending"][0]["email"] == "mate@team.com"
    # teammate signs up with the invite -> joins the SAME workspace
    r = client.post("/api/auth/signup", json={
        "email": "mate@team.com", "password": "password123", "invite_token": inv["invite_token"]}).json()
    assert r["workspace"] == client.get("/api/auth/me", headers=owner).json()["workspace"]
    mate = {"Authorization": "Bearer " + r["token"]}
    # both users now see the same workspace + shared campaigns
    cid = client.post("/api/campaigns", headers=owner, json={"name": "shared", "script": "hi"}).json()["id"]
    assert cid in [c["id"] for c in client.get("/api/campaigns", headers=mate).json()["campaigns"]]
    # invite can't be reused
    assert client.post("/api/auth/signup", json={
        "email": "third@team.com", "password": "password123", "invite_token": inv["invite_token"]}).status_code == 400


def test_callbacks_flow():
    h = signup("cb@acme.com")
    cid = client.post("/api/campaigns", headers=h, json={"name": "cb", "script": "Hi {{first_name}}"}).json()["id"]
    client.post(f"/api/campaigns/{cid}/contacts", headers=h, json={"contacts": [
        {"first_name": "Rang", "company": "Back Co", "mobile": "+1 415 555 9000"}]})
    # find the contact id
    ct = client.get(f"/api/campaigns/{cid}", headers=h).json()["contacts"][0]["id"]
    assert client.get("/api/callbacks", headers=h).json()["count"] == 0
    assert client.post(f"/api/contacts/{ct}/callback", headers=h).json()["status"] == "called_back"
    cbs = client.get("/api/callbacks", headers=h).json()
    assert cbs["count"] == 1 and cbs["callbacks"][0]["first_name"] == "Rang"
    # another workspace can't mark my contact
    b = signup("cb2@acme.com")
    assert client.post(f"/api/contacts/{ct}/callback", headers=b).status_code == 404


def test_billing_stub_upgrade():
    h = signup("bill@acme.com")
    plans = client.get("/api/billing/plans").json()
    assert plans["mode"] == "stub"
    assert {p["id"] for p in plans["plans"]} == {"starter", "growth", "scale"}
    # stub checkout applies the plan immediately
    r = client.post("/api/billing/checkout", headers=h, json={"plan": "growth"}).json()
    assert r["stub"] is True and "upgraded=growth" in r["url"]
    assert client.get("/api/usage", headers=h).json() == {"plan": "growth", "cap": 5000, "used": 0, "remaining": 5000}


def test_stripe_webhook_upgrades_workspace():
    h = signup("hook2@acme.com")
    wid = client.get("/api/auth/me", headers=h)  # ensure workspace exists
    assert wid.status_code == 200
    import sqlite3
    conn = sqlite3.connect(os.environ["COLDDROPS_DB"]); conn.row_factory = sqlite3.Row
    w = conn.execute("SELECT w.id FROM workspaces w JOIN users u ON u.workspace_id=w.id WHERE u.email='hook2@acme.com'").fetchone()["id"]
    evt = {"type": "checkout.session.completed",
           "data": {"object": {"metadata": {"workspace_id": w, "plan": "scale"}}}}
    assert client.post("/api/webhooks/stripe", json=evt).json()["ok"] is True
    assert client.get("/api/usage", headers=h).json()["plan"] == "scale"


def test_webhook_updates_status():
    h = signup("hook@acme.com")
    cid = client.post("/api/campaigns", headers=h, json={"name": "Hook", "script": "Hi {{first_name}}"}).json()["id"]
    client.post(f"/api/campaigns/{cid}/contacts", headers=h, json={"contacts": [
        {"first_name": "Hooked", "mobile": "+1 999 222 3333"}]})
    client.post(f"/api/campaigns/{cid}/send", headers=h, json={})
    conn = sqlite3.connect(os.environ["COLDDROPS_DB"]); conn.row_factory = sqlite3.Row
    fid = conn.execute("SELECT foreign_id FROM drops WHERE campaign_id=?", (cid,)).fetchone()[0]
    body = {"data": {"event_type": "call.hangup", "payload": {
        "client_state": providers._b64(fid), "call_control_id": "cc1"}}}
    # first mark it back to sending so hangup flips it to failed
    conn.execute("UPDATE drops SET status='sending' WHERE foreign_id=?", (fid,)); conn.commit()
    client.post("/api/webhooks/telnyx", json=body)
    assert client.get(f"/api/campaigns/{cid}", headers=h).json()["drop_stats"] == {"failed": 1}
