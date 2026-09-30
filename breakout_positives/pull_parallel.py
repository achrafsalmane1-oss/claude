import os, json, time, threading
from concurrent.futures import ThreadPoolExecutor
# token comes from the BISON_TOKEN env var - never commit it
import bison

camps = json.load(open("campaigns.json"))
ids = [c["id"] for c in camps]
lock = threading.Lock()
out = open("interested_by_campaign.jsonl", "w")
done = [0]
t0 = time.time()

def work(cid):
    rows = []
    for r in bison.paginate("/replies", folder="inbox", status="interested", campaign_id=cid):
        slim = {k: r.get(k) for k in ("id","subject","date_received","campaign_id","lead_id","from_email_address","from_name","automated_reply")}
        slim["text_body"] = (r.get("text_body") or "")[:2000]
        slim["lead"] = r.get("lead")
        rows.append(slim)
    with lock:
        for s in rows:
            out.write(json.dumps(s) + "\n")
        out.flush()
        done[0] += 1
        print(f"[{done[0]}/{len(ids)}] campaign {cid}: {len(rows)} interested ({time.time()-t0:.0f}s)", flush=True)
    return cid, len(rows)

with ThreadPoolExecutor(max_workers=8) as ex:
    res = list(ex.map(work, ids))
json.dump(dict((str(a),b) for a,b in res), open("counts_by_campaign.json","w"), indent=1)
print("TOTAL", sum(b for _, b in res), f"{time.time()-t0:.0f}s", flush=True)
