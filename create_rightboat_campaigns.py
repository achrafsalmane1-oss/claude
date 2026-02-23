#!/usr/bin/env python3
"""
Creates 3 outreach campaigns in EmailBison (Rightboat workspace).

Campaign 1 — "Operator Credibility"
  Step 1: Email 1  (Day 0)   — new thread    — "rightboat intro"
  Step 2: Email 2  (Day 7)   — new thread    — "rightboat customer evidence"
  Step 3: Email 3  (Day 14)  — thread reply  — "re: rightboat intro"

Campaign 2 — "Path to Profit"
  Step 1: Email 1  (Day 0)   — new thread    — "marine marketplace deal"
  Step 2: Email 2  (Day 7)   — new thread    — "rightboat traction update"
  Step 3: Email 3  (Day 14)  — thread reply  — "re: marine marketplace deal"

Campaign 3 — "Sector Specialist"
  Step 1: Email 1  (Day 0)   — new thread    — "ian x {FIRST_NAME} intro"
  Step 2: Email 2  (Day 7)   — new thread    — "rightboat for {PORTFOLIO_COMPANY}"
  Step 3: Email 3  (Day 14)  — thread reply  — "re: ian x {FIRST_NAME} intro"

Config:
  RIGHTBOAT_BISON_API_KEY  — API key for the Rightboat EmailBison workspace
  RIGHTBOAT_BISON_BASE_URL — Base URL (defaults to https://send.breakoutcreatives.com/api)
"""

import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("RIGHTBOAT_BISON_API_KEY", "")
BASE_URL = os.getenv("RIGHTBOAT_BISON_BASE_URL", "https://send.breakoutcreatives.com/api")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept":        "application/json",
    "Content-Type":  "application/json",
}

SIGNATURE = "Ian Atkins | CEO @ Rightboat"


# ===========================================================================
# CAMPAIGN 1 — "Operator Credibility"
# ===========================================================================

C1_NAME = "Rightboat — Operator Credibility"

C1_E1_SUBJECT = "rightboat intro"
C1_E1_BODY = f"""\
Hi {{FIRST_NAME}},

My name is Ian Atkins - I'm the CEO of Rightboat, a digital marketplace for boat sales.

I led a similar company in this space, Boats Group, which I built into the leading marine marketplace before selling it to Apax Partners for over $200M back in 2016 and then to Permira for over $900M in 2021.

I'm now building Rightboat into the clear #2 player in the space, but with significantly better unit economics than what we had the first time around.

We currently have 300+ paying customers at an average subscription price of £245 per month, over 35,000 listings on the platform, around 9 million annual visitors, and we're generating approximately 40,000 qualified leads per year.

We're raising £2M at a £9M valuation. We've also had early engagement from PE firms who are watching the business closely.

Would it be worth 20 minutes to walk you through where we're at and see if it's of interest?

{SIGNATURE}"""

C1_E2_SUBJECT = "rightboat customer evidence"
C1_E2_BODY = f"""\
{{FIRST_NAME}},

Can share video testimonials from 3 brokers showing 8-10x ROI vs. their previous platforms. All referenceable for investor calls.

We're also seeing 3x inbound inquiry vs. Q4 2025 - market timing is strong.

15 minutes this week to walk through traction?

{SIGNATURE}"""

C1_E3_SUBJECT = "re: rightboat intro"
C1_E3_BODY = f"""\
{{FIRST_NAME}},

Not sure if this got buried, but wanted to loop back one more time.

We've had some good momentum since I first reached out - brought on a few more customers and our inbound pipeline has picked up quite a bit.

If the timing's not right now, totally understand. But if you want a quick 10-minute overview of where we're at, I'm around most of this week.

{SIGNATURE}"""


# ===========================================================================
# CAMPAIGN 2 — "Path to Profit"
# ===========================================================================

C2_NAME = "Rightboat — Path to Profit"

C2_E1_SUBJECT = "marine marketplace deal"
C2_E1_BODY = f"""\
Hi {{FIRST_NAME}},

Wanted to put Rightboat on your radar - we're a digital boat marketplace that's roughly six months away from profitability, and I think the opportunity could be a strong fit for your portfolio.

We have 420 paying customers subscribing at an average of £245 per month, with over 35,000 active listings and around 9 million visitors hitting the platform annually. That traffic is converting into approximately 40,000 qualified leads per year for our dealers, and we've documented a 10x return on investment for our customer base.

We're projecting break-even by mid-2026, with a clear path to 40%+ EBITDA margins at scale. The business was built by the same team that scaled the previous market leader in this space to an exit north of £100M with Apax Partners.

We're currently raising £2M at a £9M valuation. Worth a quick intro later this week?

{SIGNATURE}"""

C2_E2_SUBJECT = "rightboat traction update"
C2_E2_BODY = f"""\
{{FIRST_NAME}},

Quick update on our end - we added 12 new paying customers just in January, and that OEM partnership tier we launched back in September is already sitting at around 15% of total revenue.

We've also got a couple of PE firms that have moved into diligence now.

Still have some room left in the round if you want to catch up for 15 minutes this week?

{SIGNATURE}"""

C2_E3_SUBJECT = "re: marine marketplace deal"
C2_E3_BODY = f"""\
{{FIRST_NAME}},

Not sure if this got buried, but wanted to loop back one more time.

We've had some good momentum since I first reached out - couple more customers signed, and our lead volume is up pretty significantly vs. last quarter.

If the timing's not right now, totally understand. But if you want a quick 10-minute overview of where we're at, I'm around most of this week.

{SIGNATURE}"""


# ===========================================================================
# CAMPAIGN 3 — "Sector Specialist"
# ===========================================================================

C3_NAME = "Rightboat — Sector Specialist"

C3_E1_SUBJECT = "ian x {FIRST_NAME} intro"
C3_E1_BODY = f"""\
Hi {{FIRST_NAME}},

Given your focus on marketplace technology, I thought Rightboat might be worth a closer look.

We've built a digital marketplace for boat sales that currently serves 420 paying customers, hosts over 35,000 listings, and attracts around 9 million visitors annually. We hold a clear #2 position in what is an £80 billion global market, and the business is built on strong, repeatable unit economics.

On the team side - we previously built and sold the market leader in this space to Apax Partners in 2016 for over £100M.

We're raising £2M at a £9M valuation and expect to reach break-even within the next six months.

Our longer-term exit path is targeting £40–50M by 2029, and we already have PE firms engaged in early conversations.

Any chance this is worth a quick intro with you or someone on your team?

{SIGNATURE}"""

C3_E2_SUBJECT = "rightboat for {PORTFOLIO_COMPANY}"
C3_E2_BODY = f"""\
{{FIRST_NAME}},

I noticed {{PORTFOLIO_COMPANY}} has some marine/outdoor operations - thought there might be two ways Rightboat could make sense here.

One is obviously the investment angle (we're raising £2M, 6 months to break-even).

The other is more strategic - if they've got a dealer network or any retail operations in the marine space, we might be able to help drive more qualified leads their way.

Worth a quick 5-minute chat to see if either makes sense? I've also got a few customers in {{REGION}} who'd be happy to jump on a reference call.

{SIGNATURE}"""

C3_E3_SUBJECT = "re: ian x {FIRST_NAME} intro"
C3_E3_BODY = f"""\
{{FIRST_NAME}},

Wanted to ping you one more time on this before I assume it's not a fit right now.

We've had a pretty strong couple of weeks - brought on some new customers and got good traction with a couple of PE shops that are now in diligence.

If you want to take a quick look at what we're building, I'm happy to send over our deck or jump on a 10-minute call.

Otherwise, no worries at all - happy to stay in touch and circle back down the road.

{SIGNATURE}"""


# ===========================================================================
# Helpers
# ===========================================================================

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


def create_campaign(name: str) -> int | None:
    print(f"Creating campaign: '{name}' ...")
    result = api_post("/campaigns", {"name": name})
    if not result:
        print(f"  ERROR: Failed to create campaign '{name}'.")
        return None
    campaign = result.get("campaign", result.get("data", result))
    campaign_id = campaign.get("id") if isinstance(campaign, dict) else result.get("id")
    if not campaign_id:
        print(f"  ERROR: Could not parse campaign ID. Response: {result}")
        return None
    print(f"  Campaign created. ID: {campaign_id}")
    return campaign_id


def add_step(campaign_id: int, title: str, subject: str, body: str,
             wait_in_days: int, thread_reply: bool) -> bool:
    r = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {
            "title": title,
            "sequence_steps": [{
                "email_subject": subject,
                "email_body":    body,
                "wait_in_days":  wait_in_days,
                "thread_reply":  thread_reply,
            }],
        },
    )
    if r:
        print(f"  '{title}' added.")
        return True
    print(f"  WARNING: '{title}' returned empty — check the campaign in the UI.")
    return False


# ===========================================================================
# Main
# ===========================================================================

def main():
    if not API_KEY:
        print("ERROR: RIGHTBOAT_BISON_API_KEY not set in .env")
        sys.exit(1)

    # Auth check
    print("Testing connection to Rightboat workspace...")
    me = api_get("/users")
    if not me:
        print("ERROR: Could not authenticate. Check RIGHTBOAT_BISON_API_KEY.")
        sys.exit(1)
    print("  Authenticated OK.\n")

    # List existing campaigns
    campaigns = api_get("/campaigns")
    existing = campaigns.get("data", campaigns) if isinstance(campaigns, dict) else campaigns
    if isinstance(existing, list):
        print(f"Existing campaigns in workspace: {len(existing)}")
        for c in existing[:5]:
            print(f"  - {c.get('name', c.get('id'))}")
        print()

    # -----------------------------------------------------------------------
    # Campaign 1 — Operator Credibility
    # -----------------------------------------------------------------------
    print("=" * 60)
    c1_id = create_campaign(C1_NAME)
    if c1_id:
        add_step(c1_id, "Email 1 – Operator Intro",
                 C1_E1_SUBJECT, C1_E1_BODY, wait_in_days=1, thread_reply=False)
        add_step(c1_id, "Email 2 – Customer Evidence",
                 C1_E2_SUBJECT, C1_E2_BODY, wait_in_days=7, thread_reply=False)
        add_step(c1_id, "Email 3 – Final Follow-Up",
                 C1_E3_SUBJECT, C1_E3_BODY, wait_in_days=7, thread_reply=True)
    print()

    # -----------------------------------------------------------------------
    # Campaign 2 — Path to Profit
    # -----------------------------------------------------------------------
    print("=" * 60)
    c2_id = create_campaign(C2_NAME)
    if c2_id:
        add_step(c2_id, "Email 1 – Path to Profit Intro",
                 C2_E1_SUBJECT, C2_E1_BODY, wait_in_days=1, thread_reply=False)
        add_step(c2_id, "Email 2 – Traction Update",
                 C2_E2_SUBJECT, C2_E2_BODY, wait_in_days=7, thread_reply=False)
        add_step(c2_id, "Email 3 – Final Follow-Up",
                 C2_E3_SUBJECT, C2_E3_BODY, wait_in_days=7, thread_reply=True)
    print()

    # -----------------------------------------------------------------------
    # Campaign 3 — Sector Specialist
    # -----------------------------------------------------------------------
    print("=" * 60)
    c3_id = create_campaign(C3_NAME)
    if c3_id:
        add_step(c3_id, "Email 1 – Sector Intro",
                 C3_E1_SUBJECT, C3_E1_BODY, wait_in_days=1, thread_reply=False)
        add_step(c3_id, "Email 2 – Portfolio Angle",
                 C3_E2_SUBJECT, C3_E2_BODY, wait_in_days=7, thread_reply=False)
        add_step(c3_id, "Email 3 – Final Follow-Up",
                 C3_E3_SUBJECT, C3_E3_BODY, wait_in_days=7, thread_reply=True)
    print()

    print("=" * 60)
    print("Done. All 3 campaigns created in the Rightboat workspace.")
    print("Next steps for each campaign:")
    print("  1. Verify steps and copy look correct in the UI")
    print("  2. Add sender email accounts")
    print("  3. Configure sending schedule")
    print("  4. Import leads and launch")


if __name__ == "__main__":
    main()
