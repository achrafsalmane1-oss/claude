#!/usr/bin/env python3
"""
Creates 'Visibl - YC Outreach Sequence' campaign in EmailBison (Visibl workspace).

Sequence structure:
  Step 1 — Email 1 (5 A/B variants: primary 1A, plus 1A-alt, 1B, 1C, 1D)
  Step 2 — Soft Follow-Up  (thread reply, 3 days later)
  Step 3 — Redirect / Close (thread reply, 3 days later)

Config (via .env or environment):
  VISIBL_BISON_API_KEY  — API key for the Visibl EmailBison workspace
  VISIBL_BISON_BASE_URL — Base URL for the Visibl workspace API
                          (defaults to https://send.breakoutcreatives.com/api)
"""

import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("VISIBL_BISON_API_KEY") or os.getenv("BISON_API_KEY", "")
BASE_URL = os.getenv("VISIBL_BISON_BASE_URL", "https://send.breakoutcreatives.com/api")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

CAMPAIGN_NAME = "Visibl - YC Outreach Sequence"

SIGNATURE = "Bryce Neil | Founder @ Visibl Semiconductors"

# ---------------------------------------------------------------------------
# Step 1 — Email 1 variants (5 A/B copies)  — spintax throughout
# ---------------------------------------------------------------------------

# Variant 1A (primary) — Subject: "Quick intro <> YC + semiconductors"
SUBJECT_1A = "Quick intro <> YC + semiconductors"
BODY_1A = """\
Hi {first_name},

I'm Bryce Neil, founder of Visibl Semiconductors.

We {were accepted into|got into} Y Combinator {last week|recently}, and through YC we've been {spending time with|talking to} semiconductor teams around one problem.

As teams scale, specs, RTL, and verification {slowly drift|start to drift} — and it {usually|tends to} show up late, when it's most painful.

We're building Visibl to {help teams catch|surface} those issues earlier and {reduce|cut down} the coordination work that pulls senior engineers into constant triage.

{Curious|Wondering} how {company_name} handles this today and whether it's even a problem on your side.

{Worth|Open to} a quick {conversation|chat}?

""" + SIGNATURE

# Variant 1A-alt (A/B subject test) — Subject: "spec ↔ RTL ↔ DV question"
SUBJECT_1A_ALT = "spec ↔ RTL ↔ DV question"
BODY_1A_ALT = """\
Hi {first_name},

I'm Bryce, {co-founder & CEO|founder} of Visibl Semiconductors.

We've been {talking to|speaking with} silicon teams about a {common|recurring} scaling issue: as orgs grow, specs, RTL, and verification {drift|fall out of sync} and problems {show|surface} up late, around {integration and freeze windows|tapeout}.

We're building a {low-lift|lightweight}, always-on way to {automatically flag|catch} that drift early.

Is that something {company_name} {runs into|deals with}, or mostly under control?

If it's relevant, {happy|glad} to share what we're learning. We're YC-backed, and the team is ex-Microsoft/Intel/Arm (silicon) and Deloitte OmniaAI.

I'm Bay Area–based as well, {15 min Zoom|a quick Zoom} or in-person works.

""" + SIGNATURE

# Variant 1B — YC + Team Credibility
SUBJECT_1B = "Quick intro <> YC + semiconductors"
BODY_1B = """\
Hi {first_name},

I'm Bryce Neil, founder of Visibl.

We {were accepted into|got into} Y Combinator {last week|recently}, and our team ({ex-Microsoft|former Microsoft}, long-time silicon & infra folks) has been {spending time with|talking to} semiconductor teams on a pattern we keep seeing.

As teams scale, coordination quietly {becomes|is} the bottleneck — specs, RTL, and verification drift, and senior engineers {get pulled into|end up in} late triage.

We're building Visibl to {help teams surface|flag} those issues earlier and {keep things aligned|stay ahead} as complexity grows.

{Curious|Wondering} how {company_name} {approaches|handles} this today.

{Worth|Open to} a short {conversation|chat}?

""" + SIGNATURE

# Variant 1C — YC + "What we're learning" Angle
SUBJECT_1C = "Quick intro <> YC + semiconductors"
BODY_1C = """\
Hi {first_name},

I'm Bryce, founder of Visibl.

We {just got into|were just accepted into} Y Combinator {last week|recently}, and we've been {speaking with|talking to} a number of semiconductor teams about how coordination breaks down as orgs scale.

The {common|recurring} theme: tools scale well, humans don't. Specs change, decisions {get buried|pile up}, and issues {show up|surface} late when they're hardest to fix.

Our team ({ex-Microsoft|former Microsoft}, deep infra + silicon background) is building Visibl to {tackle|close} that gap for teams like yours.

{Would love|Love} to hear how {company_name} handles this today, even just as a sanity check.

{Open to|Worth} a quick {chat|call}?

""" + SIGNATURE

# Variant 1D — Stronger Flex, Still Clean
SUBJECT_1D = "Quick intro <> YC + semiconductors"
BODY_1D = """\
Hi {first_name},

I'm Bryce Neil, founder of Visibl.

We {were accepted into|got into} Y Combinator {recently|last week}. Our team includes folks who've {built|shipped} large-scale systems at Microsoft and worked closely with silicon orgs as they grew.

One issue we keep seeing: as semiconductor teams add people and artifacts, coordination {becomes fragile|breaks down} — specs, RTL, and verification {fall out of sync|drift}, and senior engineers {end up firefighting|get pulled into constant triage}.

Visibl is built {around solving|to fix} that coordination layer.

{Curious|Wondering} whether this is something {company_name} has {felt|run into} as the team has grown.

{Worth|Open to} a short {conversation|chat}?

""" + SIGNATURE

# ---------------------------------------------------------------------------
# Step 2 — Soft Follow-Up  — spintax throughout
# ---------------------------------------------------------------------------
SUBJECT_2 = "Following up"
BODY_2 = """\
{first_name},

{Quick follow-up.|Following up.}

One thing we keep hearing from teams we're talking to through YC is that most {schedule risk|timeline slippage} doesn't come from tools — it comes from keeping humans aligned as artifacts and decisions multiply.

{Totally possible|Possible} this isn't an issue for {company_name}, but {figured it was worth asking|wanted to check}.

{Happy|Glad} to share what we're learning either way.

""" + SIGNATURE

# ---------------------------------------------------------------------------
# Step 3 — Redirect / Close  — spintax throughout
# ---------------------------------------------------------------------------
SUBJECT_3 = "Right person?"
BODY_3 = """\
Hi {first_name},

If this isn't {really your area|the right fit}, no worries at all — is there someone else on the {silicon or verification|engineering or verification} side who {thinks about this kind of thing|owns this}?

{Appreciate it.|Thanks.}

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
        print("ERROR: Set VISIBL_BISON_API_KEY (or BISON_API_KEY) in your .env file.")
        sys.exit(1)

    # 1. Auth check
    print("Testing connection...")
    me = api_get("/users")
    if not me:
        print("ERROR: Could not authenticate. Check VISIBL_BISON_API_KEY.")
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

    # 4. Step 1 — 5 A/B variants of Email 1
    step1_steps = [
        # Primary (1A)
        {
            "email_subject": SUBJECT_1A,
            "email_body": BODY_1A,
            "wait_in_days": 1,
            "thread_reply": False,
        },
        # Variant 1A-alt (A/B subject test)
        {
            "email_subject": SUBJECT_1A_ALT,
            "email_body": BODY_1A_ALT,
            "wait_in_days": 1,
            "thread_reply": False,
            "variant": True,
            "variant_from_step": 1,
        },
        # Variant 1B
        {
            "email_subject": SUBJECT_1B,
            "email_body": BODY_1B,
            "wait_in_days": 1,
            "thread_reply": False,
            "variant": True,
            "variant_from_step": 1,
        },
        # Variant 1C
        {
            "email_subject": SUBJECT_1C,
            "email_body": BODY_1C,
            "wait_in_days": 1,
            "thread_reply": False,
            "variant": True,
            "variant_from_step": 1,
        },
        # Variant 1D
        {
            "email_subject": SUBJECT_1D,
            "email_body": BODY_1D,
            "wait_in_days": 1,
            "thread_reply": False,
            "variant": True,
            "variant_from_step": 1,
        },
    ]

    print(f"Adding Step 1 (5 variants) to campaign {campaign_id} ...")
    r1 = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 1 – Founder Intro", "sequence_steps": step1_steps},
    )
    if r1:
        print(f"  Step 1 added. Response: {str(r1)[:200]}")
    else:
        print("  WARNING: Step 1 POST returned empty — check the campaign in the UI.")

    # 5. Step 2 — Soft Follow-Up
    step2_steps = [
        {
            "email_subject": SUBJECT_2,
            "email_body": BODY_2,
            "wait_in_days": 3,
            "thread_reply": True,
        }
    ]

    print(f"\nAdding Step 2 (Follow-Up) to campaign {campaign_id} ...")
    r2 = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 2 – Soft Follow-Up", "sequence_steps": step2_steps},
    )
    if r2:
        print(f"  Step 2 added. Response: {str(r2)[:200]}")
    else:
        print("  WARNING: Step 2 POST returned empty — check the campaign in the UI.")

    # 6. Step 3 — Redirect / Close
    step3_steps = [
        {
            "email_subject": SUBJECT_3,
            "email_body": BODY_3,
            "wait_in_days": 3,
            "thread_reply": True,
        }
    ]

    print(f"\nAdding Step 3 (Redirect/Close) to campaign {campaign_id} ...")
    r3 = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 3 – Redirect / Close", "sequence_steps": step3_steps},
    )
    if r3:
        print(f"  Step 3 added. Response: {str(r3)[:200]}")
    else:
        print("  WARNING: Step 3 POST returned empty — check the campaign in the UI.")

    print(f"\nDone. Campaign '{CAMPAIGN_NAME}' is ready in EmailBison (ID: {campaign_id}).")
    print("Next steps:")
    print("  1. Verify all 3 steps and 5 variants look correct in the UI")
    print("  2. Add sender email accounts to the campaign")
    print("  3. Configure sending schedule")
    print("  4. Import leads and launch")


if __name__ == "__main__":
    main()
