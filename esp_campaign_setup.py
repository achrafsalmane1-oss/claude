#!/usr/bin/env python3
"""
Business Sergeant - ESP Campaign Split Setup
Creates Google and Outlook versions of each campaign,
updates email signatures, and filters leads by ESP tag.
"""

import requests
import json
import csv
import time
import os
from collections import defaultdict

API_BASE = "https://send.ottoresults.com/api"
TOKEN = "230|GAOm2ewVrhSBmestue65g7X8i81qkvLnYAOc6Kmv2a6bbcdb"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ESP Tag IDs
OUTLOOK_TAG_ID = 1238
NON_OUTLOOK_TAG_IDS = {1237, 1239, 1240, 1241, 1242, 1243}  # Google, Zoho, Custom, Proofpoint, Mimecast, Barracuda

# Proper signature HTML
SIGNATURE_HTML = (
    "<p>{Best|All the best|Cheers|Talk soon|Best regards}<br>"
    "Michael Kracyla<br>"
    "President &amp; Co-Founder | Business Sergeant</p>"
)

# Old signature patterns to replace
OLD_SIGNATURES = [
    "<p>Michael Kracyla | President &amp; Co-Founder @ Business Sergeant</p>",
    "<p>Michael Kracyla | President &amp; Co-Founder @ Business Sergeant</p><p><br></p>",
    # Partial signature in campaign 843 step 1
    '<div><div><pre>\n{Best|All the best|Cheers|Talk soon|Best regards}</pre></div></div>',
    '<div><div><pre>{Best|All the best|Cheers|Talk soon|Best regards}</pre></div></div>',
]


def api_get(path, params=None):
    url = f"{API_BASE}/{path}"
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()


def api_post(path, data):
    url = f"{API_BASE}/{path}"
    resp = requests.post(url, headers=HEADERS, json=data)
    resp.raise_for_status()
    return resp.json()


def api_delete(path, data=None):
    url = f"{API_BASE}/{path}"
    resp = requests.delete(url, headers=HEADERS, json=data)
    resp.raise_for_status()
    return resp.json()


def fix_signature(body: str) -> str:
    """Replace old signature with proper rotating signature."""
    # Try each old signature pattern
    for old_sig in OLD_SIGNATURES:
        if old_sig in body:
            return body.replace(old_sig, SIGNATURE_HTML)

    # If none matched, append signature (fallback)
    # Check if it ends with old inline format
    if "Michael Kracyla | President" in body:
        # Find and replace the paragraph containing the old signature
        import re
        body = re.sub(
            r'<p>Michael Kracyla \| President &amp; Co-Founder @ Business Sergeant<\/p>(\s*<p><br><\/p>)?',
            SIGNATURE_HTML,
            body
        )
    return body


def get_sequence_steps(campaign_id: int) -> list:
    """Get email sequence steps for a campaign."""
    data = api_get(f"campaigns/{campaign_id}/sequence-steps")
    return data.get("data", [])


def create_campaign(name: str) -> dict:
    """Create a new campaign."""
    result = api_post("campaigns", {
        "name": name,
        "type": "outbound",
        "plain_text": True,
        "open_tracking": False,
        "include_auto_replies_in_stats": True,
        "sequence_prioritization": "followups",
    })
    return result["data"]


def create_sequence_for_campaign(campaign_id: int, title: str, steps: list) -> dict:
    """Create a new email sequence for a campaign with proper signatures."""
    updated_steps = []
    for step in steps:
        updated_body = fix_signature(step["email_body"])
        step_data = {
            "email_subject": step["email_subject"],
            "email_body": updated_body,
            "wait_in_days": step.get("wait_in_days", 1),
        }
        if step.get("variant") and step.get("variant_from_step"):
            step_data["variant"] = True
            step_data["variant_from_step"] = step["variant_from_step"]
        updated_steps.append(step_data)

    result = api_post(f"campaigns/{campaign_id}/sequence-steps", {
        "title": title,
        "sequence_steps": updated_steps,
    })
    return result.get("data", {})


def fetch_all_leads_paginated():
    """
    Fetch all leads from the global /api/leads endpoint.
    Returns list of leads with their ESP tags and campaign associations.
    """
    print("Fetching all leads (this may take a few minutes)...")
    all_leads = []
    page = 1
    total_pages = None

    while True:
        data = api_get("leads", params={"page": page, "per_page": 15})
        leads = data.get("data", [])
        meta = data.get("meta", {})

        if total_pages is None:
            total_pages = meta.get("last_page", 1)
            print(f"  Total leads: {meta.get('total')}, pages: {total_pages}")

        all_leads.extend(leads)

        if page % 50 == 0:
            print(f"  Fetched page {page}/{total_pages} ({len(all_leads)} leads so far)...")

        if page >= total_pages:
            break

        page += 1
        time.sleep(0.1)  # Rate limit respect

    print(f"  Done! Fetched {len(all_leads)} total leads.")
    return all_leads


def categorize_lead_esp(lead: dict) -> str:
    """
    Returns 'outlook', 'google', or 'unknown' based on lead's ESP tags.
    """
    tags = lead.get("tags", [])
    tag_ids = {t["id"] for t in tags}

    if OUTLOOK_TAG_ID in tag_ids:
        return "outlook"
    elif tag_ids & NON_OUTLOOK_TAG_IDS:
        return "google"
    else:
        return "unknown"


def get_campaign_lead_ids(campaign_id: int) -> set:
    """Get all lead IDs for a specific campaign."""
    print(f"  Fetching lead IDs for campaign {campaign_id}...")
    lead_ids = set()
    page = 1

    while True:
        data = api_get(f"campaigns/{campaign_id}/leads", params={"page": page, "per_page": 15})
        leads = data.get("data", [])
        meta = data.get("meta", {})

        for lead in leads:
            lead_ids.add(lead["id"])

        if page >= meta.get("last_page", 1):
            break
        page += 1
        time.sleep(0.05)

    print(f"    Found {len(lead_ids)} leads.")
    return lead_ids


def write_lead_csv(filename: str, leads: list):
    """Write leads to a CSV file for manual import."""
    if not leads:
        print(f"  No leads to write for {filename}")
        return

    fieldnames = ["first_name", "last_name", "email", "title", "company"]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            writer.writerow({
                "first_name": lead.get("first_name", ""),
                "last_name": lead.get("last_name", ""),
                "email": lead.get("email", ""),
                "title": lead.get("title", ""),
                "company": lead.get("company", ""),
            })

    print(f"  Written {len(leads)} leads to {filename}")


# ============================================================
# STEP 1: FIX CAMPAIGN 842 (remove accidental test step 6906)
# ============================================================

def fix_campaign_842():
    """
    Campaign 842's sequence has an accidental test step (id 6906, subject 'Test').
    We recreate the sequence by creating a NEW campaign with the correct 5 steps,
    then note the issue for the user.

    Note: The API doesn't allow deleting individual steps from an existing sequence.
    The original campaign 842 PAUSED state means no emails will be sent with the test step.
    We will create the new split campaigns from the CORRECT 5 steps (excluding 6906).
    """
    print("\n" + "="*60)
    print("STEP 1: Getting Campaign 2 email steps (excluding test step)")
    print("="*60)

    steps = get_sequence_steps(842)
    # Filter out the accidental test step 6906
    clean_steps = [s for s in steps if s["id"] != 6906]
    print(f"Campaign 842 has {len(steps)} steps, using {len(clean_steps)} (excluding test step 6906)")
    for s in clean_steps:
        print(f"  Step {s['id']}: {s['email_subject'][:60]} (variant={s['variant']})")

    return clean_steps


# ============================================================
# STEP 2: GET CAMPAIGN 3 STEPS
# ============================================================

def get_campaign_843_steps():
    print("\n" + "="*60)
    print("STEP 2: Getting Campaign 3 email steps")
    print("="*60)

    steps = get_sequence_steps(843)
    print(f"Campaign 843 has {len(steps)} steps")
    for s in steps:
        print(f"  Step {s['id']}: {s['email_subject'][:60]} (variant={s['variant']})")

    return steps


# ============================================================
# STEP 3: CREATE 6 NEW CAMPAIGNS
# ============================================================

CAMPAIGN_CONFIGS = [
    {
        "base_name": "Campaign 1: Veterans with Hiring Authority",
        "source_campaign_id": None,  # Campaign 833 is gone - will create shells
        "google_name": "Campaign 1: Veterans with Hiring Authority - Google",
        "outlook_name": "Campaign 1: Veterans with Hiring Authority - Outlook",
    },
    {
        "base_name": "Campaign 2: Operations Leaders & SMB Founders",
        "source_campaign_id": 842,
        "google_name": "Campaign 2: Operations Leaders & SMB Founders - Google",
        "outlook_name": "Campaign 2: Operations Leaders & SMB Founders - Outlook",
    },
    {
        "base_name": "Campaign 3: Open Roles / Hiring Signal",
        "source_campaign_id": 843,
        "google_name": "Campaign 3: Open Roles / Hiring Signal - Google",
        "outlook_name": "Campaign 3: Open Roles / Hiring Signal - Outlook",
    },
]


def create_all_campaigns(steps_by_campaign: dict) -> dict:
    """Create all 6 new campaigns and set up their sequences."""
    print("\n" + "="*60)
    print("STEP 3: Creating 6 new campaigns")
    print("="*60)

    campaign_ids = {}

    for config in CAMPAIGN_CONFIGS:
        source_id = config["source_campaign_id"]
        steps = steps_by_campaign.get(source_id, [])

        for variant, camp_name in [("google", config["google_name"]), ("outlook", config["outlook_name"])]:
            print(f"\nCreating: {camp_name}")

            # Create the campaign
            camp = create_campaign(camp_name)
            camp_id = camp["id"]
            print(f"  Created campaign ID: {camp_id}")

            # Set up email sequence if we have steps
            if steps:
                seq_title = f"{config['base_name']} - {variant.capitalize()} Sequence"
                print(f"  Creating sequence with {len(steps)} steps...")
                seq_result = create_sequence_for_campaign(camp_id, seq_title, steps)
                print(f"  Sequence created: ID {seq_result.get('id')}")
            else:
                print(f"  ⚠️  No email steps available (Campaign 1 source was deleted)")
                print(f"     Please add email content manually in the platform UI")

            campaign_ids[f"{config['base_name']}_{variant}"] = camp_id
            time.sleep(0.5)

    return campaign_ids


# ============================================================
# STEP 4: FETCH AND FILTER LEADS
# ============================================================

def build_lead_csvs(campaign_ids: dict):
    """Fetch all global leads, match to original campaigns, filter by ESP, write CSVs."""
    print("\n" + "="*60)
    print("STEP 4: Fetching leads and filtering by ESP")
    print("="*60)

    # Get lead IDs per original campaign
    print("\nGetting original campaign lead IDs...")
    # Campaign 1 (833) is gone - skip
    camp_lead_ids = {
        842: get_campaign_lead_ids(842),
        843: get_campaign_lead_ids(843),
    }

    # Fetch all global leads (with tags)
    all_leads = fetch_all_leads_paginated()

    # Build lead ID → lead data map
    lead_map = {lead["id"]: lead for lead in all_leads}

    # Organize leads into buckets: campaign -> esp_variant -> [leads]
    buckets = defaultdict(lambda: defaultdict(list))

    for source_campaign_id, lead_ids in camp_lead_ids.items():
        print(f"\nProcessing {len(lead_ids)} leads from campaign {source_campaign_id}...")

        google_count = 0
        outlook_count = 0
        unknown_count = 0

        for lead_id in lead_ids:
            lead = lead_map.get(lead_id)
            if not lead:
                # Lead not in global list - skip
                continue

            esp_variant = categorize_lead_esp(lead)

            if esp_variant == "outlook":
                outlook_count += 1
                buckets[source_campaign_id]["outlook"].append(lead)
            elif esp_variant == "google":
                google_count += 1
                buckets[source_campaign_id]["google"].append(lead)
            else:
                unknown_count += 1
                # Unknown ESP goes to Google (catch-all)
                buckets[source_campaign_id]["google"].append(lead)

        print(f"  Google/other: {google_count}, Outlook: {outlook_count}, Unknown (→Google): {unknown_count}")

    # Write CSV files
    print("\nWriting lead CSV files...")
    os.makedirs("lead_csvs", exist_ok=True)

    campaign_name_map = {
        842: "Campaign2_Operations",
        843: "Campaign3_OpenRoles",
    }

    csv_files = {}
    for source_id, variants in buckets.items():
        camp_name = campaign_name_map.get(source_id, f"Campaign_{source_id}")
        for variant, leads in variants.items():
            filename = f"lead_csvs/{camp_name}_{variant}.csv"
            write_lead_csv(filename, leads)

            # Map to new campaign ID
            if source_id == 842:
                base = "Campaign 2: Operations Leaders & SMB Founders"
            elif source_id == 843:
                base = "Campaign 3: Open Roles / Hiring Signal"
            else:
                base = f"Campaign {source_id}"

            new_camp_id = campaign_ids.get(f"{base}_{variant}")
            csv_files[filename] = {
                "new_campaign_id": new_camp_id,
                "new_campaign_name": f"{base} - {variant.capitalize()}",
                "lead_count": len(leads),
            }

    return csv_files


def print_summary(campaign_ids: dict, csv_files: dict):
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    print("\n✅ New campaigns created:")
    for key, camp_id in sorted(campaign_ids.items()):
        print(f"  [{camp_id}] {key.replace('_', ' - ', 1)}")

    print("\n📋 Lead CSV files for manual import:")
    print("   (Import these via the platform UI → Leads → Import CSV)")
    for filename, info in sorted(csv_files.items()):
        print(f"\n  File: {filename}")
        print(f"    Import to: [{info['new_campaign_id']}] {info['new_campaign_name']}")
        print(f"    Leads: {info['lead_count']}")

    print("\n⚠️  Manual actions needed:")
    print("  1. Campaign 1 (Veterans) email content: Please add email copy manually")
    print("     in the platform UI for these two campaigns:")
    for key, camp_id in sorted(campaign_ids.items()):
        if "Campaign 1" in key:
            print(f"       [{camp_id}] {key}")

    print("\n  2. Campaign 842 (original) has an accidental 'Test' step (ID 6906).")
    print("     This needs to be removed manually in the platform UI.")
    print("     The 6 new campaigns do NOT have this test step.")

    print("\n  3. Campaign 1 leads: Campaign 833 was not accessible via API.")
    print("     To split Campaign 1 leads, you'll need to export them from")
    print("     the platform UI and re-import filtered by ESP tag.")


if __name__ == "__main__":
    print("Business Sergeant - ESP Campaign Split Setup")
    print("=" * 60)

    # Step 1 & 2: Get clean email steps
    steps_842 = fix_campaign_842()
    steps_843 = get_campaign_843_steps()

    steps_by_campaign = {
        842: steps_842,
        843: steps_843,
        None: [],  # Campaign 1 (833 is gone)
    }

    # Step 3: Create 6 new campaigns
    campaign_ids = create_all_campaigns(steps_by_campaign)

    # Step 4: Fetch leads and write CSVs
    csv_files = build_lead_csvs(campaign_ids)

    # Summary
    print_summary(campaign_ids, csv_files)

    print("\n✅ Setup complete!")
