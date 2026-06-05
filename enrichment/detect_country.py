#!/usr/bin/env python3
"""
Derive the real physical Country from an address (Step 2: "Country, segregated
from physical address") and strip the trade-lane tag (Argentina/China) that the
source appends to every row. Operates in place on a Clay input CSV.

Usage: python3 detect_country.py <file.csv> <country_col> <addr_col> <trade_tag>
"""
import csv, sys, re

FILE, CCOL, ACOL, TAG = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
# optional: fill remaining blanks with this country (use when the trade tag is
# confirmed by the physical addresses, e.g. exporters whose addresses are Chinese)
DEFAULT = sys.argv[5] if len(sys.argv) > 5 else ""

US_STATES = set("al ak az ar ca co ct de fl ga hi id il in ia ks ky la me md ma "
                "mi mn ms mo mt ne nv nh nj nm ny nc nd oh ok or pa ri sc sd tn "
                "tx ut vt va wa wv wi wy dc".split())
US_ZIP = re.compile(r'\b([a-z]{2})\s+\d{5}(?:-\d{4})?\b', re.I)

# country name / strong cue -> canonical name (checked as word-ish substrings)
CUES = [
    (r'\bunited states\b|\busa\b|\bu\.?s\.?a\b|\bu\.?s\b', "United States"),
    (r'\bargentin|buenos aires|\bc[oó]rdoba\b|\brosario\b|\bmendoza\b|'
     r'\bla plata\b|\bquilmes\b|\b[a-z]\d{4}[a-z]{3}\b', "Argentina"),
    (r'\bpanama\b|zona libre|\bcolon\b|\bpan\b', "Panama"),
    (r'\buruguay', "Uruguay"), (r'\bparaguay', "Paraguay"),
    (r'\bbrasil|\bbrazil', "Brazil"), (r'\bchile\b', "Chile"),
    (r'\bbolivia', "Bolivia"), (r'\bper[uú]\b', "Peru"),
    (r'\bmexic|m[eé]xico', "Mexico"), (r'\bcolombia', "Colombia"),
    (r'\becuador', "Ecuador"), (r'\bvenezuela', "Venezuela"),
    (r'\bchina\b|\bp\.?r\.?c\b|\bcn\b', "China"),
    (r'\bhong kong\b', "Hong Kong"), (r'\btaiwan\b', "Taiwan"),
    (r'\bindia\b', "India"), (r'\bgermany|deutschland', "Germany"),
    (r'\bspain|espa[nñ]a', "Spain"), (r'\bitaly|italia', "Italy"),
    (r'\bfrance\b', "France"), (r'\bcanada\b', "Canada"),
    (r'united kingdom|\bu\.?k\b|england', "United Kingdom"),
    (r'\bnetherlands|holland', "Netherlands"),
]

def clean_addr(a):
    a = (a or "").strip()
    # strip exporter "/ China" style suffix and trailing trade tag
    a = re.sub(r'\s*/\s*' + re.escape(TAG) + r'\s*$', '', a, flags=re.I)
    a = re.sub(r'\s+' + re.escape(TAG) + r'\s*$', '', a, flags=re.I)
    a = a.strip(' /,-')
    # if the whole address was just the trade tag, there is no real address
    if a.lower() == TAG.lower():
        return ""
    return a

def detect(addr, cleaned):
    low = " " + cleaned.lower() + " "
    for pat, name in CUES:
        if re.search(pat, low):
            return name
    m = US_ZIP.search(cleaned)
    if m and m.group(1).lower() in US_STATES:
        return "United States"
    return ""   # unknown -> leave blank, don't fall back to noisy tag

rows = list(csv.reader(open(FILE, encoding="utf-8", errors="replace")))
hdr = rows[0]; ci, ai = hdr.index(CCOL), hdr.index(ACOL)
from collections import Counter
dist = Counter(); blank = 0
for r in rows[1:]:
    cleaned = clean_addr(r[ai])
    r[ai] = cleaned
    c = detect(r[ai], cleaned)
    if not c and not cleaned:
        c = TAG          # no physical address -> trade tag is all we know
    elif not c and DEFAULT:
        c = DEFAULT      # addresses confirm the trade lane -> default blanks
    r[ci] = c
    if c: dist[c] += 1
    else: blank += 1
with open(FILE, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows)
print(f"{FILE}: {sum(dist.values())} countries detected, {blank} blank")
for k, v in dist.most_common(15): print(f"  {k:18} {v}")
