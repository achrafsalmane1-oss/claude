#!/usr/bin/env python3
"""
Prepare Clay-ready input files from the raw L4 trade CSV.

Implements Step 2 of the client's Enrichment Plan:
  - reshape raw rows into the Im-/Ex- target schema
  - split Country out of the physical address
  - dedupe to one row per unique company (Clay enriches per-company)
  - leave enrichment columns blank for Clay to fill

Run: python3 enrichment/prepare_clay_inputs.py <raw_csv>
Outputs: enrichment/clay_input_exporters.csv, enrichment/clay_input_importers.csv
"""
import csv, sys, os

RAW = sys.argv[1] if len(sys.argv) > 1 else "raw.csv"
OUT = os.path.dirname(os.path.abspath(__file__))

# Target schema per the workflow doc (Ex-/Im- prefixed). Enrichment cols are blank.
EX_COLS = ["ExComp","ExAddress","ExCountry","ExComm","ExHSCode","ExDept",
           "ExFName","ExLName","ExJobTitle","ExEmail","ExPhone","ExMobile",
           "ExWA","ExLinkedIn","ExURL"]
IM_COLS = ["ImComp","ImAddress","ImCountry","ImComm","ImHSCode","ImDept",
           "ImFName","ImLName","imJobTitle","ImEmail","ImPhone","ImMobile",
           "ImWA","ImLinkedIn","ImURL"]

def exporter_country(addr: str) -> str:
    # Exporter addresses encode country after the final " / " (e.g. "... / China")
    return addr.rsplit("/", 1)[-1].strip() if "/" in addr else ""

def importer_country(addr: str) -> str:
    # Importer source-country is appended as the last Capitalized token (noisy in source).
    toks = addr.strip().split()
    return toks[-1].strip() if toks and toks[-1][:1].isupper() else ""

def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

rows = list(csv.DictReader(open(RAW, encoding="utf-8", errors="replace")))

def build(side):
    # side = ("Exporter","Ex Email","Ex Phone","Exporter Address", exporter_country, EX_COLS, "Ex")
    name_c, addr_c, ctry_fn, cols, pre = side
    agg = {}  # key -> dict
    for r in rows:
        comp = (r.get(name_c) or "").strip()
        if not comp:
            continue
        addr = (r.get(addr_c) or "").strip()
        key = (norm(comp), norm(addr))
        comm = (r.get("Commodity Name (Count: 27665)") or r.get("Commodity Name") or "").strip()
        hs = (r.get("HS Code") or "").strip()
        if key not in agg:
            agg[key] = {"comp": comp, "addr": addr, "ctry": ctry_fn(addr),
                        "comm": set(), "hs": set()}
        if comm: agg[key]["comm"].add(comm)
        if hs: agg[key]["hs"].add(hs)
    out = []
    for v in agg.values():
        row = {c: "" for c in cols}
        row[cols[0]] = v["comp"]                       # Comp
        row[cols[1]] = v["addr"]                        # Address
        row[cols[2]] = v["ctry"]                        # Country
        row[cols[3]] = " | ".join(sorted(v["comm"]))   # Commodity (all distinct)
        row[cols[4]] = " | ".join(sorted(v["hs"]))     # HS Code (all distinct)
        out.append(row)
    return cols, out

ex_cols, ex_rows = build(("Exporter","Exporter Address",exporter_country,EX_COLS,"Ex"))
im_cols, im_rows = build(("Importer","Importer Address",importer_country,IM_COLS,"Im"))

for fn, cols, data in [("clay_input_exporters.csv",ex_cols,ex_rows),
                       ("clay_input_importers.csv",im_cols,im_rows)]:
    p = os.path.join(OUT, fn)
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader(); w.writerows(data)
    print(f"{fn}: {len(data)} unique companies")
