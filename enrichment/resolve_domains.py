#!/usr/bin/env python3
"""
Best-effort domain/website resolution from company name (+ country) using the
free Clearbit/HubSpot autocomplete endpoint, with fuzzy name matching to pick
the correct candidate. Adds a URL column to a Clay input file.

Resolved domains are real lookups (not guessed). Companies with no confident
match are left BLANK on purpose so Clay's own domain-finder handles them
(guessing domains would poison the find-people step and the campaign).

Usage: python3 resolve_domains.py <input.csv> <url_col> <name_col> <out.csv> [limit]
"""
import csv, sys, re, time, json, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

INP, URLCOL, NAMECOL, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
LIMIT = int(sys.argv[5]) if len(sys.argv) > 5 else 0

SUFFIX = re.compile(r'\b(inc|llc|ltd|co|corp|corporation|company|group|intl|international|'
                    r'gmbh|sa|sas|srl|bv|nv|plc|pvt|pte|limited|holdings?|enterprises?|'
                    r'trading|import|export|imports|exports|industries|industry|'
                    r'manufacturing|mfg|technologies|technology|tech)\b', re.I)
def norm(s):
    s = (s or "").lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    s = SUFFIX.sub(' ', s)
    return ' '.join(s.split())

def score(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb: return 0.0
    if na == nb: return 1.0
    sa, sb = set(na.split()), set(nb.split())
    jacc = len(sa & sb) / len(sa | sb) if sa | sb else 0
    seq = SequenceMatcher(None, na, nb).ratio()
    return max(jacc, seq)

def resolve(name):
    if not name: return ("", 0.0)
    url = "https://autocomplete.clearbit.com/v1/companies/suggest?query=" + urllib.parse.quote(name)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                cands = json.load(r)
            best, bs = "", 0.0
            for c in cands:
                s = score(name, c.get("name", ""))
                if s > bs:
                    bs, best = s, c.get("domain", "")
            return (best if bs >= 0.72 else "", round(bs, 2))
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return ("", 0.0)

rows = list(csv.DictReader(open(INP, encoding="utf-8", errors="replace")))
if LIMIT: rows = rows[:LIMIT]
fields = list(rows[0].keys())
if "_url_match" not in fields: fields.append("_url_match")

names = [r.get(NAMECOL, "") for r in rows]
results = [None] * len(names)
def work(i): results[i] = resolve(names[i])
with ThreadPoolExecutor(max_workers=12) as ex:
    list(ex.map(work, range(len(names))))

hits = 0
for r, (dom, sc) in zip(rows, results):
    if dom:
        r[URLCOL] = dom; hits += 1
    r["_url_match"] = sc
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
print(f"{OUT}: resolved {hits}/{len(rows)} domains ({100*hits//max(len(rows),1)}%)")
