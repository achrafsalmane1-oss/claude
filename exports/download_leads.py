import json, urllib.request, urllib.error, time, csv, os, sys

TOKEN = os.environ["SB_TOKEN"]
BASE = "https://send.shieldsoutbound.com/api/leads?pagination_type=cursor"
OUT = "/home/user/claude/exports/shields_outbound_leads.csv"
STATE = "/home/user/claude/exports/state.json"
LOG = "/home/user/claude/exports/progress.log"

FIELDS = ["id","uuid","first_name","last_name","email","title","company",
          "status","notes","tags","campaigns","campaign_statuses",
          "emails_sent","opens","replies","created_at","updated_at"]

def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    with open(LOG,"a") as f: f.write(line+"\n")
    print(line, flush=True)

def fetch(url, tries=5):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Authorization":f"Bearer {TOKEN}","Accept":"application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2**a; log(f"429 rate-limited, sleep {wait}s"); time.sleep(wait); continue
            raise
        except Exception as e:
            wait = 2**a; log(f"neterr {e}, retry in {wait}s"); time.sleep(wait)
    raise RuntimeError(f"failed after {tries} tries: {url}")

def is_bounced(l):
    if (l.get("status") or "").lower() == "bounced": return True
    for c in (l.get("lead_campaign_data") or []):
        if (c.get("status") or "").lower() == "bounced": return True
    return False

def row(l):
    st = l.get("overall_stats") or {}
    cd = l.get("lead_campaign_data") or []
    return {
        "id": l.get("id"), "uuid": l.get("uuid"),
        "first_name": l.get("first_name"), "last_name": l.get("last_name"),
        "email": l.get("email"), "title": l.get("title"), "company": l.get("company"),
        "status": l.get("status"), "notes": l.get("notes"),
        "tags": "; ".join(t.get("name","") for t in (l.get("tags") or [])),
        "campaigns": "; ".join(str(c.get("campaign_id","")) for c in cd),
        "campaign_statuses": "; ".join(str(c.get("status","")) for c in cd),
        "emails_sent": st.get("emails_sent"), "opens": st.get("opens"), "replies": st.get("replies"),
        "created_at": l.get("created_at"), "updated_at": l.get("updated_at"),
    }

# resume support
url = BASE; kept = 0; bounced = 0; seen = 0
mode = "w"
if os.path.exists(STATE):
    s = json.load(open(STATE))
    if s.get("next"):
        url = s["next"]; kept = s["kept"]; bounced = s["bounced"]; seen = s["seen"]; mode = "a"
        log(f"RESUME seen={seen} kept={kept} bounced={bounced}")

f = open(OUT, mode, newline="", encoding="utf-8")
w = csv.DictWriter(f, fieldnames=FIELDS)
if mode == "w": w.writeheader()

t0 = time.time(); pages = 0
while True:
    d = fetch(url)
    data = d.get("data", [])
    if not isinstance(data, list):
        log(f"UNEXPECTED payload: {str(d)[:300]}"); break
    for l in data:
        seen += 1
        if is_bounced(l): bounced += 1; continue
        w.writerow(row(l)); kept += 1
    pages += 1
    nxt = (d.get("meta") or {}).get("next_cursor")
    nxt_url = f"{BASE}&cursor={nxt}" if nxt else None
    if pages % 50 == 0 or not nxt_url:
        f.flush()
        json.dump({"next":nxt_url,"kept":kept,"bounced":bounced,"seen":seen}, open(STATE,"w"))
        rate = seen/(time.time()-t0+0.01)
        log(f"seen={seen} kept={kept} bounced={bounced} rate={rate:.0f}/s")
    if not nxt_url:
        log(f"DONE seen={seen} kept={kept} bounced={bounced}"); break
    url = nxt_url

f.close()
json.dump({"next":None,"kept":kept,"bounced":bounced,"seen":seen,"done":True}, open(STATE,"w"))
log("COMPLETE")
