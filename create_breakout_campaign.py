#!/usr/bin/env python3
"""
Creates 'Breakout - fresh copy - 2026' campaign in EmailBison (Breakout workspace)
and adds 11 A/B copy variants for email step 1.
"""

import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BISON_API_KEY", "")
BASE_URL = "https://dedi.emailbison.com/api"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

CAMPAIGN_NAME = "Breakout - fresh copy - 2026"

# Subject line shared across all 11 variants (body-level A/B test)
SUBJECT = "Quick question"

# ---------------------------------------------------------------------------
# 11 body variants — all are A/B variations of email step 1
# ---------------------------------------------------------------------------
VARIANTS = [
    # 1
    """{FIRST_NAME},
Any chance you're looking to close a round sometime this year?
We work with a number of investment groups actively deploying into {NICHE} right now - some in the $1M-$20M range.
Happy to make some introductions if the timing lines up. Worth a quick chat?

Ryan Bryden | Breakout Capital Group
Toronto, Ontario

P.S. I'm sure your inbox is busy - shoot me a connection on linkedin so you know we're legit. Thanks.""",

    # 2
    """{FIRST_NAME},
Quick question - are you planning a raise in the next six months or so?
We do some sourcing work for a few funds with active mandates in {NICHE}. A few of them are looking to move in the next 1-2 quarters.
Open to a brief intro call to see if we can be helpful?

Ryan Bryden | Breakout Capital Group
Toronto, Ontario""",

    # 3
    """{FIRST_NAME},
Not sure if capital is on your radar right now, but a few of the investment groups we work with are actively looking at {NICHE} deals in the next few quarters.
If you're thinking about a raise, figured it might be worth a conversation.
Interested?

Ryan Bryden | Breakout Capital Group
Toronto, Ontario

P.S. I know email is crowded - I can send a connection request on LinkedIn to you as well so you know I'm real.""",

    # 4
    """{FIRST_NAME},
We're currently working with some North American and European investors looking to deploy into {NICHE} over the next few months - thought it might be relevant depending on where you are with fundraising.
Are you planning to raise anytime soon?

Ryan Bryden | Breakout Capital Group
Toronto, Ontario""",

    # 5
    """{FIRST_NAME},
A handful of funds we're sourcing for are allocating $2M-$25M into {NICHE} businesses over the next quarter or two.
Not sure if the timing is right for you, but if a raise is in the cards - we might be able to be helpful.
Worth a quick chat over the next week or two?

Ryan Bryden | Breakout Capital Group
Toronto, Ontario""",

    # 6
    """{FIRST_NAME},
Are you thinking about raising capital in the near term?
We have a few groups we source/scout for looking into deals specifically focused on {NICHE} over the next few months.
Would a quick intro call make sense or is this not relevant right now?

Ryan Bryden | Breakout Capital Group
Toronto, Ontario

P.S. We're an advisory firm based here in Toronto. Feel free to send me a connection request on LI so you know I'm a real human.""",

    # 7
    """{FIRST_NAME},
Are you planning a capital raise in the next quarter or two?
We do sourcing work for a handful of funds actively looking at {NICHE} businesses right now. A few have capital ready to deploy in the $3M-$20M range.
Happy to connect if the timing makes sense.

Ryan Bryden | Breakout Capital Group
Toronto, Ontario

P.S. Feel free to look me up on LinkedIn - happy to send a connection request so you know this is a real outreach.""",

    # 8
    """{FIRST_NAME},
Not sure if you're in fundraising mode, but wanted to reach out - we're currently scouting deals for a few investor groups with specific interest in {NICHE}.
If a raise is something you're thinking about in the next 6 months, it might be worth a quick conversation.
Is this relevant at all?

Ryan Bryden | Breakout Capital Group
Toronto, Ontario""",

    # 9
    """{FIRST_NAME},
We work with a number of North American and European funds that are actively allocating right now - several with a specific focus on {NICHE}.
Just wanted to see if fundraising is something on your radar in the near term.
If so, we might be able to make some useful introductions.
Worth a quick call?

Ryan Bryden | Breakout Capital Group
Toronto, Ontario""",

    # 10
    """{FIRST_NAME},
Any chance you're thinking about a raise this year?
We do sourcing and scouting work for a few investment groups - a handful of them are actively looking at {NICHE} deals and have mandates to deploy in the next couple of quarters.
If there's any overlap, happy to explore it.

Ryan Bryden | Breakout Capital Group
Toronto, Ontario

P.S. I'm happy to send a LinkedIn connection so you can see we're a legitimate firm. Cheers.""",

    # 11
    """{FIRST_NAME},
Quick one - are you planning to close a funding round anytime in the next 6-12 months?
We source deals for a group of funds with active interest in {NICHE}.
Some are looking to move in the $2M-$25M range over the next quarter or two.
If the timing lines up, might be worth a short conversation.

Ryan Bryden | Breakout Capital Group
Toronto, Ontario""",
]


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
        print("ERROR: BISON_API_KEY not set.")
        sys.exit(1)

    # --- 1. Test auth ---
    print("Testing connection...")
    me = api_get("/users")
    if not me:
        print("ERROR: Could not authenticate. Check BISON_API_KEY.")
        sys.exit(1)
    print(f"  Authenticated OK.\n")

    # --- 2. List current campaigns (sanity check / workspace confirmation) ---
    campaigns = api_get("/campaigns")
    existing = campaigns.get("data", campaigns) if isinstance(campaigns, dict) else campaigns
    if isinstance(existing, list):
        print(f"Existing campaigns in workspace: {len(existing)}")
        for c in existing[:5]:
            print(f"  - {c.get('name', c.get('id'))}")
        print()

    # --- 3. Create the campaign ---
    print(f"Creating campaign: '{CAMPAIGN_NAME}' ...")
    result = api_post("/campaigns", {"name": CAMPAIGN_NAME})
    if not result:
        print("ERROR: Failed to create campaign.")
        sys.exit(1)

    # The response may nest the campaign under a key or return it directly
    campaign = result.get("campaign", result.get("data", result))
    campaign_id = campaign.get("id") if isinstance(campaign, dict) else result.get("id")
    if not campaign_id:
        print(f"ERROR: Could not parse campaign ID from response: {result}")
        sys.exit(1)

    print(f"  Campaign created. ID: {campaign_id}\n")

    # --- 4. Build sequence_steps payload ---
    # Primary step (variant 1 = no variant flag)
    steps = [
        {
            "email_subject": SUBJECT,
            "email_body": VARIANTS[0],
            "wait_in_days": 0,
            "thread_reply": False,
            "order": 1,
        }
    ]

    # Variants 2-11 are A/B variants of step 1
    for body in VARIANTS[1:]:
        steps.append(
            {
                "email_subject": SUBJECT,
                "email_body": body,
                "wait_in_days": 0,
                "thread_reply": False,
                "order": 1,
                "variant": True,
                "variant_from_step": 1,
            }
        )

    # --- 5. POST the sequence steps ---
    print(f"Adding {len(steps)} email variants to campaign {campaign_id} ...")
    seq_result = api_post(
        f"/campaigns/{campaign_id}/sequence-steps",
        {"title": "Email 1", "sequence_steps": steps},
    )

    if seq_result:
        print(f"  Sequence steps added successfully.")
        print(f"  Response: {str(seq_result)[:300]}")
    else:
        print("  WARNING: Sequence step POST returned empty — check the campaign in the UI.")

    print(f"\nDone. Campaign '{CAMPAIGN_NAME}' is ready in EmailBison (ID: {campaign_id}).")
    print("Next steps:")
    print("  1. Add sender email accounts to the campaign")
    print("  2. Configure sending schedule")
    print("  3. Import leads and launch")


if __name__ == "__main__":
    main()
