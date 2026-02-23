#!/usr/bin/env python3
"""Adds the two missing thread-reply steps (2 and 4) to existing Boardy campaign ID 256."""

import os, sys, time, requests
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("BOARDY_BISON_API_KEY", "")
BASE_URL = os.getenv("BOARDY_BISON_BASE_URL", "https://send.breakoutcreatives.com/api")
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json", "Content-Type": "application/json"}
CAMPAIGN_ID = 256


def api_post(path, body):
    url = f"{BASE_URL}/{path.lstrip('/')}"
    for attempt in range(4):
        try:
            resp = requests.post(url, headers=HEADERS, json=body, timeout=60)
            if resp.status_code == 429:
                time.sleep(2 ** (attempt + 1)); continue
            if not resp.ok:
                print(f"  HTTP {resp.status_code}: {resp.text[:400]}")
                return {}
            return resp.json()
        except requests.RequestException as exc:
            print(f"  POST error ({exc}), retrying..."); time.sleep(2 ** (attempt + 1))
    return {}


BODY_2 = """\
Hi {FIRST_NAME},

{Following up|Circling back} on my last note about Boardy Ventures - wanted to add some context on who's behind it.

Andrew D'Souza, our founder, {built|scaled} Clearco - {deploying|putting} $2.5B into 10,000 companies across 11 countries. He built Boardy to solve the relationship bottleneck he saw founders {hitting|running into} at every stage of growth.

Boardy Ventures is the natural extension of that. The platform already {talks to|speaks with} thousands of founders every month. The fund backs the ones where conviction is highest.

Would love to {continue the conversation|connect} if this {fits|aligns with} how you're thinking about allocation.

Tarik
Venture Partner @Boardy"""

BODY_4 = """\
Hi {FIRST_NAME},

No worries if this isn't of interest for you or your team right now.

Wondering if there's anyone in your network that might have an eye for this you could point me to?

Tarik
Venture Partner @Boardy"""


def main():
    if not API_KEY:
        print("ERROR: BOARDY_BISON_API_KEY not set"); sys.exit(1)

    print(f"Using API key: {API_KEY[:12]}...")
    print(f"Campaign ID: {CAMPAIGN_ID}\n")

    print("Adding Step 2 (Andrew context follow-up, Day 3-4, thread reply) ...")
    r2 = api_post(f"/campaigns/{CAMPAIGN_ID}/sequence-steps", {
        "title": "Email 2 – Andrew D'Souza Context",
        "sequence_steps": [{
            "email_subject": "Re: boardy ventures intro",
            "email_body":    BODY_2,
            "wait_in_days":  3,
            "thread_reply":  True,
        }]
    })
    if r2:
        print(f"  Step 2 added. Response: {str(r2)[:200]}")
    else:
        print("  FAILED — check errors above.")

    print("\nAdding Step 4 (Soft close / referral ask, Day 11-12, thread reply) ...")
    r4 = api_post(f"/campaigns/{CAMPAIGN_ID}/sequence-steps", {
        "title": "Email 4 – Soft Close",
        "sequence_steps": [{
            "email_subject": "Re: boardy // {FIRST_NAME} check-in",
            "email_body":    BODY_4,
            "wait_in_days":  4,
            "thread_reply":  True,
        }]
    })
    if r4:
        print(f"  Step 4 added. Response: {str(r4)[:200]}")
    else:
        print("  FAILED — check errors above.")

    print("\nDone.")


if __name__ == "__main__":
    main()
