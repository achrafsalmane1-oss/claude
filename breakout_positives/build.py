import json, re, csv, collections

camps = {c["id"]: c["name"] for c in json.load(open("campaigns.json"))}

# Campaigns whose audience is investor-side (funds, PE/VC, family offices, strategic
# acquirers) or that are not capital-raise outreach at all.
INVESTOR_SIDE = {297, 247, 250, 249, 251, 4, 69, 71, 76, 130, 131, 132, 240}
NOT_FUNDRAISING = {88, 103, 124, 128, 129, 77, 175, 56, 164}

INVESTOR_TITLE = re.compile(
    r"\b(angel investor|angel investors|investor|limited partner|general partner|"
    r"managing partner|venture partner|principal|portfolio manager|fund manager|"
    r"investment (manager|director|associate|analyst|officer)|"
    r"head of (investments?|deal flow)|deal (flow|origination)|family office)\b", re.I)
INVESTOR_COMPANY = re.compile(
    r"\b(capital|ventures?|venture|equity|partners|fund|funds|investments?|"
    r"asset management|family office|holdings)\b", re.I)

rows = {}
for line in open("interested_replies.jsonl"):
    r = json.loads(line)
    if r.get("automated_reply"):
        continue
    lead = r.get("lead") or {}
    lid = lead.get("id") or r.get("lead_id")
    email = (lead.get("email") or r.get("from_email_address") or "").strip().lower()
    key = email or f"lead:{lid}"
    if not key:
        continue
    prev = rows.get(key)
    if prev and prev["date_received"] >= (r["date_received"] or ""):
        prev["campaign_ids"].add(r["campaign_id"])
        continue
    cvs = {c["name"].strip().lower(): (c["value"] or "").strip()
           for c in (lead.get("custom_variables") or [])}
    rec = {
        "lead_id": lid,
        "email": email,
        "first_name": (lead.get("first_name") or "").strip(),
        "last_name": (lead.get("last_name") or "").strip(),
        "title": (lead.get("title") or "").strip(),
        "company": (lead.get("company") or "").strip(),
        "niche": cvs.get("niche", ""),
        "city": cvs.get("city", ""),
        "date_received": r["date_received"] or "",
        "campaign_ids": {r["campaign_id"]} | (prev["campaign_ids"] if prev else set()),
        "subject": r.get("subject") or "",
        "reply": (r.get("text_body") or "")[:600],
    }
    rows[key] = rec

def side(rec):
    cids = rec["campaign_ids"]
    if cids & NOT_FUNDRAISING and not (cids - NOT_FUNDRAISING):
        return "not_fundraising"
    title, comp = rec["title"], rec["company"]
    if INVESTOR_TITLE.search(title) and INVESTOR_COMPANY.search(comp or title):
        return "investor"
    if cids & INVESTOR_SIDE and not (cids - INVESTOR_SIDE - NOT_FUNDRAISING):
        return "investor"
    if INVESTOR_TITLE.search(title) and not comp:
        return "investor"
    return "company"

buckets = collections.Counter()
for rec in rows.values():
    rec["side"] = side(rec)
    buckets[rec["side"]] += 1

json.dump([{**r, "campaign_ids": sorted(r["campaign_ids"])} for r in rows.values()],
          open("positives_all.json", "w"), indent=1)
print("unique positive repliers:", len(rows))
print(buckets)
comp = [r for r in rows.values() if r["side"] == "company"]
print("company-side:", len(comp), "| with niche:", sum(1 for r in comp if r["niche"]))
print("no name:", sum(1 for r in comp if not r["first_name"] and not r["last_name"]))

# --- outputs -------------------------------------------------------------
comp_rows = sorted((r for r in rows.values() if r["side"] == "company"),
                   key=lambda r: r["date_received"], reverse=True)
json.dump([{**r, "campaign_ids": sorted(r["campaign_ids"])} for r in comp_rows],
          open("positives_company.json", "w"), indent=1)

with open("fund_directors_positive_fundraising.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["first_name", "last_name", "niche", "linkedin_url"])
    for r in comp_rows:
        w.writerow([r["first_name"], r["last_name"], r["niche"], ""])

with open("fund_directors_positive_fundraising_full.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["first_name", "last_name", "niche", "linkedin_url", "email",
                "title", "company", "city", "replied_at", "campaigns"])
    for r in comp_rows:
        w.writerow([r["first_name"], r["last_name"], r["niche"], "", r["email"],
                    r["title"], r["company"], r["city"], r["date_received"][:10],
                    " ".join(str(c) for c in sorted(r["campaign_ids"]))])
print("csv rows:", len(comp_rows))
