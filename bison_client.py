#!/usr/bin/env python3
"""
EmailBison API Client
=====================
Connects to the EmailBison platform to manage leads and campaigns.

Authentication: Bearer token via Authorization header.
Base URL: https://dedi.emailbison.com/api

Usage:
    from bison_client import BisonClient
    client = BisonClient(api_key="YOUR_API_KEY")
    client.test_connection()
"""

import csv
import io
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

BISON_BASE_URL = "https://dedi.emailbison.com/api"


class BisonClient:
    """Client for the EmailBison API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = BISON_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a GET request with retry logic."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        for attempt in range(4):
            try:
                resp = self.session.get(url, params=params, timeout=30)
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

    def _post(self, endpoint: str, data: dict | None = None) -> dict:
        """Make a POST request with retry logic."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        for attempt in range(4):
            try:
                resp = self.session.post(url, json=data, timeout=30)
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

    # ------------------------------------------------------------------
    # Connection / auth
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        """Test API connectivity by fetching the current user info.

        Returns True if authentication succeeds.
        """
        result = self._get("/users")
        if result:
            print("[Bison] Connection successful.")
            return True
        print("[Bison] Connection failed — check your API key.")
        return False

    # ------------------------------------------------------------------
    # Leads
    # ------------------------------------------------------------------

    def list_leads(self, page: int = 1) -> dict:
        """Return a paginated list of leads."""
        return self._get("/leads", params={"page": page})

    def create_lead(
        self,
        first_name: str,
        last_name: str,
        email: str,
        company: str = "",
        title: str = "",
    ) -> dict:
        """Create a single lead.

        Required: first_name, last_name, email.
        """
        payload: dict = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
        }
        if company:
            payload["company"] = company
        if title:
            payload["title"] = title
        return self._post("/leads", data=payload)

    def bulk_upload_leads(
        self,
        records: list[dict],
        list_name: str = "PH Founders",
    ) -> dict:
        """Upload leads in bulk via CSV (up to 50,000 per batch).

        Each record should have: first_name, last_name, email, company, title.
        Records without an email address are skipped.
        """
        valid = [r for r in records if r.get("email")]
        if not valid:
            print("[Bison] No records with email addresses to upload.")
            return {}

        # Build CSV in memory
        buf = io.StringIO()
        fieldnames = ["first_name", "last_name", "email", "company", "title"]
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for record in valid:
            writer.writerow({f: record.get(f, "") for f in fieldnames})
        csv_bytes = buf.getvalue().encode("utf-8")

        url = f"{self.base_url}/leads/bulk/csv"
        # NOTE: do NOT set Content-Type here — requests sets it automatically
        #       when uploading multipart/form-data.
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        files = {"file": ("leads.csv", csv_bytes, "text/csv")}
        form_data = {
            "list_name": list_name,
            "columnsToMap[first_name][]": "first_name",
            "columnsToMap[last_name][]": "last_name",
            "columnsToMap[email][]": "email",
            "columnsToMap[company][]": "company",
            "columnsToMap[title][]": "title",
        }

        for attempt in range(4):
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    files=files,
                    data=form_data,
                    timeout=120,
                )
                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    print(f"  Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                result = resp.json()
                print(f"[Bison] Uploaded {len(valid)} leads to list '{list_name}'.")
                return result
            except requests.RequestException as exc:
                wait = 2 ** (attempt + 1)
                print(f"  Request error ({exc}). Retrying in {wait}s...")
                time.sleep(wait)
        return {}

    # ------------------------------------------------------------------
    # Campaigns
    # ------------------------------------------------------------------

    def list_campaigns(self) -> list:
        """Return all campaigns in the workspace."""
        result = self._get("/campaigns")
        if isinstance(result, dict):
            return result.get("data", [])
        return result if isinstance(result, list) else []

    def add_lead_to_campaign(self, campaign_id: str, lead_email: str) -> dict:
        """Add an existing lead to a campaign by email address."""
        return self._post(
            f"/campaigns/{campaign_id}/leads",
            data={"email": lead_email},
        )

    # ------------------------------------------------------------------
    # Master Inbox
    # ------------------------------------------------------------------

    def get_replies(self, lead_email: str | None = None) -> dict:
        """Fetch replies from the Master Inbox, optionally filtered by lead email."""
        params = {}
        if lead_email:
            params["email"] = lead_email
        return self._get("/master-inbox", params=params or None)


# ---------------------------------------------------------------------------
# CLI helper — run directly to verify credentials
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    api_key = os.getenv("BISON_API_KEY", "")
    if not api_key:
        print("ERROR: BISON_API_KEY not set in environment / .env file.")
        raise SystemExit(1)

    client = BisonClient(api_key)
    if client.test_connection():
        print("\nCampaigns:")
        for campaign in client.list_campaigns():
            print(f"  - {campaign.get('name', campaign.get('id', 'unknown'))}")
    else:
        raise SystemExit(1)
