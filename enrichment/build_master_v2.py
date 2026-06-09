#!/usr/bin/env python3
"""
Build "Master Version #2": the client's exact original Matched Trade table with
30 enrichment columns appended (15 exporter + 15 importer, per the Enrichment
Plan & Workflow schema). One primary decision-maker per company is mapped onto
every trade row. Company-level fields filled even when no contact was found.

Usage: python3 build_master_v2.py <matched_table.csv> <clay_exports_dir> <out.csv>
"""
import csv, re, sys
from difflib import SequenceMatcher
from collections import defaultdict

MT, UP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DELIV = "enrichment/deliverable"

# ---- domain sanity (reuse the cleaning denylist) ----
MULTI_TLD=("com.ar","com.br","com.mx","com.cn","co.uk","com.co","com.pe","com.uy",
           "com.py","com.bo","com.ve","com.ec","com.hk","com.tw","co.jp","com.tr","com.au")
def sld(d):
    d=(d or "").strip().lower(); d=re.sub(r'^https?://','',d).split('/')[0]
    if d.startswith('www.'): d=d[4:]
    for t in MULTI_TLD:
        if d.endswith("."+t): return d[:-(len(t)+1)].split('.')[-1]
    p=d.split('.'); return p[-2] if len(p)>=2 else (p[0] if p else "")
def toks(s):
    s=re.sub(r'[^a-z0-9 ]',' ',(s or "").lower())
    stop={'inc','llc','ltd','co','corp','sa','srl','de','group','intl','international',
          'trading','trade','import','export','company','industrial','industries','sl','cv'}
    return [w for w in s.split() if w not in stop and len(w)>1]
def score(name,dom):
    root=sld(dom); t=toks(name); cat="".join(t)
    if not root or not cat: return 0.0
    if root in cat or cat in root: return 1.0
    return round(max([SequenceMatcher(None,w,root).ratio() for w in t]+
                     [SequenceMatcher(None,cat,root).ratio()]),2)
WRONG=set("""att paloaltonetworks bloomberg bmwusa nestle novanthealth goodgamestudios
 cushmanwakefield georgia spunkmeyer karllagerfeld fadv newswire importgenius
 globalsources tendata tradewheel eximpedia trademo diytrade ec21 kompass
 messefrankfurt hktdc iata bat caterpillar nidec asahigroup-holdings chinadailyuse okchem""".split())
def clean_domain(name,dom):
    return "" if (score(name,dom)<0.5 and sld(dom) in WRONG) else (dom or "").strip()
def norm(s): return " ".join((s or "").strip().lower().split())

# ---- company-level enrichment (Address/Country/Website from Clay company tables) ----
def load_company(path):
    d={}
    for r in csv.DictReader(open(path,encoding='utf-8',errors='replace')):
        d[norm(r["Company Name"])]={
          "Address":r.get("Address",""),"Country":r.get("Country",""),
          "URL":clean_domain(r["Company Name"], r.get("DOMAIN MAIN",""))}
    return d
exp_co=load_company(f"{UP}/4b11536f-ExportersforclayDefaultviewexport1780661248119.csv")
imp_co=load_company(f"{UP}/00ad8187-importers_for_clayDefaultviewexport1780661216204.csv")

# ---- primary contact per company (from cleaned contact files) ----
def seniority(t):
    t=(t or "").lower()
    if re.search(r'chief|c\.?e\.?o|cfo|coo|\bvp\b|vice president|head|director|owner|president',t): return 3
    if re.search(r'manager|lead|principal',t): return 2
    return 1
def load_primary(path):
    by=defaultdict(list)
    for r in csv.DictReader(open(path,encoding='utf-8',errors='replace')):
        by[norm(r["Company Name"])].append(r)
    out={}
    for k,rows in by.items():
        rows.sort(key=lambda r:(bool(r["Email"].strip()), seniority(r["Job Title"]),
                                bool(r["Mobile Phone"].strip())), reverse=True)
        out[k]=rows[0]
    return out
exp_ct=load_primary(f"{DELIV}/exporter_contacts.csv")
imp_ct=load_primary(f"{DELIV}/importer_contacts.csv")

# ---- enrichment column order (doc schema) ----
def block(pre, jt):  # jt = job-title header (doc uses 'imJobTitle' for importer)
    return [f"{pre}Address",f"{pre}Country",f"{pre}Comm",f"{pre}Dept",f"{pre}Comp",
            f"{pre}Email",f"{pre}Phone",f"{pre}Mobile",f"{pre}WA",f"{pre}LinkedIn",
            jt,f"{pre}HSCode",f"{pre}URL",f"{pre}FName",f"{pre}LName"]
EX=block("Ex","ExJobTitle"); IM=block("Im","imJobTitle")

def fill(pre, jt, name, comm, hs, co, ct):
    d={c:"" for c in (EX if pre=="Ex" else IM)}
    d[f"{pre}Comp"]=name; d[f"{pre}Comm"]=comm; d[f"{pre}HSCode"]=hs
    d[f"{pre}Address"]=co.get("Address",""); d[f"{pre}Country"]=co.get("Country","")
    d[f"{pre}URL"]=co.get("URL","")
    if ct:
        d[f"{pre}Dept"]=ct.get("Department",""); d[f"{pre}Email"]=ct.get("Email","")
        d[f"{pre}Mobile"]=ct.get("Mobile Phone",""); d[f"{pre}LinkedIn"]=ct.get("LinkedIn Profile","")
        d[jt]=ct.get("Job Title",""); d[f"{pre}FName"]=ct.get("First Name","")
        d[f"{pre}LName"]=ct.get("Last Name","")
        if not d[f"{pre}URL"]: d[f"{pre}URL"]=ct.get("Website","")
    return d

mt=list(csv.DictReader(open(MT,encoding='utf-8',errors='replace')))
orig_cols=list(mt[0].keys())
out_cols=orig_cols+EX+IM
with open(OUT,"w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=out_cols); w.writeheader()
    for r in mt:
        en=norm(r["Exporter"]); inn=norm(r["Importer"])
        row=dict(r)
        row.update(fill("Ex","ExJobTitle",r["Exporter"],r["Commodity Name (Count: 27665)"],
                        r["HS Code"],exp_co.get(en,{}),exp_ct.get(en)))
        row.update(fill("Im","imJobTitle",r["Importer"],r["Commodity Name (Count: 27665)"],
                        r["HS Code"],imp_co.get(inn,{}),imp_ct.get(inn)))
        w.writerow(row)

ex_rows=sum(1 for r in mt if exp_ct.get(norm(r["Exporter"])))
im_rows=sum(1 for r in mt if imp_ct.get(norm(r["Importer"])))
print(f"{OUT}: {len(mt)} rows, {len(out_cols)} cols ({len(orig_cols)} original + 30 enrichment)")
print(f"  rows w/ exporter contact: {ex_rows} | rows w/ importer contact: {im_rows}")
