# -*- coding: utf-8 -*-
"""
Restore GHL lead ownership from a trusted source (a CRM export taken BEFORE the
round-robin overwrote owners, or a hand-built list).

Input: a CSV with columns  email,owner   where `owner` is either the GHL user id
or the agent's login email. Rows with an unknown owner are skipped and reported.

It sets ONLY assignedTo (via /contacts/upsert with email + assignedTo), touching
nothing else. Run DRY first:  DRY_RUN=1 python restore_owners.py owners.csv

Env: GHL_TOKEN, GHL_LOCATION_ID
"""
import csv, json, os, subprocess, sys, time

PIT = os.environ.get("GHL_TOKEN", "")
LOC = os.environ.get("GHL_LOCATION_ID", "bu3JqdsMUIMYcVSRBSXs")
DRY = os.environ.get("DRY_RUN", "") not in ("", "0", "false", "False")
BASE = "https://services.leadconnectorhq.com"

# agent login email -> GHL user id (accepts either form in the CSV `owner` column)
EMAIL2UID = {
    "fdepart@landquire.com": "aBXFUOaJTNd3S6xuoe2p", "mverloove@landquire.com": "NSXvGpjwu2kq3I6bhCO5",
    "pgeorges@landquire.com": "Qw0kNzYf8z7wB8ACQEWZ", "prizk@landquire.com": "fSr7OAL4VXxZIngOL7Ey",
    "tcarrel@landquire.com": "aCKmPd1GI1IikvbT3ERB", "pbaudreux@landquire.com": "lOSuNBiTo8BlFi5gAHdF",
    "kevinlanson@landquire.com": "7l60QOUa5c2EvVr96frH", "cdiot@landquire.com": "bOQhh8LhNjSOT1CvxtYW",
    "hmoraes@landquire.com": "PXQVZgou0EbKB18H5Wh3", "lferraz@landquire.com": "tvp9ana9YZWwFBUyXMf0",
    "fsantos@landquire.com": "xUvVav7DQywx2WYZnLMI", "splummer@landquire.com": "PIudlTQkBqQCWJ2bVL0l",
    "carlosurdinineasejas@gmail.com": "fQjewvPSzRh3ui2ZCf2W"}
KNOWN_UIDS = set(EMAIL2UID.values())


def upsert(email, uid):
    if DRY:
        return True
    body = {"locationId": LOC, "email": email, "assignedTo": uid}
    cmd = ["curl", "-s", "-X", "POST", BASE + "/contacts/upsert",
           "-H", "Authorization: Bearer " + PIT, "-H", "Version: 2021-07-28",
           "-H", "Content-Type: application/json", "-d", json.dumps(body)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    try:
        return bool((json.loads(out.stdout).get("contact") or {}).get("id"))
    except Exception:
        return False


def resolve(owner):
    owner = (owner or "").strip()
    if owner in KNOWN_UIDS:
        return owner
    return EMAIL2UID.get(owner.lower())


def main(path):
    ok = skipped = 0
    for row in csv.DictReader(open(path)):
        email = (row.get("email") or "").strip().lower()
        uid = resolve(row.get("owner"))
        if not email or not uid:
            print("SKIP (unknown owner/email):", row); skipped += 1; continue
        if upsert(email, uid):
            ok += 1
        else:
            print("FAIL:", email); skipped += 1
        time.sleep(0.15)
    print(f"Restored: {ok} | skipped: {skipped} | DRY_RUN={DRY}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python restore_owners.py owners.csv"); sys.exit(1)
    main(sys.argv[1])
