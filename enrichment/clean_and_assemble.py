#!/usr/bin/env python3
"""
Clean Clay's people exports and assemble the final client deliverables.

- removes contacts whose company->domain match is a verified mismatch
  (famous unrelated brands + B2B directory / trade-data / fair sites that the
  AI domain step snapped to). Removed rows are saved for audit, not lost.
- keeps legit abbreviation / parent-brand domains (slb, agd, xcmg, sinopec...).
- flags every kept contact with a Domain Match confidence (High/Med/Low).
- joins Commodity / HS Code / Country from the company table; derives Department.
- outputs one clean CSV per side + a removed-for-review CSV, and prints stats.
"""
import csv, re, sys
from difflib import SequenceMatcher
from collections import defaultdict

UP = sys.argv[1]
OUT = "enrichment/deliverable"

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
def conf(s): return "High" if s>=0.7 else ("Medium" if s>=0.5 else "Low")
def norm(s): return " ".join((s or "").strip().lower().split())

CCTLD={"ar":"Argentina","br":"Brazil","mx":"Mexico","cn":"China","hk":"Hong Kong",
       "tw":"Taiwan","pe":"Peru","uy":"Uruguay","cl":"Chile","co":"Colombia",
       "py":"Paraguay","bo":"Bolivia","ve":"Venezuela","ec":"Ecuador","uk":"United Kingdom",
       "in":"India","de":"Germany","es":"Spain","it":"Italy","fr":"France","jp":"Japan",
       "kr":"South Korea","tr":"Turkey","za":"South Africa","au":"Australia"}
def country_fallback(given, domain, name):
    if (given or "").strip(): return given
    d=(domain or "").strip().lower().split('/')[0]
    if d:
        tld=d.split('.')[-1]
        if tld in CCTLD: return CCTLD[tld]
    if "argentin" in (name or "").lower(): return "Argentina"
    return ""

# verified-wrong domain roots (famous unrelated brands + directory/data/fair sites)
WRONG = set("""att paloaltonetworks bloomberg bmwusa nestle novanthealth
 goodgamestudios cushmanwakefield georgia spunkmeyer karllagerfeld fadv newswire
 importgenius globalsources tendata tradewheel eximpedia trademo diytrade ec21
 kompass messefrankfurt hktdc iata bat caterpillar nidec asahigroup-holdings
 chinadailyuse okchem""".split())

DEPT=[(r'procure|purchas|sourcing|buyer|category|commodity|vendor',"Procurement / Purchasing"),
      (r'import|customs',"Import / Customs"),(r'supply chain',"Supply Chain"),
      (r'logistic',"Logistics"),(r'export|\btrade\b|compliance',"Export / Trade"),
      (r'sales|account|commercial',"Sales")]
def dept(t):
    t=(t or "").lower()
    for p,l in DEPT:
        if re.search(p,t): return l
    return ""

def load_company(path, name_c, extra):
    d={}
    for r in csv.DictReader(open(path,encoding='utf-8',errors='replace')):
        d[norm(r[name_c])]={k:r.get(v,"") for k,v in extra.items()}
    return d

FINAL_COLS=["Company Name","Country","Commodity","HS Code","Website","Department",
            "First Name","Last Name","Job Title","Email","Mobile Phone",
            "LinkedIn Profile","Location","Domain Match"]

def process(side, ppl_path, meta, email_field):
    rows=list(csv.DictReader(open(ppl_path,encoding='utf-8',errors='replace')))
    kept=[]; removed=[]
    for r in rows:
        name=r.get("Company Table Data","")
        dom=r.get("Company Domain","")
        s=score(name,dom); root=sld(dom)
        m=meta.get(norm(name),{})
        out={
          "Company Name":name,"Country":country_fallback(m.get("Country",""),dom,name),
          "Commodity":r.get("Commodity") or m.get("Commodity",""),
          "HS Code":r.get("HS Code") or m.get("HS Code",""),
          "Website":dom,"Department":dept(r.get("Job Title","")),
          "First Name":r.get("First Name",""),"Last Name":r.get("Last Name",""),
          "Job Title":r.get("Job Title",""),"Email":r.get(email_field,""),
          "Mobile Phone":r.get("Mobile Phone",""),
          "LinkedIn Profile":r.get("LinkedIn Profile",""),
          "Location":r.get("Location",""),"Domain Match":conf(s)}
        if s<0.5 and root in WRONG:
            out["_removed_reason"]=f"domain '{root}' unrelated to company (score {s})"
            removed.append(out)
        else:
            kept.append(out)
    return kept, removed

# ---- importers ----
imp_meta=load_company(f"{UP}/00ad8187-importers_for_clayDefaultviewexport1780661216204.csv",
    "Company Name",{"Country":"Country","Commodity":"Commodity","HS Code":"HS Code"})
imp_k,imp_r=process("im",f"{UP}/7ec9e393-ImportersPeopleDefaultviewexport1780661227929.csv",
    imp_meta,"Work Email")
# ---- exporters ----
exp_meta=load_company(f"{UP}/4b11536f-ExportersforclayDefaultviewexport1780661248119.csv",
    "Company Name",{"Country":"Country","Commodity":"Commodity","HS Code":"HS Code"})
exp_k,exp_r=process("ex",f"{UP}/1cb71e30-ExporterspeopleDefaultviewexport1780661286531Defaultviewexport1780662716049.csv",
    exp_meta,"Email")

def write(path, rows, cols):
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore'); w.writeheader(); w.writerows(rows)

write(f"{OUT}/importer_contacts.csv", imp_k, FINAL_COLS)
write(f"{OUT}/exporter_contacts.csv", exp_k, FINAL_COLS)
write(f"{OUT}/removed_for_review.csv", imp_r+exp_r, FINAL_COLS+["_removed_reason"])

def stats(lbl, total_companies, company_path, name_c, dom_c, kept):
    crows=list(csv.DictReader(open(company_path,encoding='utf-8',errors='replace')))
    with_dom=sum(1 for r in crows if (r.get(dom_c) or '').strip())
    comp_with_contact=len({norm(r["Company Name"]) for r in kept})
    with_email=sum(1 for r in kept if r["Email"].strip())
    with_phone=sum(1 for r in kept if r["Mobile Phone"].strip())
    print(f"\n=== {lbl} ===")
    print(f"  companies in list            : {total_companies}")
    print(f"  companies w/ domain found     : {with_dom}")
    print(f"  companies w/ >=1 contact (kept): {comp_with_contact}")
    print(f"  clean contacts                : {len(kept)}")
    print(f"   - with email                 : {with_email}")
    print(f"   - with mobile phone          : {with_phone}")

stats("IMPORTERS",1018,f"{UP}/00ad8187-importers_for_clayDefaultviewexport1780661216204.csv",
      "Company Name","DOMAIN MAIN",imp_k)
stats("EXPORTERS",26062,f"{UP}/4b11536f-ExportersforclayDefaultviewexport1780661248119.csv",
      "Company Name","DOMAIN MAIN",exp_k)
print(f"\nRemoved (verified wrong-domain) contacts: importers {len(imp_r)}, exporters {len(exp_r)}")
