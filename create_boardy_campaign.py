#!/usr/bin/env python3
"""
Creates 'Boardy Ventures - LP Outreach' campaign in EmailBison (Boardy workspace).

Sequence structure:
  Step 1 — Email 1  (Day 0)    : 3 A/B variants (1A primary, 1B, 1C)  — new thread
  Step 2 — Email 2  (Day 3-4)  : Andrew context follow-up              — thread reply
  Step 3 — Email 3  (Day 7-8)  : Metrics / fund thesis                 — NEW thread
  Step 4 — Email 4  (Day 11-12): Soft close / referral ask             — thread reply

Config (via .env or environment):
  BOARDY_BISON_API_KEY  — API key for the Boardy EmailBison workspace
  BOARDY_BISON_BASE_URL — Base URL (defaults to https://send.breakoutcreatives.com/api)
"""

import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("BOARDY_BISON_API_KEY", "")
BASE_URL = os.getenv("BOARDY_BISON_BASE_URL", "https://send.breakoutcreatives.com/api")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept":        "application/json",
    "Content-Type":  "application/json",
}

CAMPAIGN_NAME = "Boardy Ventures - LP Outreach"

# ---------------------------------------------------------------------------
# Step 1 — Email 1  (Day 0)  — 3 A/B variants
# ---------------------------------------------------------------------------

SUBJECT_1 = "boardy ventures intro"

BODY_1A = """\
Hi {FIRST_NAME},

I'm Tarik Sehovic, venture partner at Boardy.

Reaching out because we're {building|launching} something I wanted to put on your radar.

We built an AI relationship platform, Boardy, helping founders with fundraising, recruiting, and BD by making real introductions through a network of 113,000 contacts built over the last 3 years. Over 100,000 founders have {talked to|spoken with} Boardy, and our intro success rate sits at 40%.

Founders started asking Boardy to invest directly. Investors started asking about SPVs. So we partnered with AngelList to {launch|build} Boardy Ventures - a venture fund that deploys capital into the highest-conviction opportunities surfaced from that network.

No GP on earth can talk to every founder in the market, but Boardy already does.

We're already working with a number of investors across funds and family capital as LPs.

I'd love a quick intro to {learn more about|understand} where you're deploying and whether Boardy Ventures {could be a fit|aligns with} how you're thinking about allocation.

Would you be open to a quick intro sometime next week?

Tarik
Venture Partner @ Boardy"""

BODY_1B = """\
Hi {FIRST_NAME},

I'm Tarik Sehovic, venture partner at Boardy.

Reaching out because I think what we're {building|doing} with Boardy Ventures could be relevant to how you think about venture allocation.

Boardy is an AI that makes real introductions for founders across fundraising, recruiting, and BD. 113,000 contacts in the network. 100,000+ founders have {talked to|engaged with} Boardy. Intros succeed at a 40% rate.

Boardy Ventures is the fund that grew out of that infrastructure. We partnered with AngelList to {deploy|invest} capital into the highest-conviction opportunities Boardy surfaces from that pipeline.

We're working with LPs across funds and family offices. I'd love to {learn about|understand} your current focus and see if this {fits|makes sense}.

Would a {quick call|brief intro} work sometime {next week|this week}?

Tarik
Venture Partner @Boardy"""

BODY_1C = """\
Hi {FIRST_NAME},

I'm Tarik Sehovic, venture partner at Boardy.

Reaching out because we're doing something in venture that I think could change how you allocate, and I think it's worth a few minutes of your time.

We built an AI called Boardy that {makes|facilitates} real introductions for founders - actual warm intros through a network of 113,000 contacts.

100,000+ founders have {talked to|worked with} Boardy. The intro success rate is 40%.

That deal flow led to Boardy Ventures. Founders wanted investment, investors wanted exposure to what Boardy was surfacing, so we partnered with AngelList to {launch|formalize} a fund that backs the best of what comes through the network.

We're already working with a number of LPs across funds and family capital and are looking for more partners like you. Would love to {have a quick intro|connect} to learn where you're deploying and whether Boardy Ventures {could fit|aligns with} your allocation.

{Open to|Any interest in} a quick call {next week|this week}?

Tarik
Venture Partner @Boardy"""

# ---------------------------------------------------------------------------
# Step 2 — Email 2  (Day 3-4)  — thread reply
# ---------------------------------------------------------------------------

BODY_2 = """\
Hi {FIRST_NAME},

{Following up|Circling back} on my last note about Boardy Ventures - wanted to add some context on who's behind it.

Andrew D'Souza, our founder, {built|scaled} Clearco - {deploying|putting} $2.5B into 10,000 companies across 11 countries. He built Boardy to solve the relationship bottleneck he saw founders {hitting|running into} at every stage of growth.

Boardy Ventures is the natural extension of that. The platform already {talks to|speaks with} thousands of founders every month. The fund backs the ones where conviction is highest.

Would love to {continue the conversation|connect} if this {fits|aligns with} how you're thinking about allocation.

Tarik
Venture Partner @Boardy"""

# ---------------------------------------------------------------------------
# Step 3 — Email 3  (Day 7-8)  — NEW thread
# ---------------------------------------------------------------------------

SUBJECT_3 = "boardy // {FIRST_NAME} check-in"

BODY_3 = """\
{FIRST_NAME},

{Wanted to|Looking to} add some context on why we think Boardy Ventures {can|is positioned to} outperform traditional LPs.

The fund sits on top of a platform that {has spoken with|talked to} 100,000+ founders and {maintains|holds} 113,000 real relationships.

That means Boardy sees deals earlier, sees more of them, and can be more selective about what the fund backs - all at a volume no human GP can match.

The numbers behind the platform:

* $4.4M ARR {added|generated} in 4 weeks
* 37 signed agreements at $10K/month
* 40% intro success rate

For LPs, that {translates to|means} access to a concentrated portfolio of high-conviction deals sourced from a pipeline that simply doesn't exist anywhere else in venture.

Happy to {walk through|share} the fund thesis and economics if there's interest.

Tarik
Venture Partner @Boardy"""

# ---------------------------------------------------------------------------
# Step 4 — Email 4  (Day 11-12)  — thread reply
# ---------------------------------------------------------------------------

BODY_4 = """\
Hi {FIRST_NAME},

No worries if this isn't of interest for you or your team right now.

Wondering if there's anyone in your network that might have an eye for this you could point me to?

Tarik
Venture Partner @Boardy"""


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
        print("ERROR: BOARDY_BISON_API_KEY not set in .env")
        sys.exit(1)

    # 1. Auth check
    print("Testing connection to Boardy workspace...")
    me = api_get("/users")
    if not me:
        print("ERROR: Could not authenticate. Check BOARDY_BISON_API_KEY.")
        sys.exit(1)
    print("  Authenticated OK.\n")

    # 2. List existing campaigns (sanity check / workspace confirmation)
    campaigns = api_get("/campaigns")
    existing = campaigns.get("data", campaigns) if isinstance(campaigns, dict) else campaigns
    if isinstance(existing, list):
        print(f"Existing campaigns in Boardy workspace: {len(existing)}")
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

    # 4. Step 1 — Email 1 (3 A/B variants, Day 0, new thread)
    step1 = [
        # Primary: 1A
        {
            "email_subject": SUBJECT_1,
            "email_body":    BODY_1A,
            "wait_in_days":  1,
            "thread_reply":  False,
        },
        # Variant: 1B
        {
            "email_subject":    SUBJECT_1,
            "email_body":       BODY_1B,
            "wait_in_days":     1,
            "thread_reply":     False,
            "variant":          True,
            "variant_from_step": 1,
        },
        # Variant: 1C
        {
            "email_subject":    SUBJECT_1,
            "email_body":       BODY_1C,
            "wait_in_days":     1,
            "thread_reply":     False,
            "variant":          True,
            "variant_from_step": 1,
        },
    ]

    print(f"Adding Step 1 (3 variants) ...")
    r1 = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 1 – Boardy Ventures Intro", "sequence_steps": step1},
    )
    if r1:
        print(f"  Step 1 added. Response: {str(r1)[:200]}")
    else:
        print("  WARNING: Step 1 POST returned empty — check the campaign in the UI.")

    # 5. Step 2 — Email 2 (Day 3-4, thread reply)
    step2 = [
        {
            "email_subject": "boardy ventures intro",
            "email_body":    BODY_2,
            "wait_in_days":  3,
            "thread_reply":  True,
        }
    ]

    print(f"\nAdding Step 2 (Andrew context follow-up, Day 3-4) ...")
    r2 = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 2 – Andrew D'Souza Context", "sequence_steps": step2},
    )
    if r2:
        print(f"  Step 2 added. Response: {str(r2)[:200]}")
    else:
        print("  WARNING: Step 2 POST returned empty — check the campaign in the UI.")

    # 6. Step 3 — Email 3 (Day 7-8, NEW thread)
    step3 = [
        {
            "email_subject": SUBJECT_3,
            "email_body":    BODY_3,
            "wait_in_days":  4,
            "thread_reply":  False,
        }
    ]

    print(f"\nAdding Step 3 (Metrics / fund thesis, Day 7-8, new thread) ...")
    r3 = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 3 – Fund Metrics & Thesis", "sequence_steps": step3},
    )
    if r3:
        print(f"  Step 3 added. Response: {str(r3)[:200]}")
    else:
        print("  WARNING: Step 3 POST returned empty — check the campaign in the UI.")

    # 7. Step 4 — Email 4 (Day 11-12, thread reply)
    step4 = [
        {
            "email_subject": "boardy // {FIRST_NAME} check-in",
            "email_body":    BODY_4,
            "wait_in_days":  4,
            "thread_reply":  True,
        }
    ]

    print(f"\nAdding Step 4 (Soft close / referral ask, Day 11-12) ...")
    r4 = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 4 – Soft Close", "sequence_steps": step4},
    )
    if r4:
        print(f"  Step 4 added. Response: {str(r4)[:200]}")
    else:
        print("  WARNING: Step 4 POST returned empty — check the campaign in the UI.")

    print(f"\nDone. Campaign '{CAMPAIGN_NAME}' is ready in the Boardy workspace (ID: {campaign_id}).")
    print("Next steps:")
    print("  1. Verify all 4 steps and 3 variants look correct in the UI")
    print("  2. Add sender email accounts to the campaign")
    print("  3. Configure sending schedule")
    print("  4. Import leads and launch")


if __name__ == "__main__":
    main()
