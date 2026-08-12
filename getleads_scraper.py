#!/usr/bin/env python3
"""
GetLeads scraper: US private lending / commercial brokerage decision makers.

Pulls decision makers (C-Team, VP, Director) at commercial real estate
brokerages and private lending companies from the GetLeads contact index
(app.getleads.io), US only, excluding: North Dakota, South Dakota, Vermont,
Arizona, California, Minnesota, Nevada, Oregon, Utah. Valid emails only.

Usage:
    GETLEADS_API_KEY=glb_live_... python3 getleads_scraper.py [--target 3000]

Costs 1 GetLeads credit per record returned. Counts are free.
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import requests

BASE = "https://app.getleads.io/api/v1"

EXCLUDED_STATES = {
    "North Dakota", "South Dakota", "Vermont", "Arizona", "California",
    "Minnesota", "Nevada", "Oregon", "Utah",
}

# All US states + DC minus the exclusions (the API's `states` filter is an
# include-list with substring matching, so full names are required).
INCLUDED_STATES = [
    "Alabama", "Alaska", "Arkansas", "Colorado", "Connecticut", "Delaware",
    "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Mississippi",
    "Missouri", "Montana", "Nebraska", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "Ohio", "Oklahoma",
    "Pennsylvania", "Rhode Island", "South Carolina", "Tennessee", "Texas",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
]

COMMON_FILTERS = {
    "countries": ["United States"],
    "states": INCLUDED_STATES,
    "seniority": ["C-Team", "VP", "Director"],
    "email_status": ["VALID"],
}

# Ordered segments: lending first (small, most specific), then commercial
# brokerage (large) to fill the remainder of the target.
SEGMENTS = [
    ("lending-industries", {
        "industries": ["Loan Brokers", "Credit Intermediation"],
    }),
    ("private-lending-desc", {
        "industries": ["Financial Services", "Investment Management",
                        "Capital Markets", "Real Estate", "Banking"],
        "company_description": "private lending",
    }),
    ("hard-money-desc", {
        "company_description": "hard money",
    }),
    ("private-money-desc", {
        "company_description": "private money lend",
    }),
    ("bridge-lending-desc", {
        "industries": ["Financial Services", "Investment Management",
                        "Capital Markets", "Real Estate", "Banking"],
        "company_description": "bridge loan",
    }),
    ("commercial-brokerage", {
        "industries": ["Commercial Real Estate",
                        "Real Estate Agents and Brokers",
                        "Leasing Non-residential Real Estate"],
    }),
]

PAGE_SIZE = 1000
MAX_PER_COMPANY = 3


def api(session: requests.Session, path: str, body: dict) -> dict:
    for attempt in range(4):
        try:
            resp = session.post(f"{BASE}{path}", json=body, timeout=120)
            if resp.status_code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            print(f"  Request error ({exc}); retrying...")
            time.sleep(2 ** (attempt + 1))
    return {}


def pick(contact: dict, *names: str) -> str:
    for n in names:
        v = contact.get(n)
        if v:
            return str(v).strip()
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=3000)
    parser.add_argument("--output", default="output/lending_brokerage_dms.csv")
    args = parser.parse_args()

    key = os.getenv("GETLEADS_API_KEY", "")
    if not key:
        print("ERROR: set GETLEADS_API_KEY")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {key}",
                            "Content-Type": "application/json"})

    records: list[dict] = []
    seen_emails: set[str] = set()

    for name, extra in SEGMENTS:
        if len(records) >= args.target:
            break
        filters = {**COMMON_FILTERS, **extra}
        offset = 0
        print(f"\n--- Segment: {name} ---")
        while len(records) < args.target:
            body = {
                "filters": filters,
                "limit": min(PAGE_SIZE, args.target - len(records)),
                "offset": offset,
                "max_per_company": MAX_PER_COMPANY,
            }
            data = api(session, "/contacts/search", body)
            if data.get("credits_exhausted"):
                print(f"  CREDITS EXHAUSTED: {data.get('message', '')}")
                print("  Stopping — upgrade the GetLeads plan and re-run.")
                write_and_exit(records, args.output)
            contacts = data.get("contacts", [])
            if not contacts:
                break
            for c in contacts:
                email = pick(c, "email_address", "email").lower()
                if not email or email in seen_emails:
                    continue
                state = pick(c, "person_state", "state")
                if any(x.lower() in state.lower() for x in EXCLUDED_STATES):
                    continue  # belt-and-braces on top of the include-list
                seen_emails.add(email)
                records.append({
                    "first_name": pick(c, "first_name", "person_first_name"),
                    "last_name": pick(c, "last_name", "person_last_name"),
                    "title": pick(c, "job_title", "title"),
                    "company": pick(c, "org_company_name", "company_name"),
                    "email": email,
                    "state": state,
                    "linkedin_url": pick(c, "linkedin_url", "person_linkedin_url"),
                    "segment": name,
                })
            print(f"  offset {offset}: +{len(contacts)} fetched, "
                  f"total kept {len(records)}/{args.target} "
                  f"(credits left: {data.get('creditsRemaining')})")
            if not data.get("has_more"):
                break
            offset = data.get("next_offset", offset + len(contacts))

    write_and_exit(records, args.output)


def write_and_exit(records: list[dict], output: str) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["first_name", "last_name", "title", "company", "email",
              "state", "linkedin_url", "segment"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    print(f"\nWrote {len(records)} records to {path}")
    sys.exit(0)


if __name__ == "__main__":
    main()
