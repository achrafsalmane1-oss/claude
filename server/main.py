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
import secrets
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

from . import auth, billing, notifications, providers, sms

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
            CREATE TABLE IF NOT EXISTS audiences (
              id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
              name TEXT NOT NULL, contacts TEXT NOT NULL DEFAULT '[]', created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_keys (
              key TEXT PRIMARY KEY, workspace_id INTEGER NOT NULL,
              name TEXT, created_at REAL NOT NULL, last_used REAL
            );
            CREATE TABLE IF NOT EXISTS notifications (
              id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
              kind TEXT NOT NULL, title TEXT, body TEXT,
              email_to TEXT, delivered INTEGER NOT NULL DEFAULT 0,
              read INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS otps (
              workspace_id INTEGER PRIMARY KEY, phone TEXT NOT NULL,
              code TEXT NOT NULL, expires_at REAL NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL
            );
            """
        )
        # lightweight migrations (safe to re-run)
        for stmt in ("ALTER TABLE campaigns ADD COLUMN variants TEXT",
                     "ALTER TABLE campaigns ADD COLUMN scheduled_at REAL",
                     "ALTER TABLE campaigns ADD COLUMN window_start INTEGER",
                     "ALTER TABLE campaigns ADD COLUMN window_end INTEGER",
                     "ALTER TABLE campaigns ADD COLUMN tz_offset_min INTEGER NOT NULL DEFAULT 0",
                     "ALTER TABLE contacts ADD COLUMN variant INTEGER NOT NULL DEFAULT 0",
                     "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'member'",
                     "ALTER TABLE workspaces ADD COLUMN phone TEXT",
                     "ALTER TABLE workspaces ADD COLUMN phone_verified INTEGER NOT NULL DEFAULT 0",
                     "ALTER TABLE workspaces ADD COLUMN onboarded INTEGER NOT NULL DEFAULT 0"):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
        # backfill: the earliest user in each workspace is the owner
        try:
            conn.execute("UPDATE users SET role='owner' WHERE id IN "
                         "(SELECT MIN(id) FROM users GROUP BY workspace_id)")
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
        try:
            self.role = user["role"]
        except Exception:
            self.role = "owner"  # API-key context has full access


def get_ctx(authorization: str = Header(default=""),
            x_api_key: str = Header(default="")) -> Ctx:
    # API key (for customers' programmatic access) takes priority
    if x_api_key:
        with db() as conn:
            k = conn.execute("SELECT * FROM api_keys WHERE key=?", (x_api_key,)).fetchone()
            if not k:
                raise HTTPException(401, "invalid API key")
            conn.execute("UPDATE api_keys SET last_used=? WHERE key=?", (time.time(), x_api_key))
            ws = conn.execute("SELECT * FROM workspaces WHERE id=?", (k["workspace_id"],)).fetchone()
            user = conn.execute("SELECT * FROM users WHERE workspace_id=? ORDER BY id LIMIT 1", (k["workspace_id"],)).fetchone()
        return Ctx(user or {"email": "api@key"}, ws)
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


def require_owner(ctx: Ctx = Depends(get_ctx)) -> Ctx:
    if ctx.role != "owner":
        raise HTTPException(403, "owner permission required for this action")
    return ctx


def notify_workspace(wid: int, kind: str, title: str, body: str) -> None:
    """Record a workspace notification and email members (SMTP if configured, else stub)."""
    with db() as conn:
        emails = [r["email"] for r in conn.execute("SELECT email FROM users WHERE workspace_id=?", (wid,))]
        to = ",".join(emails)
        delivered = notifications.send_email(emails, title, body)
        conn.execute(
            "INSERT INTO notifications (workspace_id, kind, title, body, email_to, delivered, created_at) VALUES (?,?,?,?,?,?,?)",
            (wid, kind, title, body, to, 1 if delivered else 0, time.time()))


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
        role = "member" if invite else "owner"
        uid = conn.execute(
            "INSERT INTO users (email, pw_hash, workspace_id, role, created_at) VALUES (?,?,?,?,?)",
            (body.email, auth.hash_password(body.password), wid, role, time.time()),
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


# ---------- phone verification (onboarding) ----------

OTP_TTL = 10 * 60  # codes valid for 10 minutes


def _gen_code() -> str:
    # 6-digit numeric, unbiased, no leading-zero worries (kept as string)
    return f"{secrets.randbelow(1_000_000):06d}"


def _e164(raw: str) -> str:
    """Normalize to +digits E.164-ish. Assumes US (+1) for 10-digit input."""
    digits = re.sub(r"\D", "", raw or "")
    if raw and raw.strip().startswith("+"):
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits if digits else ""


class OtpRequestIn(BaseModel):
    phone: str


@app.post("/api/auth/request-otp")
def request_otp(body: OtpRequestIn, ctx: Ctx = Depends(get_ctx)):
    phone = _e164(body.phone)
    if len(re.sub(r"\D", "", phone)) < 10:
        raise HTTPException(422, "Enter a valid mobile number.")
    code = _gen_code()
    now = time.time()
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO otps (workspace_id, phone, code, expires_at, attempts, created_at) "
            "VALUES (?,?,?,?,0,?)",
            (ctx.wid, phone, code, now + OTP_TTL, now),
        )
    result = sms.send_sms(phone, f"Your Colddrops verification code is {code}")
    resp = {"phone": phone, "sent": result.get("sent", False), "channel": result["backend"]}
    # In dev backend (no paid number yet) surface the code so the flow works end-to-end.
    if result["backend"] == "dev":
        resp["dev_code"] = code
        resp["dev_note"] = "SMS provider not configured — showing the code here so you can finish."
    return resp


class OtpVerifyIn(BaseModel):
    code: str


@app.post("/api/auth/verify-otp")
def verify_otp(body: OtpVerifyIn, ctx: Ctx = Depends(get_ctx)):
    code = re.sub(r"\D", "", body.code or "")
    with db() as conn:
        row = conn.execute("SELECT * FROM otps WHERE workspace_id=?", (ctx.wid,)).fetchone()
        if not row:
            raise HTTPException(400, "Request a code first.")
        if row["attempts"] >= 6:
            raise HTTPException(429, "Too many attempts. Request a new code.")
        if time.time() > row["expires_at"]:
            raise HTTPException(400, "That code expired. Request a new one.")
        if code != row["code"]:
            conn.execute("UPDATE otps SET attempts=attempts+1 WHERE workspace_id=?", (ctx.wid,))
            raise HTTPException(400, "That code isn't right. Try again.")
        conn.execute("UPDATE workspaces SET phone=?, phone_verified=1 WHERE id=?", (row["phone"], ctx.wid))
        conn.execute("DELETE FROM otps WHERE workspace_id=?", (ctx.wid,))
    return {"phone": row["phone"], "phone_verified": True}


class OnboardIn(BaseModel):
    goal: str | None = None


@app.post("/api/onboarding/complete")
def onboarding_complete(body: OnboardIn = OnboardIn(), ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        conn.execute("UPDATE workspaces SET onboarded=1 WHERE id=?", (ctx.wid,))
    return {"onboarded": True}


def usage_for(wid: int) -> dict:
    with db() as conn:
        ws = conn.execute("SELECT * FROM workspaces WHERE id=?", (wid,)).fetchone()
        used = conn.execute(
            "SELECT COUNT(*) FROM drops WHERE workspace_id=? AND created_at>=?",
            (wid, auth.month_start()),
        ).fetchone()[0]
    cap = auth.PLAN_CAPS.get(ws["plan"], 0)
    return {"plan": ws["plan"], "cap": cap, "used": used, "remaining": max(0, cap - used)}


def _ws_col(ws, name, default=None):
    try:
        return ws[name]
    except (IndexError, KeyError):
        return default


@app.get("/api/auth/me")
def me(ctx: Ctx = Depends(get_ctx)):
    ws = ctx.workspace
    return {
        "email": ctx.user["email"],
        "workspace": ws["name"],
        "role": ctx.role,
        "phone": _ws_col(ws, "phone"),
        "phone_verified": bool(_ws_col(ws, "phone_verified", 0)),
        "onboarded": bool(_ws_col(ws, "onboarded", 0)),
        "usage": usage_for(ctx.wid),
    }


@app.get("/api/usage")
def usage(ctx: Ctx = Depends(get_ctx)):
    return usage_for(ctx.wid)


# ---------- team ----------

class InviteIn(BaseModel):
    email: EmailStr


@app.post("/api/team/invite")
def team_invite(body: InviteIn, ctx: Ctx = Depends(require_owner)):
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
            "SELECT email, role, created_at FROM users WHERE workspace_id=? ORDER BY created_at", (ctx.wid,)).fetchall()
        pending = conn.execute(
            "SELECT email, created_at FROM invites WHERE workspace_id=? AND accepted_at IS NULL ORDER BY created_at",
            (ctx.wid,)).fetchall()
    return {"members": [dict(m) for m in members], "pending": [dict(p) for p in pending]}


@app.get("/api/analytics")
def analytics(days: int = 14, ctx: Ctx = Depends(get_ctx)):
    days = max(7, min(90, days))
    import datetime as dt
    cutoff = time.time() - days * 86400
    with db() as conn:
        drops_sent = conn.execute("SELECT COUNT(*) FROM drops WHERE workspace_id=?", (ctx.wid,)).fetchone()[0]
        delivered = conn.execute("SELECT COUNT(*) FROM drops WHERE workspace_id=? AND status='delivered'", (ctx.wid,)).fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM drops WHERE workspace_id=? AND status='failed'", (ctx.wid,)).fetchone()[0]
        callbacks = conn.execute(
            "SELECT COUNT(*) FROM contacts ct JOIN campaigns c ON c.id=ct.campaign_id "
            "WHERE c.workspace_id=? AND ct.status='called_back'", (ctx.wid,)).fetchone()[0]
        rows = conn.execute(
            "SELECT CAST(created_at AS INT)/86400 AS day, COUNT(*) n, "
            "SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) d "
            "FROM drops WHERE workspace_id=? AND created_at>=? GROUP BY day", (ctx.wid, cutoff)).fetchall()
        by_camp = conn.execute(
            """SELECT c.id, c.name,
                      COUNT(ct.id) contacts,
                      SUM(CASE WHEN ct.status IN ('delivered','called_back') THEN 1 ELSE 0 END) delivered,
                      SUM(CASE WHEN ct.status='called_back' THEN 1 ELSE 0 END) callbacks
               FROM campaigns c LEFT JOIN contacts ct ON ct.campaign_id=c.id
               WHERE c.workspace_id=? GROUP BY c.id ORDER BY c.created_at DESC LIMIT 12""",
            (ctx.wid,)).fetchall()
    # dense daily series (fill gaps with 0)
    by_day = {r["day"]: r for r in rows}
    today = int(time.time()) // 86400
    series = []
    for d in range(today - days + 1, today + 1):
        r = by_day.get(d)
        series.append({
            "date": dt.datetime.utcfromtimestamp(d * 86400).strftime("%b %d"),
            "sent": (r["n"] if r else 0) or 0,
            "delivered": (r["d"] if r else 0) or 0,
        })
    campaigns = []
    for r in by_camp:
        dv = (r["delivered"] or 0)
        cb = (r["callbacks"] or 0)
        campaigns.append({"id": r["id"], "name": r["name"], "contacts": r["contacts"] or 0,
                          "delivered": dv, "callbacks": cb,
                          "callback_rate": round(cb / dv, 3) if dv else 0.0})
    return {
        "totals": {"drops_sent": drops_sent, "delivered": delivered, "failed": failed,
                   "callbacks": callbacks,
                   "delivery_rate": round(delivered / drops_sent, 3) if drops_sent else 0.0,
                   "callback_rate": round(callbacks / delivered, 3) if delivered else 0.0},
        "series": series,
        "campaigns": campaigns,
    }


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
def billing_checkout(body: CheckoutIn, ctx: Ctx = Depends(require_owner)):
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


def valid_mobile(raw: str | None) -> bool:
    """A droppable mobile: 8–15 digits (E.164-ish). Empty is allowed (staged w/o number)."""
    d = norm_phone(raw)
    return d == "" or 8 <= len(d) <= 15


@app.post("/api/campaigns/{campaign_id}/contacts")
def add_contacts(campaign_id: int, body: ContactsIn, ctx: Ctx = Depends(get_ctx)):
    added = invalid = duplicate = 0
    with db() as conn:
        _owned_campaign(conn, campaign_id, ctx.wid)
        seen = {norm_phone(r["mobile"]) for r in conn.execute(
            "SELECT mobile FROM contacts WHERE campaign_id=? AND mobile IS NOT NULL", (campaign_id,))
            if norm_phone(r["mobile"])}
        for c in body.contacts:
            mob = norm_phone(c.get("mobile"))
            if c.get("mobile") and not valid_mobile(c.get("mobile")):
                invalid += 1
                continue
            if mob and mob in seen:  # dedupe within the campaign by mobile
                duplicate += 1
                continue
            if mob:
                seen.add(mob)
            conn.execute(
                """INSERT INTO contacts (campaign_id, first_name, last_name, company, title,
                     country, email, linkedin_url, mobile, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (campaign_id, c.get("first_name"), c.get("last_name"), c.get("company"),
                 c.get("title"), c.get("country"), c.get("email"), c.get("linkedin_url"),
                 c.get("mobile"), time.time()),
            )
            added += 1
        n = conn.execute("SELECT COUNT(*) FROM contacts WHERE campaign_id=?", (campaign_id,)).fetchone()[0]
    return {"campaign_id": campaign_id, "contact_count": n,
            "added": added, "skipped_duplicate": duplicate, "skipped_invalid": invalid}


@app.post("/api/contacts/{contact_id}/callback")
def mark_callback(contact_id: int, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        row = conn.execute(
            """SELECT ct.id, ct.first_name, ct.last_name, ct.company, ct.mobile
               FROM contacts ct JOIN campaigns c ON c.id=ct.campaign_id
               WHERE ct.id=? AND c.workspace_id=?""", (contact_id, ctx.wid)).fetchone()
        if not row:
            raise HTTPException(404, "contact not found")
        conn.execute("UPDATE contacts SET status='called_back' WHERE id=?", (contact_id,))
    nm = ((row["first_name"] or "") + " " + (row["last_name"] or "")).strip() or "A prospect"
    notify_workspace(ctx.wid, "callback", f"📞 {nm} called back",
                     f"{nm}{(' at ' + row['company']) if row['company'] else ''} just called back "
                     f"({row['mobile'] or 'unknown number'}). Follow up in Colddrops → Callbacks.")
    return {"contact_id": contact_id, "status": "called_back"}


# ---------- notifications ----------

@app.get("/api/notifications")
def list_notifications(ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, kind, title, body, delivered, read, created_at FROM notifications "
            "WHERE workspace_id=? ORDER BY created_at DESC LIMIT 50", (ctx.wid,)).fetchall()
        unread = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE workspace_id=? AND read=0", (ctx.wid,)).fetchone()[0]
    return {"notifications": [dict(r) for r in rows], "unread": unread,
            "email_configured": notifications.configured()}


@app.post("/api/notifications/read")
def mark_notifications_read(ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        conn.execute("UPDATE notifications SET read=1 WHERE workspace_id=?", (ctx.wid,))
    return {"ok": True}


# ---------- saved audiences ----------

class AudienceIn(BaseModel):
    name: str
    contacts: list[dict] = Field(..., min_length=1)


@app.post("/api/audiences")
def create_audience(body: AudienceIn, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO audiences (workspace_id, name, contacts, created_at) VALUES (?,?,?,?)",
            (ctx.wid, body.name, json.dumps(body.contacts), time.time()))
    return {"id": cur.lastrowid, "name": body.name, "count": len(body.contacts)}


@app.get("/api/audiences")
def list_audiences(ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, name, contacts, created_at FROM audiences WHERE workspace_id=? ORDER BY created_at DESC",
            (ctx.wid,)).fetchall()
    return {"audiences": [
        {"id": r["id"], "name": r["name"], "count": len(json.loads(r["contacts"])), "created_at": r["created_at"]}
        for r in rows]}


@app.get("/api/audiences/{audience_id}/contacts")
def audience_contacts(audience_id: int, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        a = conn.execute("SELECT * FROM audiences WHERE id=? AND workspace_id=?", (audience_id, ctx.wid)).fetchone()
        if not a:
            raise HTTPException(404, "audience not found")
    return {"id": audience_id, "name": a["name"], "contacts": json.loads(a["contacts"])}


@app.post("/api/campaigns/{campaign_id}/contacts/from_audience")
def add_from_audience(campaign_id: int, audience_id: int, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        _owned_campaign(conn, campaign_id, ctx.wid)
        a = conn.execute("SELECT * FROM audiences WHERE id=? AND workspace_id=?", (audience_id, ctx.wid)).fetchone()
        if not a:
            raise HTTPException(404, "audience not found")
        contacts = json.loads(a["contacts"])
        for c in contacts:
            conn.execute(
                """INSERT INTO contacts (campaign_id, first_name, last_name, company, title,
                     country, email, linkedin_url, mobile, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (campaign_id, c.get("first_name"), c.get("last_name"), c.get("company"),
                 c.get("title"), c.get("country"), c.get("email"), c.get("linkedin_url"),
                 c.get("mobile"), time.time()))
    return {"campaign_id": campaign_id, "added": len(contacts)}


# ---------- API keys (public API) ----------

class ApiKeyIn(BaseModel):
    name: str | None = None


@app.post("/api/keys")
def create_api_key(body: ApiKeyIn, ctx: Ctx = Depends(require_owner)):
    key = "cd_live_" + auth.new_token()[:32]
    with db() as conn:
        conn.execute("INSERT INTO api_keys (key, workspace_id, name, created_at) VALUES (?,?,?,?)",
                     (key, ctx.wid, body.name or "API key", time.time()))
    return {"key": key, "name": body.name or "API key"}


@app.get("/api/keys")
def list_api_keys(ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        rows = conn.execute(
            "SELECT key, name, created_at, last_used FROM api_keys WHERE workspace_id=? ORDER BY created_at DESC",
            (ctx.wid,)).fetchall()
    # mask all but the last 4 chars
    return {"keys": [{"key": "cd_live_…" + r["key"][-4:], "name": r["name"],
                      "created_at": r["created_at"], "last_used": r["last_used"]} for r in rows]}


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


def _queue_campaign(campaign_id: int, wid: int) -> dict:
    """Queue drops for a campaign's pending contacts. Returns counts + drop ids."""
    u = usage_for(wid)
    with db() as conn:
        camp = conn.execute("SELECT * FROM campaigns WHERE id=? AND workspace_id=?", (campaign_id, wid)).fetchone()
        if not camp:
            raise HTTPException(404, "campaign not found")
        if not camp["script"].strip():
            raise HTTPException(422, "campaign script is empty")
        suppressed = {r["phone"] for r in conn.execute("SELECT phone FROM suppressions WHERE workspace_id=?", (wid,))}
        contacts = conn.execute("SELECT * FROM contacts WHERE campaign_id=? AND status='queued'", (campaign_id,)).fetchall()
        try:
            nvariants = max(1, len(json.loads(camp["variants"]))) if camp["variants"] else 1
        except Exception:
            nvariants = 1
        queued, no_mobile, skipped_dnc = [], 0, 0
        for ct in contacts:
            if len(queued) >= u["remaining"]:
                break
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
                "INSERT INTO drops (foreign_id, workspace_id, campaign_id, contact_id, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (fid, wid, campaign_id, ct["id"], time.time(), time.time()))
            queued.append(cur.lastrowid)
        conn.execute("UPDATE campaigns SET status='sending', scheduled_at=NULL WHERE id=?", (campaign_id,))
    droppable = len([c for c in contacts if norm_phone(c["mobile"]) and norm_phone(c["mobile"]) not in suppressed])
    return {"queued": queued, "skipped_no_mobile": no_mobile,
            "skipped_suppressed": skipped_dnc, "hit_plan_cap": droppable > len(queued)}


@app.post("/api/campaigns/{campaign_id}/send")
def send_campaign(campaign_id: int, background: BackgroundTasks,
                  body: SendIn | None = None, ctx: Ctx = Depends(get_ctx)):
    live_ready = providers.voice_live() and providers.delivery_live()
    dry = body.dry_run if body and body.dry_run is not None else not live_ready
    if not dry and not live_ready:
        missing = [k for k in ("ELEVENLABS_API_KEY", "TELNYX_API_KEY", "TELNYX_CONNECTION_ID",
                               "TELNYX_FROM_NUMBER") if not os.environ.get(k)]
        raise HTTPException(400, "Live send needs: " + ", ".join(missing) + '. Or pass {"dry_run": true}.')
    r = _queue_campaign(campaign_id, ctx.wid)
    for drop_id in r["queued"]:
        background.add_task(process_drop, drop_id)
    return {"campaign_id": campaign_id,
            "mode": "live" if (not dry and live_ready) else "dry_run",
            "queued": len(r["queued"]), "skipped_no_mobile": r["skipped_no_mobile"],
            "skipped_suppressed": r["skipped_suppressed"], "hit_plan_cap": r["hit_plan_cap"],
            "usage": usage_for(ctx.wid)}


class ScheduleIn(BaseModel):
    at: float  # unix timestamp
    window_start: int | None = Field(None, ge=0, le=23)   # local hour drops may start
    window_end: int | None = Field(None, ge=1, le=24)     # local hour drops must stop
    tz_offset_min: int = 0                                 # minutes from UTC (recipient/campaign tz)


@app.post("/api/campaigns/{campaign_id}/schedule")
def schedule_campaign(campaign_id: int, body: ScheduleIn, ctx: Ctx = Depends(get_ctx)):
    with db() as conn:
        _owned_campaign(conn, campaign_id, ctx.wid)
        conn.execute(
            "UPDATE campaigns SET status='scheduled', scheduled_at=?, window_start=?, window_end=?, tz_offset_min=? WHERE id=?",
            (body.at, body.window_start, body.window_end, body.tz_offset_min, campaign_id))
    return {"campaign_id": campaign_id, "status": "scheduled", "scheduled_at": body.at,
            "window": [body.window_start, body.window_end], "tz_offset_min": body.tz_offset_min}


def in_send_window(camp, now: float | None = None) -> bool:
    """True if a campaign may send right now, given its quiet-hours window (if any)."""
    ws, we = camp["window_start"], camp["window_end"]
    if ws is None or we is None:
        return True
    local = (now or time.time()) + (camp["tz_offset_min"] or 0) * 60
    hour = int(time.gmtime(local).tm_hour)
    return ws <= hour < we if ws < we else (hour >= ws or hour < we)


def process_scheduled() -> int:
    """Send scheduled campaigns whose time has arrived AND that are inside their send window."""
    now = time.time()
    with db() as conn:
        due = conn.execute(
            "SELECT * FROM campaigns WHERE status='scheduled' AND scheduled_at IS NOT NULL AND scheduled_at<=?",
            (now,)).fetchall()
    sent = 0
    for c in due:
        if not in_send_window(c, now):
            continue  # outside quiet-hours window — try again next tick
        try:
            r = _queue_campaign(c["id"], c["workspace_id"])
            for drop_id in r["queued"]:
                process_drop(drop_id)
            sent += 1
        except Exception:
            pass
    return sent


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


@app.on_event("startup")
async def _start_scheduler():
    import asyncio

    async def loop():
        while True:
            await asyncio.sleep(30)
            try:
                process_scheduled()
            except Exception:
                pass

    asyncio.create_task(loop())


app.mount("/audio", StaticFiles(directory=providers.AUDIO_DIR), name="audio")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
