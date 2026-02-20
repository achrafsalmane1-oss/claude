#!/usr/bin/env python3
"""
Philippines Founders Scraper
=============================
Scrapes founders/CEOs of Philippines-based companies (10-500 employees)
from B2B data APIs. Outputs CSV with first_name, last_name, company, email.

Primary source: Apollo.io API (free tier: 10,000 credits/month)
Fallback:       Hunter.io API (optional, for email enrichment)

Usage:
    1. Copy .env.example to .env and add your API key(s)
    2. python3 scraper.py [--target 5000] [--output founders.csv]
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
BISON_API_KEY = os.getenv("BISON_API_KEY", "")

APOLLO_SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"

# Titles that indicate a founder / top executive
FOUNDER_TITLES = [
    "founder",
    "co-founder",
    "cofounder",
    "ceo",
    "chief executive officer",
    "owner",
    "managing director",
    "president",
]

# Apollo employee range codes for 10-500
EMPLOYEE_RANGES = [
    "11,20",
    "21,50",
    "51,100",
    "101,200",
    "201,500",
]

OUTPUT_DIR = Path("output")


# ---------------------------------------------------------------------------
# Apollo.io scraper
# ---------------------------------------------------------------------------
class ApolloScraper:
    """Fetches founder records from Apollo.io people search API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def search_people(self, page: int = 1, per_page: int = 100,
                      title_keywords: list | None = None,
                      employee_ranges: list | None = None) -> dict:
        """Run a single people-search request against Apollo."""
        payload = {
            "api_key": self.api_key,
            "page": page,
            "per_page": per_page,
            "person_locations": ["Philippines"],
            "person_titles": title_keywords or FOUNDER_TITLES,
            "organization_num_employees_ranges": employee_ranges or EMPLOYEE_RANGES,
            "contact_email_status": ["verified", "guessed", "unavailable"],
        }

        for attempt in range(4):
            try:
                resp = self.session.post(APOLLO_SEARCH_URL, json=payload, timeout=30)
                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    print(f"  Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                wait = 2 ** (attempt + 1)
                print(f"  Request error ({exc}). Retrying in {wait}s...")
                time.sleep(wait)

        return {}

    def scrape_all(self, target: int = 5000,
                   per_page: int = 100) -> list[dict]:
        """Paginate through Apollo results until we hit the target count."""
        results = []
        seen_ids = set()
        page = 1

        # We cycle through different title keywords to maximize unique results
        title_groups = [
            ["founder", "co-founder", "cofounder"],
            ["ceo", "chief executive officer"],
            ["owner"],
            ["managing director"],
            ["president"],
        ]

        for titles in title_groups:
            page = 1
            consecutive_empty = 0
            label = ", ".join(titles)
            print(f"\n--- Searching titles: {label} ---")

            while len(results) < target:
                print(f"  Page {page} | Collected so far: {len(results)}/{target}")
                data = self.search_people(page=page, per_page=per_page,
                                          title_keywords=titles)

                people = data.get("people", [])
                if not people:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        print(f"  No more results for [{label}].")
                        break
                    page += 1
                    continue

                consecutive_empty = 0
                pagination = data.get("pagination", {})
                total_pages = pagination.get("total_pages", page)

                for person in people:
                    pid = person.get("id")
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)

                    first = (person.get("first_name") or "").strip()
                    last = (person.get("last_name") or "").strip()
                    email = (person.get("email") or "").strip()
                    org = person.get("organization", {}) or {}
                    company = (org.get("name") or "").strip()

                    if not first or not last:
                        continue

                    results.append({
                        "first_name": first,
                        "last_name": last,
                        "company": company,
                        "email": email,
                        "title": (person.get("title") or "").strip(),
                    })

                if page >= total_pages:
                    print(f"  Reached last page ({total_pages}) for [{label}].")
                    break

                page += 1
                # Respect rate limits
                time.sleep(1)

            if len(results) >= target:
                break

        return results


# ---------------------------------------------------------------------------
# Hunter.io email enrichment (optional)
# ---------------------------------------------------------------------------
class HunterEnricher:
    """Attempts to find emails via Hunter.io for records missing them."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def find_email(self, first_name: str, last_name: str,
                   company: str) -> str | None:
        """Use Hunter email-finder to locate an email."""
        if not company:
            return None

        url = "https://api.hunter.io/v2/email-finder"
        params = {
            "company": company,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": self.api_key,
        }

        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code == 429:
                    time.sleep(2 ** (attempt + 1))
                    continue
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return data.get("email")
                return None
            except requests.RequestException:
                time.sleep(2 ** (attempt + 1))

        return None

    def enrich(self, records: list[dict], limit: int | None = None) -> int:
        """Fill in missing emails using Hunter. Returns count of emails found."""
        missing = [r for r in records if not r.get("email")]
        if limit:
            missing = missing[:limit]

        found = 0
        total = len(missing)
        for i, record in enumerate(missing, 1):
            print(f"  Hunter enrichment {i}/{total}...", end="\r")
            email = self.find_email(
                record["first_name"], record["last_name"], record["company"]
            )
            if email:
                record["email"] = email
                found += 1
            time.sleep(0.5)  # rate limit

        print()
        return found


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------
def write_csv(records: list[dict], filepath: Path) -> None:
    """Write records to CSV."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["first_name", "last_name", "company", "email", "title"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"\nWrote {len(records)} records to {filepath}")


def print_summary(records: list[dict]) -> None:
    """Print a quick summary of collected data."""
    total = len(records)
    with_email = sum(1 for r in records if r.get("email"))
    with_company = sum(1 for r in records if r.get("company"))
    print("\n========== SUMMARY ==========")
    print(f"Total records:       {total}")
    print(f"With email:          {with_email} ({100*with_email/max(total,1):.1f}%)")
    print(f"With company name:   {with_company} ({100*with_company/max(total,1):.1f}%)")
    print("=============================")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Scrape Philippines-based founders (10-500 employees)"
    )
    parser.add_argument(
        "--target", type=int, default=5000,
        help="Target number of records to collect (default: 5000)",
    )
    parser.add_argument(
        "--output", type=str, default="output/ph_founders.csv",
        help="Output CSV path (default: output/ph_founders.csv)",
    )
    parser.add_argument(
        "--enrich", action="store_true",
        help="Use Hunter.io to fill in missing emails (requires HUNTER_API_KEY)",
    )
    parser.add_argument(
        "--enrich-limit", type=int, default=None,
        help="Max records to attempt Hunter enrichment on",
    )
    parser.add_argument(
        "--bison", action="store_true",
        help="Upload collected leads to EmailBison (requires BISON_API_KEY)",
    )
    parser.add_argument(
        "--bison-list", type=str, default="PH Founders",
        help="EmailBison list name for bulk upload (default: 'PH Founders')",
    )
    args = parser.parse_args()

    # Validate API keys
    if not APOLLO_API_KEY:
        print("ERROR: APOLLO_API_KEY not set. See .env.example for setup instructions.")
        sys.exit(1)

    print("=" * 50)
    print("Philippines Founders Scraper")
    print(f"Target: {args.target} records")
    print("=" * 50)

    # Phase 1: Apollo scrape
    print("\n[Phase 1] Scraping from Apollo.io...")
    apollo = ApolloScraper(APOLLO_API_KEY)
    records = apollo.scrape_all(target=args.target)
    print(f"\nCollected {len(records)} records from Apollo.")

    # Phase 2: Hunter enrichment (optional)
    if args.enrich and HUNTER_API_KEY:
        print("\n[Phase 2] Enriching missing emails via Hunter.io...")
        hunter = HunterEnricher(HUNTER_API_KEY)
        found = hunter.enrich(records, limit=args.enrich_limit)
        print(f"Hunter found {found} additional emails.")
    elif args.enrich and not HUNTER_API_KEY:
        print("\nSkipping Hunter enrichment (HUNTER_API_KEY not set).")

    # Phase 3: EmailBison upload (optional)
    if args.bison:
        if BISON_API_KEY:
            print("\n[Phase 3] Uploading leads to EmailBison...")
            from bison_client import BisonClient
            bison = BisonClient(BISON_API_KEY)
            if bison.test_connection():
                bison.bulk_upload_leads(records, list_name=args.bison_list)
            else:
                print("Skipping EmailBison upload (connection failed).")
        else:
            print("\nSkipping EmailBison upload (BISON_API_KEY not set).")

    # Output
    print_summary(records)
    write_csv(records, Path(args.output))

    if len(records) < args.target:
        print(f"\nNote: Collected {len(records)}/{args.target}. To get more results:")
        print("  - Ensure your Apollo.io plan has sufficient credits")
        print("  - Run again (the API may surface new results over time)")
        print("  - Consider upgrading to a paid Apollo.io plan for deeper access")


if __name__ == "__main__":
    main()
