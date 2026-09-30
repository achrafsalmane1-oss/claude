import json, os, urllib.request, urllib.error, time
BASE="https://send.breakoutcreatives.com/api"
TOK=os.environ["BISON_TOKEN"]
def day_stats(cid, start, end=None):
    body=json.dumps({"start_date":start,"end_date":end or start}).encode()
    req=urllib.request.Request(f"{BASE}/campaigns/{cid}/stats", data=body, method="POST",
        headers={"Authorization":"Bearer "+TOK,"Accept":"application/json","Content-Type":"application/json"})
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode()).get("data")
        except urllib.error.HTTPError as e:
            if e.code in (404,422): return None
            time.sleep(1.5*(a+1))
        except Exception:
            time.sleep(1.5*(a+1))
    return None
