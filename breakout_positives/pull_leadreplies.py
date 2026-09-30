import os, json, re, time, threading
from concurrent.futures import ThreadPoolExecutor
# token comes from the BISON_TOKEN env var - never commit it
import bison, heyreach

SLUG = re.compile(r"(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|pub)/([A-Za-z0-9\-_%À-ÿ\.]{3,})", re.I)

have = {r["email"] for r in __import__("csv").DictReader(open("heyreach_500_full.csv"))} \
       if os.path.exists("heyreach_500_full.csv") else set()
rows = json.load(open("positives_company.json"))
SENIOR_ORDER = {5: 0, 4: 1, 3: 2, 1: 3, 0: 4}
def prio(r):
    dom = r["email"].split("@")[-1]
    tld = dom.rsplit(".", 1)[-1]
    foreign = 0 if (tld in heyreach.CC_TLD and tld not in heyreach.US_TLDS) else 1
    return (foreign, SENIOR_ORDER.get(heyreach.seniority(r["title"]), 4), r["date_received"])
targets = [r for r in rows if r["email"] not in have and r["lead_id"]]
targets.sort(key=prio)
print("targets:", len(targets), flush=True)

lock = threading.Lock(); out = open("lead_sig_slugs.jsonl", "w"); done = [0, 0]; t0 = time.time()

def work(r):
    try:
        found = set(); names = set()
        for rep in bison.paginate(f"/leads/{r['lead_id']}/replies", max_pages=6):
            body = (rep.get("text_body") or "")[:2500]
            for s in SLUG.findall(body):
                found.add(s.rstrip("/.,)>\"'"))
            if rep.get("from_name"):
                names.add(rep["from_name"])
    except Exception as e:
        found, names = set(), set()
    with lock:
        done[0] += 1
        if found:
            done[1] += 1
            out.write(json.dumps({"email": r["email"], "lead_id": r["lead_id"],
                                  "slugs": sorted(found), "from_names": sorted(names)}) + "\n")
            out.flush()
        if done[0] % 250 == 0:
            print(f"{done[0]}/{len(targets)} scanned, {done[1]} with linkedin ({time.time()-t0:.0f}s)", flush=True)

with ThreadPoolExecutor(max_workers=10) as ex:
    list(ex.map(work, targets))
out.close()
print("DONE", done, f"{time.time()-t0:.0f}s", flush=True)
