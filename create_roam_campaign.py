#!/usr/bin/env python3
"""
Creates 'ROAM AI - Investor Outreach' campaign in EmailBison (ROAM workspace).

Sequence structure:
  Step 1 — Email 1 (3 A/B variants)
  Step 2 — Traction Rotation  (thread reply, 3 days later)
  Step 3 — Team / Credibility (new thread, 4 days later)

Config (via .env or environment):
  ROAM_BISON_API_KEY  — API key for the ROAM AI EmailBison workspace
  ROAM_BISON_BASE_URL — Base URL (defaults to https://send.breakoutcreatives.com/api)
"""

import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("ROAM_BISON_API_KEY", "")
BASE_URL = os.getenv("ROAM_BISON_BASE_URL", "https://send.breakoutcreatives.com/api")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

CAMPAIGN_NAME = "ROAM AI - Investor Outreach"

SIGNATURE = "Brandon Brown | CEO @ Roam AI"

# ---------------------------------------------------------------------------
# Step 1 — Email 1 variants (3 A/B copies)  — spintax throughout
# ---------------------------------------------------------------------------

# Variant 1 (primary) — spintax subject: {Roam AI intro|ROAM AI|Quick intro|Permian AI}
SUBJECT_1A = "{Roam AI intro|ROAM AI|Quick intro|Permian AI}"
BODY_1A = """\
Hi {first_name},

I'm Brandon Brown, CEO of ROAM AI.

We're {raising|securing} $5.5MM to scale autonomous ESP optimization for oil & gas operators delivering 3-8% production uplift and 50% failure rate reduction.

$2.5MM expected revenue this year, 250+ wells optimized, and currently profitable with no outside capital.

Given your focus on {investor_focus}, would it make sense to send the deck or {set|schedule} a quick call?

""" + SIGNATURE

# Variant 2 — straight credibility
SUBJECT_1B = "{Roam AI intro|ROAM AI|Quick intro|Permian AI}"
BODY_1B = """\
Hi {first_name},

I'm Brandon, {CEO|co-founder} of ROAM AI.

We're {raising $5.5MM|in the middle of our $5.5MM raise} to scale the only two-parameter ESP optimization system on the market, hardware + AI, patent-pending.

Results to date: 250+ wells, 3-8% production uplift, 50% failure rate decrease, $2.5MM 2025 revenue.

No outside capital raised — profitable from day one.

From my research, I thought we'd align well with {company}, but I'm happy to send a deck first for you to take a look if you're interested.

Is email the best place to send it?

""" + SIGNATURE

# Variant 3 — Operator-Built Angle
SUBJECT_1C = "{energy tech intro|ROAM AI intro|quick intro}"
BODY_1C = """\
Hi {first_name},

I'm Brandon Brown, CEO of ROAM AI.

We're {raising|closing} a $5.5MM round to scale AI-driven ESP optimization built by a team with 100+ years of combined upstream experience.

We're the only solution with proprietary hardware for two-parameter control (pump speed + backpressure).

250+ wells optimized, $2.5MM 2025 revenue, currently profitable.

Given {company_name}'s {focus on energy tech|interest in industrial AI}, I think we'd fit your portfolio well.

What's the best way we can align with your review process?

Appreciate your time,

""" + SIGNATURE

# ---------------------------------------------------------------------------
# Step 2 — Traction Rotation (thread reply, Day 3-4)
# ---------------------------------------------------------------------------
SUBJECT_2 = "Re:"
BODY_2 = """\
{first_name},

{Wanted to add|Just wanted to add} some context on traction.

Current customer results: one operator running the full ROAM suite at $200K ARR, another averaging $70K/month across multiple projects.

Pipeline at $13.5M with $2.6M closed won.

Market timing is strong. O&G is finally investing in AI optimization after years of {catching up|being behind the curve}.

If this is in your wheelhouse, {happy to walk through the model|I'd love to walk through the numbers}.

""" + SIGNATURE

# ---------------------------------------------------------------------------
# Step 3 — Team / Credibility Angle (new thread, Day 7-8)
# ---------------------------------------------------------------------------
SUBJECT_3 = "{first_name}, starting fresh in case the last thread got buried."
BODY_3 = """\
Our team has 100+ years combined upstream experience, including CIO of the Year recognition and major digital transformation wins at Vital Energy and Chesapeake.

{Raising|Closing} $5.5MM. $2.5MM 2025 revenue, profitable, patent-pending technology, 250+ wells optimized.

Would you be open to a quick intro to see if this would be a fit at all for {company}?

""" + SIGNATURE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_get(path: str, params: dict | None = None) -> dict:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    for attempt in range(4):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
            if resp.status_code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            print(f"  GET error ({exc}), retrying...")
            time.sleep(2 ** (attempt + 1))
    return {}


def api_post(path: str, body: dict) -> dict:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    for attempt in range(4):
        try:
            resp = requests.post(url, headers=HEADERS, json=body, timeout=60)
            if resp.status_code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            if not resp.ok:
                print(f"  POST {path} -> HTTP {resp.status_code}: {resp.text[:400]}")
                return {}
            return resp.json()
        except requests.RequestException as exc:
            print(f"  POST error ({exc}), retrying...")
            time.sleep(2 ** (attempt + 1))
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not API_KEY:
        print("ERROR: Set ROAM_BISON_API_KEY in your .env file.")
        sys.exit(1)

    # 1. Auth check
    print("Testing connection...")
    me = api_get("/users")
    if not me:
        print("ERROR: Could not authenticate. Check ROAM_BISON_API_KEY.")
        sys.exit(1)
    print("  Authenticated OK.\n")

    # 2. List existing campaigns
    campaigns = api_get("/campaigns")
    existing = campaigns.get("data", campaigns) if isinstance(campaigns, dict) else campaigns
    if isinstance(existing, list):
        print(f"Existing campaigns in workspace: {len(existing)}")
        for c in existing[:5]:
            print(f"  - {c.get('name', c.get('id'))}")
        print()

    # 3. Create the campaign
    print(f"Creating campaign: '{CAMPAIGN_NAME}' ...")
    result = api_post("/campaigns", {"name": CAMPAIGN_NAME})
    if not result:
        print("ERROR: Failed to create campaign.")
        sys.exit(1)

    campaign = result.get("campaign", result.get("data", result))
    campaign_id = campaign.get("id") if isinstance(campaign, dict) else result.get("id")
    if not campaign_id:
        print(f"ERROR: Could not parse campaign ID from response: {result}")
        sys.exit(1)
    print(f"  Campaign created. ID: {campaign_id}\n")

    # 4. Step 1 — 3 A/B variants of Email 1
    step1_steps = [
        # Variant 1 (primary)
        {
            "email_subject": SUBJECT_1A,
            "email_body": BODY_1A,
            "wait_in_days": 1,
            "thread_reply": False,
        },
        # Variant 2
        {
            "email_subject": SUBJECT_1B,
            "email_body": BODY_1B,
            "wait_in_days": 1,
            "thread_reply": False,
            "variant": True,
            "variant_from_step": 1,
        },
        # Variant 3 — Operator-Built Angle
        {
            "email_subject": SUBJECT_1C,
            "email_body": BODY_1C,
            "wait_in_days": 1,
            "thread_reply": False,
            "variant": True,
            "variant_from_step": 1,
        },
    ]

    print(f"Adding Step 1 (3 variants) to campaign {campaign_id} ...")
    r1 = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 1 – Investor Intro", "sequence_steps": step1_steps},
    )
    if r1:
        print(f"  Step 1 added. Response: {str(r1)[:200]}")
    else:
        print("  WARNING: Step 1 POST returned empty — check the campaign in the UI.")

    # 5. Step 2 — Traction Rotation (thread reply, day 3-4)
    step2_steps = [
        {
            "email_subject": SUBJECT_2,
            "email_body": BODY_2,
            "wait_in_days": 3,
            "thread_reply": True,
        }
    ]

    print(f"\nAdding Step 2 (Traction Rotation) to campaign {campaign_id} ...")
    r2 = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 2 – Traction Rotation", "sequence_steps": step2_steps},
    )
    if r2:
        print(f"  Step 2 added. Response: {str(r2)[:200]}")
    else:
        print("  WARNING: Step 2 POST returned empty — check the campaign in the UI.")

    # 6. Step 3 — Team / Credibility (new thread, day 7-8)
    step3_steps = [
        {
            "email_subject": SUBJECT_3,
            "email_body": BODY_3,
            "wait_in_days": 4,
            "thread_reply": False,
        }
    ]

    print(f"\nAdding Step 3 (Team/Credibility) to campaign {campaign_id} ...")
    r3 = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 3 – Team & Credibility", "sequence_steps": step3_steps},
    )
    if r3:
        print(f"  Step 3 added. Response: {str(r3)[:200]}")
    else:
        print("  WARNING: Step 3 POST returned empty — check the campaign in the UI.")

    print(f"\nDone. Campaign '{CAMPAIGN_NAME}' is ready in EmailBison (ID: {campaign_id}).")
    print("Next steps:")
    print("  1. Verify all 3 steps and 3 variants look correct in the UI")
    print("  2. Add sender email accounts to the campaign")
    print("  3. Configure sending schedule")
    print("  4. Import leads and launch")


if __name__ == "__main__":
    main()
