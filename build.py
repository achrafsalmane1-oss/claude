#!/usr/bin/env python3
"""
Franklin campaign dashboard — data builder
==========================================
Pulls campaign performance from the Email Bison API and writes a *curated*
data file (``site/data.js``) that the static dashboard reads.

What ends up in the published file is deliberately limited to the metrics the
client should see:

    * total emails sent to date
    * emails sent per day
    * total replies (and replies per day)
    * campaign names + status

Deliverability noise (bounces, unsubscribes, per-step internals) is fetched
from the API but never written to the output file, so it can never reach the
browser. The API key is read from the environment and is likewise never
written to the output.

Usage:
    EMAIL_BISON_API_KEY=xxx python3 build.py
"""

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.getenv("EMAIL_BISON_API_KEY", "").strip()
BASE_URL = os.getenv(
    "EMAIL_BISON_BASE_URL", "https://send.breakoutcreatives.com/api"
).rstrip("/")

# The client this dashboard is for. Only used for display.
CLIENT_NAME = os.getenv("CLIENT_NAME", "Franklin")

OUTPUT_PATH = Path(__file__).parent / "site" / "data.js"

session = requests.Session()
session.headers.update(
    {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
)


# ---------------------------------------------------------------------------
# HTTP helpers (with retry + exponential backoff)
# ---------------------------------------------------------------------------
def _request(method: str, path: str, **kwargs) -> dict:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    last_err = None
    for attempt in range(5):
        try:
            resp = session.request(method, url, timeout=30, **kwargs)
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"  Rate limited on {path}, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_err = exc
            wait = 2 ** attempt
            print(f"  Request error on {path} ({exc}); retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"Failed request {method} {path}: {last_err}")


def get_campaigns() -> list[dict]:
    """Return all campaigns visible to this API key (already Franklin-scoped)."""
    data = _request("GET", "campaigns?per_page=100").get("data", [])
    # Newest first for display; oldest first is handled where it matters.
    return data


def get_day_stats(campaign_id: int, day: str) -> dict:
    """Return {emails_sent, replies} for a single campaign on a single day."""
    body = {"start_date": day, "end_date": day}
    data = _request("POST", f"campaigns/{campaign_id}/stats", json=body).get(
        "data", {}
    )
    return {
        "sent": int(data.get("emails_sent", 0) or 0),
        "replies": int(data.get("unique_replies_per_contact", 0) or 0),
    }


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def build() -> dict:
    if not API_KEY:
        print("ERROR: EMAIL_BISON_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    today = datetime.now(timezone.utc).date()

    print("Fetching campaigns...")
    campaigns = get_campaigns()
    print(f"  Found {len(campaigns)} campaign(s).")

    # --- Headline totals come straight from the campaign objects (authoritative
    #     current cumulative counts). ---
    total_sent = sum(int(c.get("emails_sent", 0) or 0) for c in campaigns)
    total_replies = sum(int(c.get("replied", 0) or 0) for c in campaigns)
    active = sum(1 for c in campaigns if c.get("status") == "active")
    reply_rate = round(100 * total_replies / total_sent, 1) if total_sent else 0.0

    # --- Per-day series: query each campaign day-by-day over its active window
    #     and aggregate across campaigns. ---
    daily: dict[str, dict] = {}
    earliest = None
    for c in campaigns:
        cid = c["id"]
        created = datetime.fromisoformat(
            c["created_at"].replace("Z", "+00:00")
        ).date()
        earliest = created if earliest is None else min(earliest, created)
        print(f"  Fetching daily stats for '{c.get('name')}' (id {cid})...")
        for d in daterange(created, today):
            key = d.isoformat()
            stats = get_day_stats(cid, key)
            if key not in daily:
                daily[key] = {"sent": 0, "replies": 0}
            daily[key]["sent"] += stats["sent"]
            daily[key]["replies"] += stats["replies"]

    # Ensure a continuous, gap-free series from the first day to today.
    series = []
    if earliest:
        for d in daterange(earliest, today):
            key = d.isoformat()
            entry = daily.get(key, {"sent": 0, "replies": 0})
            series.append(
                {"date": key, "sent": entry["sent"], "replies": entry["replies"]}
            )

    # --- Curated campaign summaries (no bounce / unsubscribe / internals). ---
    campaign_rows = []
    for c in sorted(
        campaigns, key=lambda x: x.get("created_at", ""), reverse=True
    ):
        started = datetime.fromisoformat(
            c["created_at"].replace("Z", "+00:00")
        ).date()
        campaign_rows.append(
            {
                "name": c.get("name"),
                "status": c.get("status"),
                "sent": int(c.get("emails_sent", 0) or 0),
                "replies": int(c.get("replied", 0) or 0),
                "started": started.isoformat(),
            }
        )

    now = datetime.now(timezone.utc)
    return {
        "client": CLIENT_NAME,
        "generated_at": now.isoformat(),
        "generated_at_display": now.strftime("%B %-d, %Y"),
        "timezone": "UTC",
        "totals": {
            "emails_sent": total_sent,
            "replies": total_replies,
            "reply_rate": reply_rate,
            "campaigns_total": len(campaigns),
            "campaigns_active": active,
        },
        "daily": series,
        "campaigns": campaign_rows,
    }


def main():
    payload = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Write as a JS assignment so the page works both on a web host and when
    # opened directly from disk (no fetch / CORS needed).
    js = "window.FRANKLIN_DATA = " + json.dumps(payload, indent=2) + ";\n"
    OUTPUT_PATH.write_text(js, encoding="utf-8")

    t = payload["totals"]
    print("\n========== BUILT ==========")
    print(f"  Emails sent:   {t['emails_sent']:,}")
    print(f"  Replies:       {t['replies']:,}  ({t['reply_rate']}%)")
    print(f"  Campaigns:     {t['campaigns_total']} ({t['campaigns_active']} active)")
    print(f"  Days in chart: {len(payload['daily'])}")
    print(f"  Wrote:         {OUTPUT_PATH}")
    print("===========================")


if __name__ == "__main__":
    main()
