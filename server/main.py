"""Colddrops API server.

Serves the web app and the product API:
  - lead search / mobile enrichment (Moltsets)
  - script merge preview
  - campaigns + contacts (SQLite)
  - the send pipeline: merge -> voice render -> RVM drop -> webhook status,
    with DNC/opt-out suppression. Works end-to-end in dry-run mode until the
    voice + delivery providers are configured.

Run:  MOLTSETS_API_KEY=ms_xxx uvicorn server.main:app --reload
"""
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path

import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import providers

MOLTSETS_BASE = "https://api.moltsets.com/api/v1/tools"
MOLTSETS_KEY = os.environ.get("MOLTSETS_API_KEY", "")
DB_PATH = Path(os.environ.get("COLDDROPS_DB", Path(__file__).parent / "colddrops.db"))
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Colddrops API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ---------- storage ----------

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS campaigns (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              script TEXT NOT NULL DEFAULT '',
              voice TEXT NOT NULL DEFAULT 'ava',
              status TEXT NOT NULL DEFAULT 'draft',
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contacts (
              id INTEGER PRIMARY KEY,
              campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
              first_name TEXT, last_name TEXT, company TEXT,
              title TEXT, country TEXT, email TEXT,
              linkedin_url TEXT, mobile TEXT,
              status TEXT NOT NULL DEFAULT 'queued',
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS drops (
              id INTEGER PRIMARY KEY,
              foreign_id TEXT UNIQUE NOT NULL,
              campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
              contact_id INTEGER NOT NULL REFERENCES contacts(id),
              audio_path TEXT, provider_id TEXT,
              status TEXT NOT NULL DEFAULT 'queued',
              error TEXT,
              created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS suppressions (
              phone TEXT PRIMARY KEY,
              reason TEXT NOT NULL DEFAULT 'opt_out',
              created_at REAL NOT NULL
            );
            """
        )


init_db()


def norm_phone(raw: str | None) -> str:
    return re.sub(r"\D", "", raw or "")


# ---------- moltsets ----------

def moltsets(path: str, payload: dict) -> dict:
    if not MOLTSETS_KEY:
        raise HTTPException(503, "MOLTSETS_API_KEY is not configured on the server")
    r = requests.post(
        f"{MOLTSETS_BASE}/{path}",
        json=payload,
        headers={"Authorization": f"Bearer {MOLTSETS_KEY}"},
        timeout=60,
    )
    if r.status_code == 404:  # not_found responses use 404 with a JSON body
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
def leads_search(body: LeadSearch):
    payload = {k: v for k, v in body.model_dump().items() if v not in (None, "")}
    data = moltsets("search_people", payload)
    results = []
    for p in data.get("results", {}).get("results", []):
        company = p.get("company") or {}
        results.append(
            {
                "full_name": p.get("full_name"),
                "first_name": p.get("first_name"),
                "last_name": p.get("last_name"),
                "title": p.get("title"),
                "company": company.get("name"),
                "company_domain": (company.get("website_url") or "")
                    .replace("https://", "").replace("http://", "").strip("/") or None,
                "country": p.get("country"),
                "email": p.get("business_email"),
                "linkedin_url": p.get("linkedin_url"),
                "linkedin_slug": p.get("linkedin_slug"),
            }
        )
    return {"results": results, "total": data.get("results", {}).get("total", len(results))}


class MobileLookup(BaseModel):
    linkedin_urls: list[str] = Field(..., min_length=1, max_length=100)


@app.post("/api/leads/mobiles")
def leads_mobiles(body: MobileLookup):
    data = moltsets("linkedin_to_mobile_phone", {"linkedin_urls": body.linkedin_urls})
    out = []
    for row in data.get("results", []) if isinstance(data.get("results"), list) else []:
        out.append(
            {
                "linkedin_url": row.get("input"),
                "mobile": (row.get("data") or {}).get("mobile_phone"),
                "validated_at": (row.get("data") or {}).get("last_validated_at"),
                "found": row.get("status") == "ok",
            }
        )
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
def script_preview(body: ScriptPreview):
    text, missing = merge_script(body.script, body.contact)
    return {"text": text, "missing": missing}


# ---------- campaigns ----------

class CampaignIn(BaseModel):
    name: str
    script: str = ""
    voice: str = "ava"


@app.post("/api/campaigns")
def create_campaign(body: CampaignIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO campaigns (name, script, voice, created_at) VALUES (?,?,?,?)",
            (body.name, body.script, body.voice, time.time()),
        )
        return {"id": cur.lastrowid, "name": body.name, "status": "draft"}


@app.get("/api/campaigns")
def list_campaigns():
    with db() as conn:
        rows = conn.execute(
            """
            SELECT c.*, COUNT(ct.id) AS contact_count,
              SUM(CASE WHEN ct.status='delivered' THEN 1 ELSE 0 END) AS delivered_count
            FROM campaigns c LEFT JOIN contacts ct ON ct.campaign_id = c.id
            GROUP BY c.id ORDER BY c.created_at DESC
            """
        ).fetchall()
        return {"campaigns": [dict(r) for r in rows]}


@app.get("/api/campaigns/{campaign_id}")
def campaign_detail(campaign_id: int):
    with db() as conn:
        c = conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
        if not c:
            raise HTTPException(404, "campaign not found")
        contacts = conn.execute(
            "SELECT * FROM contacts WHERE campaign_id=? ORDER BY id", (campaign_id,)
        ).fetchall()
        drops = conn.execute(
            "SELECT status, COUNT(*) n FROM drops WHERE campaign_id=? GROUP BY status",
            (campaign_id,),
        ).fetchall()
        return {
            "campaign": dict(c),
            "contacts": [dict(r) for r in contacts],
            "drop_stats": {r["status"]: r["n"] for r in drops},
        }


class ContactsIn(BaseModel):
    contacts: list[dict] = Field(..., min_length=1)


@app.post("/api/campaigns/{campaign_id}/contacts")
def add_contacts(campaign_id: int, body: ContactsIn):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM campaigns WHERE id=?", (campaign_id,)).fetchone():
            raise HTTPException(404, "campaign not found")
        for c in body.contacts:
            conn.execute(
                """INSERT INTO contacts
                   (campaign_id, first_name, last_name, company, title, country,
                    email, linkedin_url, mobile, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    campaign_id, c.get("first_name"), c.get("last_name"),
                    c.get("company"), c.get("title"), c.get("country"),
                    c.get("email"), c.get("linkedin_url"), c.get("mobile"),
                    time.time(),
                ),
            )
        n = conn.execute(
            "SELECT COUNT(*) FROM contacts WHERE campaign_id=?", (campaign_id,)
        ).fetchone()[0]
    return {"campaign_id": campaign_id, "contact_count": n}


# ---------- suppression (DNC / opt-out) ----------

class SuppressIn(BaseModel):
    phone: str
    reason: str = "opt_out"


@app.post("/api/suppressions")
def add_suppression(body: SuppressIn):
    phone = norm_phone(body.phone)
    if not phone:
        raise HTTPException(422, "invalid phone")
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO suppressions (phone, reason, created_at) VALUES (?,?,?)",
            (phone, body.reason, time.time()),
        )
    return {"phone": phone, "suppressed": True}


@app.get("/api/suppressions")
def list_suppressions():
    with db() as conn:
        rows = conn.execute("SELECT * FROM suppressions ORDER BY created_at DESC").fetchall()
        return {"suppressions": [dict(r) for r in rows]}


# ---------- send pipeline ----------

def process_drop(drop_id: int) -> None:
    """merge -> render voice -> send RVM. Called per drop in the background."""
    with db() as conn:
        row = conn.execute(
            """SELECT d.id, d.foreign_id, c.script, ct.*
               FROM drops d
               JOIN campaigns c ON c.id = d.campaign_id
               JOIN contacts ct ON ct.id = d.contact_id
               WHERE d.id=?""",
            (drop_id,),
        ).fetchone()
    if not row:
        return
    try:
        text, _missing = merge_script(row["script"], dict(row))
        path, url = providers.render_voice(text, row["foreign_id"])
        result = providers.send_rvm(norm_phone(row["mobile"]), url, row["foreign_id"])
        with db() as conn:
            conn.execute(
                "UPDATE drops SET audio_path=?, provider_id=?, status=?, updated_at=? WHERE id=?",
                (str(path.name), result["provider_id"], result["status"], time.time(), drop_id),
            )
            conn.execute(
                "UPDATE contacts SET status=? WHERE id=?", (result["status"], row["id"])
            )
    except Exception as exc:  # keep the batch going; record the failure
        with db() as conn:
            conn.execute(
                "UPDATE drops SET status='failed', error=?, updated_at=? WHERE id=?",
                (str(exc)[:300], time.time(), drop_id),
            )


class SendIn(BaseModel):
    dry_run: bool | None = None  # default: auto (dry-run unless providers configured)


@app.post("/api/campaigns/{campaign_id}/send")
def send_campaign(campaign_id: int, background: BackgroundTasks, body: SendIn | None = None):
    live_ready = providers.voice_live() and providers.delivery_live()
    dry = body.dry_run if body and body.dry_run is not None else not live_ready
    if not dry and not live_ready:
        missing = [
            k for k in ("ELEVENLABS_API_KEY", "DROPCOWBOY_TEAM_ID", "DROPCOWBOY_SECRET")
            if not os.environ.get(k)
        ]
        raise HTTPException(400, "Live send needs: " + ", ".join(missing)
                            + ". Or pass {\"dry_run\": true}.")
    with db() as conn:
        camp = conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
        if not camp:
            raise HTTPException(404, "campaign not found")
        if not camp["script"].strip():
            raise HTTPException(422, "campaign script is empty")
        suppressed = {r["phone"] for r in conn.execute("SELECT phone FROM suppressions")}
        contacts = conn.execute(
            "SELECT * FROM contacts WHERE campaign_id=? AND status='queued'", (campaign_id,)
        ).fetchall()

        queued, no_mobile, skipped_dnc = [], 0, 0
        for ct in contacts:
            phone = norm_phone(ct["mobile"])
            if not phone:
                no_mobile += 1
                continue
            if phone in suppressed:
                skipped_dnc += 1
                conn.execute("UPDATE contacts SET status='suppressed' WHERE id=?", (ct["id"],))
                continue
            fid = f"cd_{campaign_id}_{ct['id']}_{uuid.uuid4().hex[:8]}"
            cur = conn.execute(
                """INSERT INTO drops (foreign_id, campaign_id, contact_id, created_at, updated_at)
                   VALUES (?,?,?,?,?)""",
                (fid, campaign_id, ct["id"], time.time(), time.time()),
            )
            queued.append(cur.lastrowid)
        conn.execute("UPDATE campaigns SET status='sending' WHERE id=?", (campaign_id,))

    for drop_id in queued:
        background.add_task(process_drop, drop_id)
    return {
        "campaign_id": campaign_id,
        "mode": "dry_run" if dry and not live_ready else ("dry_run" if dry else "live"),
        "queued": len(queued),
        "skipped_no_mobile": no_mobile,
        "skipped_suppressed": skipped_dnc,
    }


# ---------- delivery webhooks ----------

@app.post("/api/webhooks/dropcowboy")
async def dropcowboy_webhook(payload: dict):
    fid = payload.get("foreign_id") or payload.get("id")
    status = (payload.get("status") or "").lower()
    mapped = {
        "delivered": "delivered", "success": "delivered", "completed": "delivered",
        "failed": "failed", "error": "failed", "undeliverable": "failed",
    }.get(status, status or "unknown")
    if not fid:
        raise HTTPException(422, "missing foreign_id")
    with db() as conn:
        row = conn.execute("SELECT * FROM drops WHERE foreign_id=?", (fid,)).fetchone()
        if not row:
            raise HTTPException(404, "unknown drop")
        conn.execute(
            "UPDATE drops SET status=?, updated_at=? WHERE id=?",
            (mapped, time.time(), row["id"]),
        )
        conn.execute("UPDATE contacts SET status=? WHERE id=?", (mapped, row["contact_id"]))
    return {"ok": True, "foreign_id": fid, "status": mapped}


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "moltsets_configured": bool(MOLTSETS_KEY),
        "voice_configured": providers.voice_live(),
        "delivery_configured": providers.delivery_live(),
        "mode": "live" if providers.voice_live() and providers.delivery_live() else "dry_run",
    }


# static mounts go last so /api keeps priority
app.mount("/audio", StaticFiles(directory=providers.AUDIO_DIR), name="audio")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
