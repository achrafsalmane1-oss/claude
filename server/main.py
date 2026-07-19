"""Colddrops API server.

Serves the web app and exposes the product API:
  - lead search / mobile enrichment (Moltsets)
  - script merge preview
  - campaign + contact storage (SQLite)
  - send endpoint (stubbed until voice/delivery providers are configured)

Run:  MOLTSETS_API_KEY=ms_xxx uvicorn server.main:app --reload
"""
import os
import re
import sqlite3
import time
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

MOLTSETS_BASE = "https://api.moltsets.com/api/v1/tools"
MOLTSETS_KEY = os.environ.get("MOLTSETS_API_KEY", "")
DB_PATH = Path(os.environ.get("COLDDROPS_DB", Path(__file__).parent / "colddrops.db"))
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Colddrops API", version="0.1.0")
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
            """
        )


init_db()


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
                "company_domain": (company.get("website_url") or "").replace("https://", "").replace("http://", "").strip("/") or None,
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


class ScriptPreview(BaseModel):
    script: str
    contact: dict = {}


@app.post("/api/script/preview")
def script_preview(body: ScriptPreview):
    missing: set[str] = set()

    def sub(m: re.Match) -> str:
        key = m.group(1)
        val = body.contact.get(key)
        if val in (None, ""):
            missing.add(key)
            return f"[{key}]"
        return str(val)

    return {"text": VAR_RE.sub(sub, body.script), "missing": sorted(missing)}


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
            SELECT c.*, COUNT(ct.id) AS contact_count
            FROM campaigns c LEFT JOIN contacts ct ON ct.campaign_id = c.id
            GROUP BY c.id ORDER BY c.created_at DESC
            """
        ).fetchall()
        return {"campaigns": [dict(r) for r in rows]}


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


@app.post("/api/campaigns/{campaign_id}/send")
def send_campaign(campaign_id: int):
    missing = [
        k for k in ("ELEVENLABS_API_KEY", "DROPCOWBOY_TEAM_ID", "DROPCOWBOY_SECRET")
        if not os.environ.get(k)
    ]
    raise HTTPException(
        501,
        "Sending is not enabled yet. Configure the voice + delivery providers first: "
        + ", ".join(missing),
    )


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "moltsets_configured": bool(MOLTSETS_KEY),
        "delivery_configured": bool(os.environ.get("DROPCOWBOY_SECRET")),
        "voice_configured": bool(os.environ.get("ELEVENLABS_API_KEY")),
    }


# static app is mounted last so /api keeps priority
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
