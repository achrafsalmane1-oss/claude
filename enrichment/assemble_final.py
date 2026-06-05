#!/usr/bin/env python3
"""
Assemble the FINAL client deliverable from a Clay "Find People" export.

Clay enriches the company table and (per company) returns up to 2-3 contacts.
This joins each contact back to the company's Commodity / HS Code / Country /
Address from our prepared input, derives Department from the job title, and
writes the final CSV in the client's exact Ex-/Im- schema.

Because Clay's exact export column names depend on how the table is built,
map them once in COLMAP below (left = our target field, right = the column
name in the Clay export). Run with --peek first to print the export's headers.

Usage:
  python3 assemble_final.py --peek <clay_export.csv>
  python3 assemble_final.py <side: ex|im> <clay_export.csv> <our_input.csv> <out.csv>
"""
import csv, sys, re

# ---- target schema (client's columns), in order ----
SCHEMA = {
 "ex": ["ExComp","ExAddress","ExCountry","ExComm","ExHSCode","ExDept","ExFName",
        "ExLName","ExJobTitle","ExEmail","ExPhone","ExMobile","ExWA","ExLinkedIn","ExURL"],
 "im": ["ImComp","ImAddress","ImCountry","ImComm","ImHSCode","ImDept","ImFName",
        "ImLName","imJobTitle","ImEmail","ImPhone","ImMobile","ImWA","ImLinkedIn","ImURL"],
}
# company-level fields copied from our input (keyed by company name)
CARRY = {"ex": ["ExComp","ExAddress","ExCountry","ExComm","ExHSCode","ExURL"],
         "im": ["ImComp","ImAddress","ImCountry","ImComm","ImHSCode","ImURL"]}

# Map Clay export columns -> our per-contact target fields. EDIT after --peek.
# Keys are generic; values are likely Clay header names (lowercased match).
CONTACT_MAP = {
 "FName":    ["first name","firstname","first_name","contact first name"],
 "LName":    ["last name","lastname","last_name","contact last name"],
 "JobTitle": ["job title","title","jobtitle","position","contact title"],
 "Email":    ["email","work email","email address","professional email"],
 "Phone":    ["phone","phone number","work phone","direct phone","company phone"],
 "Mobile":   ["mobile","mobile phone","cell","mobile number","personal phone"],
 "WA":       ["whatsapp","whatsapp number","wa"],
 "LinkedIn": ["linkedin","linkedin url","linkedin profile","li url"],
 "CompanyKey":["company","company name","account","organization","domain","website"],
}

DEPT = [  # (regex on title, department label)
 (r'procure|purchas|sourcing|buyer|category|commodity|vendor', "Procurement / Purchasing"),
 (r'import|customs', "Import / Customs"),
 (r'supply chain', "Supply Chain"),
 (r'logistic', "Logistics"),
 (r'export|\btrade\b|compliance', "Export / Trade"),
 (r'sales|account', "Sales"),
]
def dept(title):
    t = (title or "").lower()
    for pat, lab in DEPT:
        if re.search(pat, t): return lab
    return ""

def norm(s): return " ".join((s or "").strip().lower().split())

def find_col(headers, options):
    low = {h.lower(): h for h in headers}
    for o in options:
        if o in low: return low[o]
    # loose contains-match fallback
    for o in options:
        for h in headers:
            if o in h.lower(): return h
    return None

def peek(path):
    r = csv.reader(open(path, encoding="utf-8", errors="replace"))
    print("Clay export columns:")
    for h in next(r): print("  -", h)

def run(side, export, our_input, out):
    side = side.lower(); sch = SCHEMA[side]; carry = CARRY[side]
    pre = "Ex" if side == "ex" else "Im"
    comp_field = f"{pre}Comp"
    # company metadata keyed by normalized company name
    meta = {}
    for r in csv.DictReader(open(our_input, encoding="utf-8", errors="replace")):
        meta[norm(r[comp_field])] = {k: r.get(k, "") for k in carry}
    exp_rows = list(csv.DictReader(open(export, encoding="utf-8", errors="replace")))
    headers = exp_rows[0].keys() if exp_rows else []
    cols = {k: find_col(headers, v) for k, v in CONTACT_MAP.items()}
    missing = [k for k, v in cols.items() if v is None]
    if missing:
        print(f"WARN: could not map {missing} -- edit CONTACT_MAP, run --peek to see headers")
    title_f = "imJobTitle" if side == "im" else "ExJobTitle"
    out_rows = []
    for r in exp_rows:
        key = norm(r.get(cols["CompanyKey"], "")) if cols["CompanyKey"] else ""
        m = meta.get(key, {})
        row = {c: "" for c in sch}
        for c in carry: row[c] = m.get(c, "")              # company-level
        g = lambda k: r.get(cols[k], "") if cols.get(k) else ""
        row[f"{pre}FName"] = g("FName"); row[f"{pre}LName"] = g("LName")
        row[title_f] = g("JobTitle"); row[f"{pre}Email"] = g("Email")
        row[f"{pre}Phone"] = g("Phone"); row[f"{pre}Mobile"] = g("Mobile")
        row[f"{pre}WA"] = g("WA"); row[f"{pre}LinkedIn"] = g("LinkedIn")
        row[f"{pre}Dept"] = dept(g("JobTitle"))
        out_rows.append(row)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sch); w.writeheader(); w.writerows(out_rows)
    print(f"{out}: {len(out_rows)} contact rows written")

if __name__ == "__main__":
    if sys.argv[1] == "--peek": peek(sys.argv[2])
    else: run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
