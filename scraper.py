#!/usr/bin/env python3
"""
Philippines Founders Scraper (Free — No API Keys Required)
==========================================================
Scrapes founders/owners/managers of Philippines-based companies (10-500 employees)
from free public business directories. Outputs CSV with first_name, last_name,
company, email.

Primary source: BusinessList.ph (214,000+ companies with contact details)

Usage:
    python3 scraper.py [--target 5000] [--output output/ph_founders.csv]
    python3 scraper.py --resume          # resume from last checkpoint
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = "https://www.businesslist.ph"
OUTPUT_DIR = Path("output")
CHECKPOINT_FILE = OUTPUT_DIR / ".checkpoint.json"

# Philippine cities ordered by business count
LOCATIONS = [
    "manila",
    "quezon-city",
    "makati",
    "pasig",
    "taguig",
    "mandaluyong",
    "cebu-city",
    "davao-city",
    "pasay",
    "paranaque",
    "san-juan",
    "caloocan",
    "valenzuela",
    "muntinlupa",
    "las-pinas",
    "marikina",
    "malabon",
    "navotas",
    "pateros",
    "antipolo",
    "cainta",
    "taytay",
    "bacoor",
    "imus",
    "dasmarinas",
    "general-trias",
    "cavite-city",
    "san-pedro",
    "binan",
    "santa-rosa",
    "cabuyao",
    "calamba",
    "angeles-city",
    "san-fernando",
    "olongapo",
    "subic",
    "baguio",
    "iloilo-city",
    "bacolod",
    "cagayan-de-oro",
    "zamboanga-city",
    "general-santos",
    "butuan",
    "tacloban",
    "legazpi",
    "naga",
    "lipa",
    "batangas-city",
    "lucena",
    "puerto-princesa",
    "tagbilaran",
    "dumaguete",
    "roxas",
    "pagadian",
    "iligan",
    "surigao",
    "tuguegarao",
    "santiago",
    "cauayan",
    "san-jose",
    "cabanatuan",
    "meycauayan",
    "malolos",
]

# Employee ranges we want (10-500)
VALID_EMPLOYEE_RANGES = {
    "1-10", "2-10", "5-10",
    "10-50", "11-50", "10-20", "11-20",
    "20-50", "21-50",
    "50-100", "51-100", "50-200", "51-200",
    "100-200", "101-200",
    "200-500", "201-500",
    "100-500", "101-500",
}

# Friendly headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def polite_sleep(min_s: float = 1.0, max_s: float = 3.0):
    """Random delay to be polite to servers."""
    time.sleep(random.uniform(min_s, max_s))


def is_valid_name(name: str) -> bool:
    """Check if a string looks like a real person name."""
    if not name or len(name) < 2:
        return False
    # Reject if it looks like an email
    if "@" in name:
        return False
    # Reject if it contains URLs
    if "http" in name.lower() or "www." in name.lower():
        return False
    # Reject common non-name values (substring match)
    lower = name.strip().lower()
    bad_exact = ["n/a", "none", "not available", "tba", "tbd",
                 "admin", "administrator", "management", "staff", "team"]
    if lower in bad_exact:
        return False
    bad_prefix = ["closed", "temporarily", "permanently", "under construction"]
    if any(lower.startswith(b) for b in bad_prefix):
        return False
    # Reject if starts with a year or number
    if re.match(r"^\d", name):
        return False
    # Must contain at least 2 alphabetic characters
    if len(re.findall(r"[a-zA-Z]", name)) < 2:
        return False
    return True


def parse_name(full_name: str) -> tuple[str, str]:
    """Split a full name into (first_name, last_name)."""
    full_name = re.sub(r"\s+", " ", full_name).strip()
    # Remove common prefixes
    full_name = re.sub(r"^(Dr\.?|Engr\.?|Atty\.?|Mr\.?|Mrs\.?|Ms\.?)\s+",
                       "", full_name, flags=re.IGNORECASE).strip()
    # Remove common suffixes
    full_name = re.sub(r",?\s*(Jr\.?|Sr\.?|III|II|IV)$", "", full_name, flags=re.IGNORECASE).strip()

    if not is_valid_name(full_name):
        return ("", "")

    parts = full_name.split()
    if len(parts) == 0:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], " ".join(parts[1:]))


def employee_range_matches(emp_text: str) -> bool:
    """Check if the employee range text indicates 10-500 employees."""
    emp_text = emp_text.strip().lower().replace(" ", "")

    # Try to extract numbers
    numbers = re.findall(r"\d+", emp_text)
    if len(numbers) >= 2:
        lo, hi = int(numbers[0]), int(numbers[1])
        # Accept if the range overlaps with 10-500
        return lo >= 10 and hi <= 500
    elif len(numbers) == 1:
        n = int(numbers[0])
        return 10 <= n <= 500

    # Check against known range strings
    return emp_text in VALID_EMPLOYEE_RANGES


def fetch_page(session: requests.Session, url: str) -> BeautifulSoup | None:
    """Fetch a page and return parsed BeautifulSoup, with retry logic."""
    for attempt in range(4):
        try:
            resp = session.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"    Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as exc:
            wait = 2 ** (attempt + 1)
            print(f"    Request error ({exc}). Retrying in {wait}s...")
            time.sleep(wait)
    return None


# ---------------------------------------------------------------------------
# BusinessList.ph Scraper
# ---------------------------------------------------------------------------
class BusinessListScraper:
    """Scrapes company listings from BusinessList.ph."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_listing_urls(self, location: str, page: int = 1) -> list[str]:
        """Get company detail page URLs from a location listing page."""
        url = f"{BASE_URL}/location/{location}/{page}" if page > 1 else f"{BASE_URL}/location/{location}"
        soup = fetch_page(self.session, url)
        if not soup:
            return []

        urls = []
        # Company links follow pattern: /company/{id}/{slug} (relative) or full businesslist.ph URL
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Only match businesslist.ph company links
            if href.startswith("/company/") and re.match(r"/company/\d+/", href):
                full_url = BASE_URL + href
                if full_url not in urls:
                    urls.append(full_url)
            elif "businesslist.ph/company/" in href and re.search(r"/company/\d+/", href):
                if href not in urls:
                    urls.append(href)
        return urls

    def scrape_company(self, url: str) -> dict | None:
        """Scrape a single company detail page for founder info."""
        soup = fetch_page(self.session, url)
        if not soup:
            return None

        record = {
            "first_name": "",
            "last_name": "",
            "company": "",
            "email": "",
            "title": "",
            "employee_range": "",
            "source_url": url,
        }

        page_text = soup.get_text()
        raw_html = str(soup)
        contact_name = ""

        # --- Extract company name from h1, clean location suffix ---
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True)
            # Remove " - City, Philippines" suffix
            name = re.sub(r"\s*-\s*[A-Z][a-zA-Z\s,]+Philippines$", "", name).strip()
            record["company"] = name

        # --- Method 1: BusinessList.ph div.info > div.label structure ---
        for info_div in soup.find_all("div", class_="info"):
            label_div = info_div.find("div", class_="label")
            if not label_div:
                continue
            label = label_div.get_text(strip=True).lower()
            # Value = info text minus the label text
            value = info_div.get_text(strip=True)
            value = value[len(label_div.get_text(strip=True)):].strip()

            if any(k in label for k in ["manager", "contact person", "owner",
                                         "director", "principal", "representative",
                                         "founder", "ceo", "proprietor"]):
                contact_name = value
                if "manager" in label:
                    record["title"] = "Manager"
                elif "owner" in label:
                    record["title"] = "Owner"
                elif "director" in label:
                    record["title"] = "Director"
                elif "founder" in label:
                    record["title"] = "Founder"
                elif "ceo" in label:
                    record["title"] = "CEO"
                elif "proprietor" in label:
                    record["title"] = "Proprietor"
                else:
                    record["title"] = "Contact Person"

            elif "employee" in label:
                record["employee_range"] = value

        # --- Method 2: Fallback — dt/dd, th/td, strong/span pairs ---
        if not contact_name:
            for dt in soup.find_all(["dt", "th", "strong", "b", "label"]):
                label = dt.get_text(strip=True).lower()
                value_el = dt.find_next_sibling(["dd", "td", "span", "div", "p"])
                if not value_el:
                    value_el = dt.find_next(["dd", "td", "span"])
                if not value_el:
                    continue
                value = value_el.get_text(strip=True)

                if any(k in label for k in ["contact person", "manager", "owner",
                                             "director", "founder", "ceo",
                                             "proprietor"]):
                    contact_name = value

                elif not record["employee_range"] and ("employee" in label or "staff" in label):
                    record["employee_range"] = value

        # --- Email extraction ---
        # Try mailto links first
        mailto = soup.find("a", href=re.compile(r"mailto:", re.IGNORECASE))
        if mailto:
            record["email"] = mailto["href"].split("mailto:")[-1].split("?")[0].strip()

        # Regex scan of raw HTML for emails (catches obfuscated/hidden ones)
        if not record["email"]:
            emails = re.findall(
                r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
                raw_html,
            )
            for em in emails:
                em_lower = em.lower()
                if not any(skip in em_lower for skip in [
                    "businesslist", "example.com", "sentry", "noreply",
                    "wixpress", "schema.org", "w3.org", "googleapis",
                ]):
                    record["email"] = em
                    break

        # --- Contact name fallback: regex in page text ---
        if not contact_name:
            patterns = [
                r"(?:Contact\s+Person|Manager|Owner|Director|Founder|CEO|Proprietor)\s*[:\-–]\s*([A-Z][a-zA-Z.]+(?:\s+[A-Z][a-zA-Z.]+){1,4})",
                r"(?:managed?\s+by|owned?\s+by|founded?\s+by)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,3})",
            ]
            for pat in patterns:
                m = re.search(pat, page_text)
                if m:
                    contact_name = m.group(1).strip()
                    break

        # --- Employee count fallback: regex in page text ---
        if not record["employee_range"]:
            m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(?:employees|staff|workers|people)",
                          page_text, re.IGNORECASE)
            if m:
                record["employee_range"] = m.group(0).strip()

        # --- Parse contact name into first/last ---
        if contact_name:
            first, last = parse_name(contact_name)
            record["first_name"] = first
            record["last_name"] = last

        return record

    def _process_record(self, record: dict) -> dict | None:
        """Validate and filter a scraped record. Returns cleaned dict or None."""
        if not record or not record["first_name"]:
            return None

        # Filter: employee range must be 10-500 (if available)
        if record["employee_range"]:
            if not employee_range_matches(record["employee_range"]):
                return None

        return {
            "first_name": record["first_name"],
            "last_name": record["last_name"],
            "company": record["company"],
            "email": record["email"],
            "title": record["title"],
        }

    def scrape(self, target: int = 5000, resume_state: dict | None = None,
               workers: int = 3) -> list[dict]:
        """Main scrape loop with concurrent workers for detail pages."""
        results = []
        seen_companies = set()
        total_scraped = 0
        lock = Lock()

        # Resume from checkpoint if available
        start_loc_idx = 0
        start_page = 1
        if resume_state:
            results = resume_state.get("results", [])
            seen_companies = set(resume_state.get("seen_companies", []))
            start_loc_idx = resume_state.get("location_idx", 0)
            start_page = resume_state.get("page", 1)
            print(f"  Resuming: {len(results)} records, "
                  f"location={start_loc_idx}, page={start_page}")

        def scrape_one(url: str) -> dict | None:
            """Scrape one company page (called from thread pool)."""
            polite_sleep(0.5, 1.5)
            return self.scrape_company(url)

        for loc_idx in range(start_loc_idx, len(LOCATIONS)):
            location = LOCATIONS[loc_idx]
            page = start_page if loc_idx == start_loc_idx else 1
            consecutive_empty = 0

            print(f"\n--- {location} ---")

            while len(results) < target:
                print(f"  pg {page} | {len(results)}/{target} collected | {total_scraped} scraped")

                company_urls = self.get_listing_urls(location, page)

                if not company_urls:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                    page += 1
                    polite_sleep(1.0, 2.0)
                    continue

                consecutive_empty = 0

                # Filter to unseen URLs
                new_urls = []
                for url in company_urls:
                    key = url.split("/company/")[-1] if "/company/" in url else url
                    if key not in seen_companies:
                        seen_companies.add(key)
                        new_urls.append(url)

                # Scrape company pages concurrently
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {pool.submit(scrape_one, url): url for url in new_urls}

                    for future in as_completed(futures):
                        total_scraped += 1
                        try:
                            raw = future.result()
                        except Exception:
                            continue

                        cleaned = self._process_record(raw)
                        if cleaned:
                            results.append(cleaned)

                        if len(results) >= target:
                            break

                # Checkpoint every page
                if len(results) % 20 == 0 or page % 5 == 0:
                    save_checkpoint({
                        "results": results,
                        "seen_companies": list(seen_companies),
                        "location_idx": loc_idx,
                        "page": page,
                    })

                page += 1
                polite_sleep(0.5, 1.5)

            if len(results) >= target:
                break

        # Final checkpoint
        save_checkpoint({
            "results": results,
            "seen_companies": list(seen_companies),
            "location_idx": loc_idx if 'loc_idx' in dir() else 0,
            "page": page if 'page' in dir() else 1,
        })
        return results


# ---------------------------------------------------------------------------
# Checkpoint save/load
# ---------------------------------------------------------------------------
def save_checkpoint(state: dict):
    """Save scraper state for resuming."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f)


def load_checkpoint() -> dict | None:
    """Load scraper state if available."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return None


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
    """Print a summary of collected data."""
    total = len(records)
    with_email = sum(1 for r in records if r.get("email"))
    with_company = sum(1 for r in records if r.get("company"))
    with_full_name = sum(1 for r in records if r.get("first_name") and r.get("last_name"))
    print("\n========== SUMMARY ==========")
    print(f"Total records:       {total}")
    print(f"With full name:      {with_full_name} ({100*with_full_name/max(total,1):.1f}%)")
    print(f"With email:          {with_email} ({100*with_email/max(total,1):.1f}%)")
    print(f"With company name:   {with_company} ({100*with_company/max(total,1):.1f}%)")
    print("=============================")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Scrape Philippines-based founders (10-500 employees) from free directories"
    )
    parser.add_argument(
        "--target", type=int, default=5000,
        help="Target number of records (default: 5000)",
    )
    parser.add_argument(
        "--output", type=str, default="output/ph_founders.csv",
        help="Output CSV path (default: output/ph_founders.csv)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from last checkpoint",
    )
    parser.add_argument(
        "--workers", type=int, default=3,
        help="Number of concurrent scrapers (default: 3, max: 5)",
    )
    args = parser.parse_args()
    args.workers = min(args.workers, 5)

    print("=" * 55)
    print("  Philippines Founders Scraper (Free Edition)")
    print(f"  Target: {args.target} records")
    print(f"  Workers: {args.workers} concurrent")
    print(f"  Source: BusinessList.ph (214K+ companies)")
    print("=" * 55)

    # Load checkpoint if resuming
    resume_state = None
    if args.resume:
        resume_state = load_checkpoint()
        if resume_state:
            print(f"\nResuming from checkpoint ({len(resume_state.get('results', []))} records)...")
        else:
            print("\nNo checkpoint found. Starting fresh.")

    # Scrape
    print("\n[Scraping] BusinessList.ph company profiles...")
    scraper = BusinessListScraper()
    records = scraper.scrape(target=args.target, resume_state=resume_state,
                             workers=args.workers)

    # Output
    print_summary(records)
    write_csv(records, Path(args.output))

    # Clean up checkpoint on success
    if len(records) >= args.target and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        print("Checkpoint file removed (target reached).")

    if len(records) < args.target:
        print(f"\nCollected {len(records)}/{args.target}.")
        print("Run with --resume to continue from where you left off.")


if __name__ == "__main__":
    main()
