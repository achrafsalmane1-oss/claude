#!/usr/bin/env python3
"""
Produce a clean Clay-ready INPUT file: human-readable column names, only the
columns that carry data (Company, Address, Country, Commodity, HS Code,
Website). Drops the empty enrichment placeholders (Clay generates those) and
helper columns.

Usage: python3 finalize_clay_input.py <ex|im> <domains.csv> <out.csv>
"""
import csv, sys

side, INP, OUT = sys.argv[1].lower(), sys.argv[2], sys.argv[3]
pre = "Ex" if side == "ex" else "Im"

# source field (in domains file) -> clean output header
SRC = [(f"{pre}Comp","Company Name"), (f"{pre}Address","Address"),
       (f"{pre}Country","Country"), (f"{pre}Comm","Commodity"),
       (f"{pre}HSCode","HS Code"), (f"{pre}URL","Website")]

rows = list(csv.DictReader(open(INP, encoding="utf-8", errors="replace")))
out_headers = [h for _, h in SRC]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=out_headers); w.writeheader()
    for r in rows:
        w.writerow({h: (r.get(s, "") or "").strip() for s, h in SRC})
with_site = sum(1 for r in rows if (r.get(f"{pre}URL") or "").strip())
print(f"{OUT}: {len(rows)} rows, {len(out_headers)} cols, {with_site} with Website")
