"""Colddrops API server.

Serves the web app and the product API, now multi-tenant:
  - auth (signup/login/me) + per-workspace data scoping
  - plan + monthly usage metering (Stripe-ready, no Stripe needed yet)
  - lead search / mobile enrichment (Moltsets)
  - script merge, campaigns/contacts, CSV export
  - send pipeline: merge -> voice render -> drop -> webhook, with DNC suppression

Run:  MOLTSETS_API_KEY=ms_xxx uvicorn server.main:app --reload
"""
import io
import csv
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path

import requests
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

from fastapi import Request

from . import auth, billing, providers

MOLTSETS_BASE = "https://api.moltsets.com/api/v1/tools"
MOLTSETS_KEY = os.environ.get("MOLTSETS_API_KEY", "")
DB_PATH = Path(os.environ.get("COLDDROPS_DB", Path(__file__).parent / "colddrops.db"))
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Colddrops API", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------- storage ----------

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
              id INTEGER PRIMARY KEY, name TEXT NOT NULL,
              plan TEXT NOT NULL DEFAULT 'starter', created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id), created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS campaigns (
              id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
              name TEXT NOT NULL, script TEXT NOT NULL DEFAULT '',
              voice TEXT NOT NULL DEFAULT 'ava', status TEXT NOT NULL DEFAULT 'draft',
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contacts (
              id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
              first_name TEXT, last_name TEXT, company TEXT, title TEXT, country TEXT,
              email TEXT, linkedin_url TEXT, mobile TEXT,
              status TEXT NOT NULL DEFAULT 'queued', created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS drops (
              id INTEGER PRIMARY KEY, foreign_id TEXT UNIQUE NOT NULL,
              workspace_id INTEGER NOT NULL, campaign_id INTEGER NOT NULL, contact_id INTEGER NOT NULL,
              audio_path TEXT, provider_id TEXT, status TEXT NOT NULL DEFAULT 'queued',
              error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS suppressions (
              workspace_id INTEGER NOT NULL, phone TEXT NOT NULL,
              reason TEXT NOT NULL DEFAULT 'opt_out', created_at REAL NOT NULL,
              PRIMARY KEY (workspace_id, phone)
            );
            CREATE TABLE IF NOT EXISTS invites (
              token TEXT PRIMARY KEY, workspace_id INTEGER NOT NULL,
              email TEXT NOT NULL, invited_by TEXT, created_at REAL NOT NULL,
              accepted_at REAL
            );
            """
        )
        # lightweight migrations (safe to re-run)
        for stmt in ("ALTER TABLE campaigns ADD COLUMN variants TEXT",
                     "ALTER TABLE contacts ADD COLUMN variant INTEGER NOT NULL DEFAULT 0"):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass


init_db()


def norm_phone(raw: str | None) -> str:
    return re.sub(r"\D", "", raw or "")


# ---------- auth ----------

class Ctx:
    def __init__(self, user, workspace):
        self.user = user
        self.workspace = workspace
        self.wid = workspace["id"]


def get_ctx(authorization: str = Header(default="")) -> Ctx:
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    if not token:
        raise HTTPException(401, "authentication required")
    with db() as conn:
        s = conn.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
        if not s:
            raise HTTPException(401, "invalid or expired session")
        user = conn.execute("SELECT * FROM users WHERE id=?", (s["user_id"],)).fetchone()
        ws = conn.execute("SELECT * FROM workspaces WHERE id=?", (user["workspace_id"],)).fetchone()
    return Ctx(user, ws)


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    workspace_name: str | None = None
    invite_token: str | None = None


@app.post("/api/auth/signup")
def signup(body: SignupIn):
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email=?", (body.email,)).fetchone():
            raise HTTPException(409, "email already registered")
        invite = None
        if body.invite_token:
            invite = conn.execute(
                "SELECT * FROM invites WHERE token=? AND accepted_at IS NULL", (body.invite_token,)
            ).fetchone()
            if not invite:
                raise HTTPException(400, "invite is invalid or already used")
        if invite:  # join the inviting workspace
            wid = invite["workspace_id"]
            ws = conn.execute("SELECT * FROM workspaces WHERE id=?", (wid,)).fetchone()
            wname, plan = ws["name"], ws["plan"]
            conn.execute("UPDATE invites SET accepted_at=? WHERE token=?", (time.time(), body.invite_token))
        else:  # create a new workspace
            wname = body.workspace_name or body.email.split("@")[0].title() + " Workspace"
            plan = auth.DEFAULT_PLAN
            wid = conn.execute(
                "INSERT INTO workspaces (name, plan, created_at) VALUES (?,?,?)",
                (wname, plan, time.time()),
            ).lastrowid
        uid = conn.execute(
            "INSERT INTO users (email, pw_hash, workspace_id, created_at) VALUES (?,?,?,?)",
            (body.email, auth.hash_password(body.password), wid, time.time()),
        ).lastrowid
        token = auth.new_token()
        conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?,?,?)",
                     (token, uid, time.time()))
    return {"token": token, "email": body.email, "workspace": wname, "plan": plan}


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@app.post("/api/auth/login")
def login(body: LoginIn):
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (body.email,)).fetchone()
        if not user or not auth.verify_password(body.password, user["pw_hash"]):
            raise HTTPException(401, "invalid email or password")
        token = auth.new_token()
        conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?,?,?)",
                     (token, user["id"], time.time()))
        ws = conn.execute("SELECT * FROM workspaces WHERE id=?", (user["workspace_id"],)).fetchone()
    return {"token": token, "email": user["email"], "workspace": ws["name"], "plan": ws["plan"]}


@app.post("/api/auth/logout")
def logout(ctx: Ctx = Depends(get_ctx), authorization: str = Header(default="")):
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    return {"ok": True}


def usage_for(wid: int) -> dict:
    with db() as conn:
        ws = conn.execute("SELECT * FROM workspaces WHERE id=?", (wid,)).fetchone()
        used = conn.execute(
            "SELECT COUNT(*) FROM drops WHERE workspace_id=? AND created_at>=?",
            (wid, auth.month_start()),
        ).fetchone()[0]
    cap = auth.PLAN_CAPS.get(ws["plan"], 0)
    return {"plan": ws["plan"], "cap": cap, "used": used, "remaining": max(0, cap - used)}


@app.get("/api/auth/me")
def me(ctx: Ctx = Depends(get_ctx)):
    return {
        "email": ctx.user["email"],
        "workspace": ctx.workspace["name"],
        "usage": usage_for(ctx.wid),
    }


@app.get("/api/usage")
def usage(ctx: Ctx = Depends(get_ctx)):
    return usage_for(ctx.wid)


# ---------- team ----------

class InviteIn(BaseModel):
    email: EmailStr


@app.post("/api/team/invite")
def team_invite(body: InviteIn, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email=? AND workspace_id=?", (body.email, ctx.wid)).fetchone():
            raise HTTPException(409, "already a member")
        token = auth.new_token()
        conn.execute(
            "INSERT INTO invites (token, workspace_id, email, invited_by, created_at) VALUES (?,?,?,?,?)",
            (token, ctx.wid, body.email, ctx.user["email"], time.time()),
        )
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    return {"email": body.email, "invite_token": token,
            "invite_url": f"{base}/login.html?invite={token}"}


@app.get("/api/team")
def team(ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        members = conn.execute(
            "SELECT email, created_at FROM users WHERE workspace_id=? ORDER BY created_at", (ctx.wid,)).fetchall()
        pending = conn.execute(
            "SELECT email, created_at FROM invites WHERE workspace_id=? AND accepted_at IS NULL ORDER BY created_at",
            (ctx.wid,)).fetchall()
    return {"members": [dict(m) for m in members], "pending": [dict(p) for p in pending]}


@app.get("/api/dashboard")
def dashboard(ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        drops_sent = conn.execute("SELECT COUNT(*) FROM drops WHERE workspace_id=?", (ctx.wid,)).fetchone()[0]
        delivered = conn.execute("SELECT COUNT(*) FROM drops WHERE workspace_id=? AND status='delivered'", (ctx.wid,)).fetchone()[0]
        campaigns = conn.execute("SELECT COUNT(*) FROM campaigns WHERE workspace_id=?", (ctx.wid,)).fetchone()[0]
        contacts = conn.execute(
            "SELECT COUNT(*) FROM contacts ct JOIN campaigns c ON c.id=ct.campaign_id WHERE c.workspace_id=?",
            (ctx.wid,)).fetchone()[0]
        callbacks = conn.execute(
            "SELECT COUNT(*) FROM contacts ct JOIN campaigns c ON c.id=ct.campaign_id "
            "WHERE c.workspace_id=? AND ct.status='called_back'", (ctx.wid,)).fetchone()[0]
        latest = conn.execute(
            """SELECT ct.first_name, ct.last_name, ct.company, ct.country, ct.status, ct.mobile
               FROM contacts ct JOIN campaigns c ON c.id=ct.campaign_id
               WHERE c.workspace_id=? AND ct.status IN ('delivered','sent','called_back')
               ORDER BY ct.id DESC LIMIT 5""", (ctx.wid,)).fetchall()
    return {
        "stats": {"drops_sent": drops_sent, "delivered": delivered,
                  "campaigns": campaigns, "contacts": contacts, "callbacks": callbacks},
        "usage": usage_for(ctx.wid),
        "latest": [dict(r) for r in latest],
    }


# ---------- billing ----------

@app.get("/api/billing/plans")
def billing_plans():
    return {"plans": billing.plan_catalog(), "mode": "live" if billing.live() else "stub"}


class CheckoutIn(BaseModel):
    plan: str


@app.post("/api/billing/checkout")
def billing_checkout(body: CheckoutIn, ctx: Ctx = Depends(get_ctx)):
    if body.plan not in billing.PLANS:
        raise HTTPException(422, "unknown plan")
    result = billing.create_checkout(ctx.wid, body.plan, ctx.user["email"])
    if result.get("stub"):  # no Stripe yet: apply the plan immediately
        with db() as conn:
            conn.execute("UPDATE workspaces SET plan=? WHERE id=?", (body.plan, ctx.wid))
    return result


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    raw = await request.body()
    parsed = billing.verify_and_parse_webhook(raw, request.headers.get("stripe-signature", ""))
    if parsed:
        with db() as conn:
            conn.execute("UPDATE workspaces SET plan=? WHERE id=?", (parsed["plan"], parsed["workspace_id"]))
    return {"ok": True}


# ---------- moltsets ----------

def moltsets(path: str, payload: dict) -> dict:
    if not MOLTSETS_KEY:
        raise HTTPException(503, "MOLTSETS_API_KEY is not configured on the server")
    r = requests.post(f"{MOLTSETS_BASE}/{path}", json=payload,
                      headers={"Authorization": f"Bearer {MOLTSETS_KEY}"}, timeout=60)
    if r.status_code == 404:
        try:
            return r.json()
        except ValueError:
            raise HTTPException(502, "Unexpected response from data provider")
    if r.status_code != 200:
        raise HTTPException(502, f"Data provider error ({r.status_code})")
    return r.json()


class LeadSearch(BaseModel):
    query: str = ""
    company: str | None = None
    company_domain: str | None = None
    country: str | None = None
    seniority: str | None = None
    industry: str | None = None
    limit: int = Field(10, ge=1, le=25)
    offset: int = Field(0, ge=0)


@app.post("/api/leads/search")
def leads_search(body: LeadSearch, ctx: Ctx = Depends(get_ctx)):
    payload = {k: v for k, v in body.model_dump().items() if v not in (None, "")}
    data = moltsets("search_people", payload)
    results = []
    for p in data.get("results", {}).get("results", []):
        company = p.get("company") or {}
        results.append({
            "full_name": p.get("full_name"), "first_name": p.get("first_name"),
            "last_name": p.get("last_name"), "title": p.get("title"),
            "company": company.get("name"),
            "company_domain": (company.get("website_url") or "")
                .replace("https://", "").replace("http://", "").strip("/") or None,
            "country": p.get("country"), "email": p.get("business_email"),
            "linkedin_url": p.get("linkedin_url"), "linkedin_slug": p.get("linkedin_slug"),
        })
    return {"results": results, "total": data.get("results", {}).get("total", len(results))}


class MobileLookup(BaseModel):
    linkedin_urls: list[str] = Field(..., min_length=1, max_length=100)


@app.post("/api/leads/mobiles")
def leads_mobiles(body: MobileLookup, ctx: Ctx = Depends(get_ctx)):
    data = moltsets("linkedin_to_mobile_phone", {"linkedin_urls": body.linkedin_urls})
    out = []
    for row in data.get("results", []) if isinstance(data.get("results"), list) else []:
        out.append({
            "linkedin_url": row.get("input"),
            "mobile": (row.get("data") or {}).get("mobile_phone"),
            "validated_at": (row.get("data") or {}).get("last_validated_at"),
            "found": row.get("status") == "ok",
        })
    return {"results": out, "found": sum(1 for r in out if r["found"]), "checked": len(out)}


# ---------- script merge ----------

VAR_RE = re.compile(r"{{\s*(\w+)\s*}}")


def merge_script(script: str, contact: dict) -> tuple[str, list[str]]:
    missing: set[str] = set()

    def sub(m: re.Match) -> str:
        key = m.group(1)
        val = contact.get(key)
        if val in (None, ""):
            missing.add(key)
            return f"[{key}]"
        return str(val)

    return VAR_RE.sub(sub, script), sorted(missing)


class ScriptPreview(BaseModel):
    script: str
    contact: dict = {}


@app.post("/api/script/preview")
def script_preview(body: ScriptPreview, ctx: Ctx = Depends(get_ctx)):
    text, missing = merge_script(body.script, body.contact)
    return {"text": text, "missing": missing}


# ---------- campaigns ----------

class CampaignIn(BaseModel):
    name: str
    script: str = ""
    voice: str = "ava"
    variants: list[str] | None = None  # A/B: extra script variants (script is variant A)


@app.post("/api/campaigns")
def create_campaign(body: CampaignIn, ctx: Ctx = Depends(get_ctx)):
    variants = [body.script] + [v for v in (body.variants or []) if v.strip()]
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO campaigns (workspace_id, name, script, voice, variants, created_at) VALUES (?,?,?,?,?,?)",
            (ctx.wid, body.name, body.script, body.voice, json.dumps(variants), time.time()),
        )
        return {"id": cur.lastrowid, "name": body.name, "status": "draft", "variant_count": len(variants)}


@app.get("/api/campaigns")
def list_campaigns(ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        rows = conn.execute(
            """SELECT c.*, COUNT(ct.id) AS contact_count,
                 SUM(CASE WHEN ct.status='delivered' THEN 1 ELSE 0 END) AS delivered_count
               FROM campaigns c LEFT JOIN contacts ct ON ct.campaign_id=c.id
               WHERE c.workspace_id=? GROUP BY c.id ORDER BY c.created_at DESC""",
            (ctx.wid,),
        ).fetchall()
        return {"campaigns": [dict(r) for r in rows]}


def _owned_campaign(conn, campaign_id: int, wid: int):
    c = conn.execute("SELECT * FROM campaigns WHERE id=? AND workspace_id=?", (campaign_id, wid)).fetchone()
    if not c:
        raise HTTPException(404, "campaign not found")
    return c


@app.get("/api/campaigns/{campaign_id}")
def campaign_detail(campaign_id: int, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        c = _owned_campaign(conn, campaign_id, ctx.wid)
        contacts = conn.execute("SELECT * FROM contacts WHERE campaign_id=? ORDER BY id", (campaign_id,)).fetchall()
        drops = conn.execute("SELECT status, COUNT(*) n FROM drops WHERE campaign_id=? GROUP BY status", (campaign_id,)).fetchall()
    return {"campaign": dict(c), "contacts": [dict(r) for r in contacts],
            "drop_stats": {r["status"]: r["n"] for r in drops}}


class ContactsIn(BaseModel):
    contacts: list[dict] = Field(..., min_length=1)


@app.post("/api/campaigns/{campaign_id}/contacts")
def add_contacts(campaign_id: int, body: ContactsIn, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        _owned_campaign(conn, campaign_id, ctx.wid)
        for c in body.contacts:
            conn.execute(
                """INSERT INTO contacts (campaign_id, first_name, last_name, company, title,
                     country, email, linkedin_url, mobile, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (campaign_id, c.get("first_name"), c.get("last_name"), c.get("company"),
                 c.get("title"), c.get("country"), c.get("email"), c.get("linkedin_url"),
                 c.get("mobile"), time.time()),
            )
        n = conn.execute("SELECT COUNT(*) FROM contacts WHERE campaign_id=?", (campaign_id,)).fetchone()[0]
    return {"campaign_id": campaign_id, "contact_count": n}


@app.post("/api/contacts/{contact_id}/callback")
def mark_callback(contact_id: int, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        row = conn.execute(
            """SELECT ct.id FROM contacts ct JOIN campaigns c ON c.id=ct.campaign_id
               WHERE ct.id=? AND c.workspace_id=?""", (contact_id, ctx.wid)).fetchone()
        if not row:
            raise HTTPException(404, "contact not found")
        conn.execute("UPDATE contacts SET status='called_back' WHERE id=?", (contact_id,))
    return {"contact_id": contact_id, "status": "called_back"}


@app.get("/api/callbacks")
def list_callbacks(ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        rows = conn.execute(
            """SELECT ct.id, ct.first_name, ct.last_name, ct.company, ct.title, ct.country,
                      ct.email, ct.mobile, ct.linkedin_url, c.name AS campaign
               FROM contacts ct JOIN campaigns c ON c.id=ct.campaign_id
               WHERE c.workspace_id=? AND ct.status='called_back'
               ORDER BY ct.id DESC""", (ctx.wid,)).fetchall()
    return {"callbacks": [dict(r) for r in rows], "count": len(rows)}


@app.get("/api/campaigns/{campaign_id}/analytics")
def campaign_analytics(campaign_id: int, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        c = _owned_campaign(conn, campaign_id, ctx.wid)
        try:
            variants = json.loads(c["variants"]) if c["variants"] else [c["script"]]
        except Exception:
            variants = [c["script"]]
        rows = conn.execute(
            """SELECT variant,
                      COUNT(*) AS total,
                      SUM(CASE WHEN status IN ('delivered','called_back') THEN 1 ELSE 0 END) AS delivered,
                      SUM(CASE WHEN status='called_back' THEN 1 ELSE 0 END) AS callbacks
               FROM contacts WHERE campaign_id=? GROUP BY variant""", (campaign_id,)).fetchall()
    by_variant = {r["variant"]: r for r in rows}
    out = []
    for i, script in enumerate(variants):
        r = by_variant.get(i)
        delivered = (r["delivered"] if r else 0) or 0
        callbacks = (r["callbacks"] if r else 0) or 0
        out.append({
            "variant": chr(65 + i),  # A, B, C…
            "script": script,
            "sent": (r["total"] if r else 0) or 0,
            "delivered": delivered,
            "callbacks": callbacks,
            "callback_rate": round(callbacks / delivered, 3) if delivered else 0.0,
        })
    winner = max(out, key=lambda v: v["callback_rate"])["variant"] if any(v["delivered"] for v in out) else None
    return {"campaign": c["name"], "variants": out, "winner": winner}


@app.get("/api/campaigns/{campaign_id}/contacts.csv")
def export_contacts_csv(campaign_id: int, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        c = _owned_campaign(conn, campaign_id, ctx.wid)
        rows = conn.execute("SELECT * FROM contacts WHERE campaign_id=? ORDER BY id", (campaign_id,)).fetchall()
    buf = io.StringIO()
    cols = ["first_name", "last_name", "company", "title", "country", "email", "mobile", "linkedin_url", "status"]
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([r[c] for c in cols])
    fname = re.sub(r"[^a-z0-9]+", "-", c["name"].lower()).strip("-") or "campaign"
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{fname}-contacts.csv"'})


# ---------- suppression ----------

class SuppressIn(BaseModel):
    phone: str
    reason: str = "opt_out"


@app.post("/api/suppressions")
def add_suppression(body: SuppressIn, ctx: Ctx = Depends(get_ctx)):
    phone = norm_phone(body.phone)
    if not phone:
        raise HTTPException(422, "invalid phone")
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO suppressions (workspace_id, phone, reason, created_at) VALUES (?,?,?,?)",
            (ctx.wid, phone, body.reason, time.time()),
        )
    return {"phone": phone, "suppressed": True}


@app.get("/api/suppressions")
def list_suppressions(ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        rows = conn.execute("SELECT phone, reason, created_at FROM suppressions WHERE workspace_id=? ORDER BY created_at DESC", (ctx.wid,)).fetchall()
    return {"suppressions": [dict(r) for r in rows]}


# ---------- send pipeline ----------

def process_drop(drop_id: int) -> None:
    with db() as conn:
        row = conn.execute(
            """SELECT d.id, d.foreign_id, c.script, c.variants, ct.*
               FROM drops d JOIN campaigns c ON c.id=d.campaign_id
               JOIN contacts ct ON ct.id=d.contact_id WHERE d.id=?""",
            (drop_id,),
        ).fetchone()
    if not row:
        return
    try:
        script = row["script"]
        if row["variants"]:
            try:
                vs = json.loads(row["variants"])
                if vs:
                    script = vs[(row["variant"] or 0) % len(vs)]
            except Exception:
                pass
        text, _ = merge_script(script, dict(row))
        voice = providers.render_voice(text, row["foreign_id"])
        result = providers.send_rvm(norm_phone(row["mobile"]), voice["url"], row["foreign_id"])
        with db() as conn:
            conn.execute("UPDATE drops SET audio_path=?, provider_id=?, status=?, updated_at=? WHERE id=?",
                         (voice["path"].name, result["provider_id"], result["status"], time.time(), drop_id))
            conn.execute("UPDATE contacts SET status=? WHERE id=?", (result["status"], row["id"]))
    except Exception as exc:
        with db() as conn:
            conn.execute("UPDATE drops SET status='failed', error=?, updated_at=? WHERE id=?",
                         (str(exc)[:300], time.time(), drop_id))


class SendIn(BaseModel):
    dry_run: bool | None = None


@app.post("/api/campaigns/{campaign_id}/send")
def send_campaign(campaign_id: int, background: BackgroundTasks,
                  body: SendIn | None = None, ctx: Ctx = Depends(get_ctx)):
    live_ready = providers.voice_live() and providers.delivery_live()
    dry = body.dry_run if body and body.dry_run is not None else not live_ready
    if not dry and not live_ready:
        missing = [k for k in ("ELEVENLABS_API_KEY", "TELNYX_API_KEY", "TELNYX_CONNECTION_ID",
                               "TELNYX_FROM_NUMBER") if not os.environ.get(k)]
        raise HTTPException(400, "Live send needs: " + ", ".join(missing) + '. Or pass {"dry_run": true}.')

    u = usage_for(ctx.wid)
    with db() as conn:
        camp = _owned_campaign(conn, campaign_id, ctx.wid)
        if not camp["script"].strip():
            raise HTTPException(422, "campaign script is empty")
        suppressed = {r["phone"] for r in conn.execute("SELECT phone FROM suppressions WHERE workspace_id=?", (ctx.wid,))}
        contacts = conn.execute("SELECT * FROM contacts WHERE campaign_id=? AND status='queued'", (campaign_id,)).fetchall()

        try:
            nvariants = max(1, len(json.loads(camp["variants"]))) if camp["variants"] else 1
        except Exception:
            nvariants = 1
        queued, no_mobile, skipped_dnc = [], 0, 0
        for ct in contacts:
            if len(queued) >= u["remaining"]:
                break  # respect the plan's monthly cap
            phone = norm_phone(ct["mobile"])
            if not phone:
                no_mobile += 1
                continue
            if phone in suppressed:
                skipped_dnc += 1
                conn.execute("UPDATE contacts SET status='suppressed' WHERE id=?", (ct["id"],))
                continue
            conn.execute("UPDATE contacts SET variant=? WHERE id=?", (len(queued) % nvariants, ct["id"]))
            fid = f"cd_{campaign_id}_{ct['id']}_{uuid.uuid4().hex[:8]}"
            cur = conn.execute(
                """INSERT INTO drops (foreign_id, workspace_id, campaign_id, contact_id, created_at, updated_at)
                   VALUES (?,?,?,?,?,?)""",
                (fid, ctx.wid, campaign_id, ct["id"], time.time(), time.time()),
            )
            queued.append(cur.lastrowid)
        conn.execute("UPDATE campaigns SET status='sending' WHERE id=?", (campaign_id,))

    for drop_id in queued:
        background.add_task(process_drop, drop_id)
    capped = len([c for c in contacts if norm_phone(c["mobile"]) and norm_phone(c["mobile"]) not in suppressed]) > len(queued)
    return {"campaign_id": campaign_id,
            "mode": "live" if (not dry and live_ready) else "dry_run",
            "queued": len(queued), "skipped_no_mobile": no_mobile,
            "skipped_suppressed": skipped_dnc, "hit_plan_cap": capped,
            "usage": usage_for(ctx.wid)}


# ---------- delivery webhook ----------

@app.post("/api/webhooks/telnyx")
async def telnyx_webhook(payload: dict):
    data = (payload.get("data") or {})
    event = data.get("event_type", "")
    p = data.get("payload", {})
    ccid = p.get("call_control_id")
    fid = providers.decode_client_state(p.get("client_state"))

    def set_status(status: str):
        if not fid:
            return
        with db() as conn:
            row = conn.execute("SELECT * FROM drops WHERE foreign_id=?", (fid,)).fetchone()
            if row:
                conn.execute("UPDATE drops SET status=?, updated_at=? WHERE id=?", (status, time.time(), row["id"]))
                conn.execute("UPDATE contacts SET status=? WHERE id=?", (status, row["contact_id"]))

    # inbound: a prospect calling the number back -> log a callback
    if event == "call.initiated" and p.get("direction") in ("incoming", "inbound"):
        caller = norm_phone(p.get("from"))
        if caller:
            with db() as conn:
                row = conn.execute(
                    """SELECT ct.id FROM contacts ct JOIN campaigns c ON c.id=ct.campaign_id
                       WHERE REPLACE(REPLACE(REPLACE(REPLACE(ct.mobile,'+',''),'-',''),' ',''),'(','') LIKE ?
                       ORDER BY ct.id DESC LIMIT 1""", ("%" + caller[-10:],)).fetchone()
                if row:
                    conn.execute("UPDATE contacts SET status='called_back' WHERE id=?", (row["id"],))
        return {"ok": True, "handled": "inbound_callback"}

    if event in ("call.machine.detection.ended", "call.machine.premium.detection.ended"):
        if p.get("result", "") in ("machine", "detected"):
            audio = next((h.get("value", "") for h in (p.get("custom_headers") or [])
                          if h.get("name") == "X-Colddrops-Audio"), "")
            if ccid and audio and providers.TELNYX_KEY:
                requests.post(f"https://api.telnyx.com/v2/calls/{ccid}/actions/playback_start",
                              headers={"Authorization": f"Bearer {providers.TELNYX_KEY}"},
                              json={"audio_url": audio}, timeout=30)
            set_status("delivered")
        else:
            if ccid and providers.TELNYX_KEY:
                requests.post(f"https://api.telnyx.com/v2/calls/{ccid}/actions/hangup",
                              headers={"Authorization": f"Bearer {providers.TELNYX_KEY}"}, timeout=30)
            set_status("skipped_human")
    elif event == "call.playback.ended":
        if ccid and providers.TELNYX_KEY:
            requests.post(f"https://api.telnyx.com/v2/calls/{ccid}/actions/hangup",
                          headers={"Authorization": f"Bearer {providers.TELNYX_KEY}"}, timeout=30)
    elif event == "call.hangup":
        with db() as conn:
            row = conn.execute("SELECT status FROM drops WHERE foreign_id=?", (fid,)).fetchone()
        if row and row["status"] in ("queued", "sending"):
            set_status("failed")
    return {"ok": True}


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "moltsets_configured": bool(MOLTSETS_KEY),
        "voice_backend": providers.active_voice_backend(),
        "voice_real": providers.voice_live(),
        "delivery_backend": providers.active_delivery_backend(),
        "delivery_live": providers.delivery_live(),
        "mode": "live" if providers.voice_live() and providers.delivery_live() else "dry_run",
    }


app.mount("/audio", StaticFiles(directory=providers.AUDIO_DIR), name="audio")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
