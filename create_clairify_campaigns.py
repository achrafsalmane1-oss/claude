#!/usr/bin/env python3
"""
Creates 3 outreach campaigns in EmailBison (Clairify workspace).

Campaign 1 — "Product Built, Now Scale"
  Step 1: Email 1  (Day 0)   — new thread    — {Quick intro|Clairify|Executive AI for MSPs}
  Step 2: Email 2  (Day 3-4) — thread reply  — (no subject)
  Step 3: Email 3  (Day 7-8) — new thread    — {Clairify // {FIRST_NAME}|Quick follow-up}
  Step 4: Email 4  (Day 11-12)— new thread   — {Last note|Final follow-up}

Campaign 2 — "The Information Overload Problem"
  Step 1: Email 1  (Day 0)   — new thread    — {Quick intro|Solving executive overload|Clairify}
  Step 2: Email 2  (Day 3-4) — thread reply  — (no subject)
  Step 3: Email 3  (Day 7-8) — new thread    — {Clairify // follow-up|Executive intelligence platform}
  Step 4: Email 4  (Day 11-12)— new thread   — {Last note|Final email}

Campaign 3 — "Capital-Efficient Execution"
  Step 1: Email 1  (Day 0)   — new thread    — {Quick intro|Bootstrapped to SOC 2|Clairify}
  Step 2: Email 2  (Day 3-4) — thread reply  — (no subject)
  Step 3: Email 3  (Day 7-8) — new thread    — {Clairify // {FIRST_NAME}|Capital-efficient SaaS}
  Step 4: Email 4  (Day 11-12)— new thread   — {Last note|Final follow-up}

Config:
  CLAIRIFY_BISON_API_KEY  — API key for the Clairify EmailBison workspace
  CLAIRIFY_BISON_BASE_URL — Base URL (defaults to https://send.breakoutcreatives.com/api)
"""

import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("CLAIRIFY_BISON_API_KEY", "")
BASE_URL = os.getenv("CLAIRIFY_BISON_BASE_URL", "https://send.breakoutcreatives.com/api")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept":        "application/json",
    "Content-Type":  "application/json",
}


# ===========================================================================
# CAMPAIGN 1 — "Product Built, Now Scale"
# ===========================================================================

C1_NAME = "Clairify — Product Built, Now Scale"

C1_E1_SUBJECT = "{Quick intro|Clairify|Executive AI for MSPs}"
C1_E1_BODY = """\
Hi {FIRST_NAME},

We're raising $2M on a SAFE ($10M cap) to scale go-to-market. The product is built and early feedback is positive. Now we need capital to sell.

We spent 18 months heads-down building an executive intelligence platform for professional services leadership. Unifies information streams, AI-powered summaries, Q&A for decisions at scale.

Where we are now: team of 12, SOC 2 Type 1 certified, iOS and web apps shipped. 100% bootstrapped on $75K.

The market: MSP executives are drowning. 2-3x the communications of individual contributors, 40+ apps to juggle, and 40% have seen leadership effectiveness decline for 5 years straight. That's a $650B market growing 14%.

{Worth|Open to} a quick {call|intro}?

Mehul Patel
Co-founder, Clairify"""

C1_E2_SUBJECT = "Re: {Quick intro|Clairify|Executive AI for MSPs}"
C1_E2_BODY = """\
Hi {FIRST_NAME},

{Wanted to|Looking to} add context on why we're raising now.

We've proven we can build. 18 months from first line of code to enterprise-ready. SOC 2 certified. Product shipped. Team of 12.

What we haven't proven yet is that we can sell at scale. That's what the $2M is for: design partners, pilots, paid acquisition, and the GTM team to run it.

The AI isn't cutting-edge. We use proven models in their sweet spot. The value is the implementation against real business insight from a team that's lived the MSP chaos firsthand.

{Does|Would} this {fit|align with} what you're looking at?

Mehul"""

C1_E3_SUBJECT = "{Clairify // {FIRST_NAME}|Quick follow-up}"
C1_E3_BODY = """\
Hi {FIRST_NAME},

Following up on Clairify.

Quick summary:

- Executive intelligence platform for MSP leadership
- Unifies information streams, AI-powered summaries, Q&A for decisions
- $650B market growing 14%
- Idea to enterprise-ready in 18 months
- Team of 12, SOC 2 certified, iOS and web shipped
- 100% bootstrapped ($75K invested)

{Raising|Securing} $2M on a SAFE ($10M cap) to scale GTM.

{Worth|Open to} a {call|quick chat}?

Mehul Patel
Co-founder, Clairify"""

C1_E4_SUBJECT = "{Last note|Final follow-up}"
C1_E4_BODY = """\
Hi {FIRST_NAME},

Last {note|email} on Clairify.

Product is built. SOC 2 certified. Team of 12. $650B market.

{Raising|Securing} $2M on a SAFE ($10M cap) to scale GTM.

If timing works, {happy|glad} to walk you through the product. If not, I'll {reach back|circle back} when it makes sense.

Mehul Patel
Co-founder, Clairify"""


# ===========================================================================
# CAMPAIGN 2 — "The Information Overload Problem"
# ===========================================================================

C2_NAME = "Clairify — The Information Overload Problem"

C2_E1_SUBJECT = "{Quick intro|Solving executive overload|Clairify}"
C2_E1_BODY = """\
Hi {FIRST_NAME},

We've been looking into funds that might have an appetite for what we're building at Clairify and {fund_name} came up.

We're raising $2M on a SAFE ($10M cap) to scale go-to-market.

The problem we're solving: MSP executives receive 2-3x the communications of individual contributors. The average MSP uses 40+ applications. Only 33% have a strategic plan for the next year. And 40% have seen leadership effectiveness decline for 5 years straight.

Clairify fixes this. We unify information streams (starting with email), distill messages into actionable summaries, and power an AI Q&A system that supports recall and reduces context-switching.

We spent 18 months building the product. Team of 12, SOC 2 certified, iOS and web shipped. 100% bootstrapped on $75K.

{Worth|Open to} a quick {call|intro}?

Mehul Patel
Co-founder, Clairify"""

C2_E2_SUBJECT = "Re: {Quick intro|Solving executive overload|Clairify}"
C2_E2_BODY = """\
Hi {FIRST_NAME},

{Wanted to|Looking to} explain why we started with MSPs.

MSPs are the proving ground. The pain is urgent, the compliance bar is high, and the market is massive ($650B, growing 14%). If we can solve executive intelligence here, it scales to professional services broadly.

Our team has deep MSP operator experience. We've lived the chaos of running a services business across dozens of disconnected tools. That's our unfair advantage.

Product is built. Now we need capital to sell.

{Does|Would} this make sense to {explore|discuss}?

Mehul"""

C2_E3_SUBJECT = "{Clairify // follow-up|Executive intelligence platform}"
C2_E3_BODY = """\
Hi {FIRST_NAME},

Following up on Clairify.

We're raising $2M on a SAFE ($10M cap) to scale GTM.

What we've built: executive intelligence layer for MSP leadership. Email integration live. Teams and Slack next. AI summaries and Q&A reduce overload and support decision-making.

Where we are: 18 months from idea to enterprise-ready. Team of 12. SOC 2 certified. 100% bootstrapped.

{Worth|Open to} a {call|quick chat}?

Mehul Patel
Co-founder, Clairify"""

C2_E4_SUBJECT = "{Last note|Final email}"
C2_E4_BODY = """\
Hi {FIRST_NAME},

Last email on Clairify.

Executive intelligence for MSP leadership. Reduces information overload, supports decision-making. $650B market.

Product is built. {Raising|Securing} $2M on a SAFE ($10M cap) to scale GTM.

If timing works, {happy|glad} to chat. If not, I'll {circle back|reach back} when it makes sense.

Mehul Patel
Co-founder, Clairify"""


# ===========================================================================
# CAMPAIGN 3 — "Capital-Efficient Execution"
# ===========================================================================

C3_NAME = "Clairify — Capital-Efficient Execution"

C3_E1_SUBJECT = "{Quick intro|Bootstrapped to SOC 2|Clairify}"
C3_E1_BODY = """\
Hi {FIRST_NAME},

We're raising $2M on a SAFE ($10M cap) to scale go-to-market.

We took Clairify from idea to enterprise-ready in 18 months on $75K of our own capital. Team of 12. SOC 2 Type 1 certified. iOS and web apps shipped.

Clairify is an executive intelligence platform for MSP leadership. We unify information streams, provide AI-powered summaries, and power a Q&A system for decision-making at scale.

The ~$650B MSP market is growing at ~14%, and AI pressure is forcing providers up the stack toward advisory. We're positioned in front of that shift.

Product is built. Now we need capital to sell.

{Worth|Open to} a quick {call|intro}?

Mehul Patel
Co-founder, Clairify"""

C3_E2_SUBJECT = "Re: {Quick intro|Bootstrapped to SOC 2|Clairify}"
C3_E2_BODY = """\
Hi {FIRST_NAME},

{Wanted to|Looking to} share why we're capital-efficient.

Our founding team combines MSP operator experience, product expertise, and AI execution talent. We know the problem deeply because we've lived it. That means less guessing, less waste.

We're not building frontier AI. We use proven models where they work best. The investor is paying for implementation of proven technology against real business insight.

We've proven we can build. Now we need capital to prove we can sell.

{Does|Would} this {fit|align with} what you're looking at?

Mehul"""

C3_E3_SUBJECT = "{Clairify // {FIRST_NAME}|Capital-efficient SaaS}"
C3_E3_BODY = """\
Hi {FIRST_NAME},

Following up on Clairify.

We're raising $2M on a SAFE ($10M cap) to scale GTM.

What we've built: enterprise-ready AI platform for MSP executives on $75K bootstrapped. SOC 2 certified. Team of 12. iOS and web shipped.

The market: $650B MSP market growing 14%. Product is built. Now we need capital to sell.

{Worth|Open to} a {call|quick chat}?

Mehul Patel
Co-founder, Clairify"""

C3_E4_SUBJECT = "{Last note|Final follow-up}"
C3_E4_BODY = """\
Hi {FIRST_NAME},

Last {note|email} on Clairify.

Bootstrapped to enterprise-ready in 18 months. SOC 2 certified. Team of 12. $650B market.

{Raising|Securing} $2M on a SAFE ($10M cap) to scale GTM.

If timing works, {happy|glad} to {walk you through|share} the product. If not, I'll {reach back|circle back} when it makes sense.

Mehul Patel
Co-founder, Clairify"""


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
        print(f"  ERROR: Failed to create campaign.")
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
        print("ERROR: CLAIRIFY_BISON_API_KEY not set in .env")
        sys.exit(1)

    print("Testing connection to Clairify workspace...")
    me = api_get("/users")
    if not me:
        print("ERROR: Could not authenticate. Check CLAIRIFY_BISON_API_KEY.")
        sys.exit(1)
    print("  Authenticated OK.\n")

    campaigns = api_get("/campaigns")
    existing = campaigns.get("data", campaigns) if isinstance(campaigns, dict) else campaigns
    if isinstance(existing, list):
        print(f"Existing campaigns in workspace: {len(existing)}")
        for c in existing[:5]:
            print(f"  - {c.get('name', c.get('id'))}")
        print()

    # -----------------------------------------------------------------------
    # Campaign 1 — Product Built, Now Scale
    # -----------------------------------------------------------------------
    print("=" * 60)
    c1_id = create_campaign(C1_NAME)
    if c1_id:
        add_step(c1_id, "Email 1 – Product Intro",
                 C1_E1_SUBJECT, C1_E1_BODY, wait_in_days=1, thread_reply=False)
        add_step(c1_id, "Email 2 – Why Raising Now",
                 C1_E2_SUBJECT, C1_E2_BODY, wait_in_days=3, thread_reply=True)
        add_step(c1_id, "Email 3 – Quick Summary (new thread)",
                 C1_E3_SUBJECT, C1_E3_BODY, wait_in_days=4, thread_reply=False)
        add_step(c1_id, "Email 4 – Last Note",
                 C1_E4_SUBJECT, C1_E4_BODY, wait_in_days=4, thread_reply=False)
    print()

    # -----------------------------------------------------------------------
    # Campaign 2 — The Information Overload Problem
    # -----------------------------------------------------------------------
    print("=" * 60)
    c2_id = create_campaign(C2_NAME)
    if c2_id:
        add_step(c2_id, "Email 1 – Overload Problem Intro",
                 C2_E1_SUBJECT, C2_E1_BODY, wait_in_days=1, thread_reply=False)
        add_step(c2_id, "Email 2 – Why MSPs",
                 C2_E2_SUBJECT, C2_E2_BODY, wait_in_days=3, thread_reply=True)
        add_step(c2_id, "Email 3 – Follow-Up (new thread)",
                 C2_E3_SUBJECT, C2_E3_BODY, wait_in_days=4, thread_reply=False)
        add_step(c2_id, "Email 4 – Last Note",
                 C2_E4_SUBJECT, C2_E4_BODY, wait_in_days=4, thread_reply=False)
    print()

    # -----------------------------------------------------------------------
    # Campaign 3 — Capital-Efficient Execution
    # -----------------------------------------------------------------------
    print("=" * 60)
    c3_id = create_campaign(C3_NAME)
    if c3_id:
        add_step(c3_id, "Email 1 – Capital Efficiency Intro",
                 C3_E1_SUBJECT, C3_E1_BODY, wait_in_days=1, thread_reply=False)
        add_step(c3_id, "Email 2 – Why Capital-Efficient",
                 C3_E2_SUBJECT, C3_E2_BODY, wait_in_days=3, thread_reply=True)
        add_step(c3_id, "Email 3 – Follow-Up (new thread)",
                 C3_E3_SUBJECT, C3_E3_BODY, wait_in_days=4, thread_reply=False)
        add_step(c3_id, "Email 4 – Last Note",
                 C3_E4_SUBJECT, C3_E4_BODY, wait_in_days=4, thread_reply=False)
    print()

    print("=" * 60)
    print("Done. All 3 campaigns created in the Clairify workspace.")
    print("Next steps for each campaign:")
    print("  1. Verify steps and copy look correct in the UI")
    print("  2. Add sender email accounts")
    print("  3. Configure sending schedule")
    print("  4. Import leads and launch")


if __name__ == "__main__":
    main()
