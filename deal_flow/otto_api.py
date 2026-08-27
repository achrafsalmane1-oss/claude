import os
import json, urllib.request, urllib.error, time, sys
TOKEN=os.environ.get("OTTO_API_KEY","")
BASE="https://send.ottoresults.com/api"
def get(path, **params):
    q="&".join(f"{k}={v}" for k,v in params.items() if v is not None)
    url=BASE+path+(("?"+q) if q else "")
    for a in range(5):
        try:
            r=urllib.request.Request(url, headers={"Authorization":"Bearer "+TOKEN,"Accept":"application/json","User-Agent":"curl/8.5.0"})
            with urllib.request.urlopen(r, timeout=60) as resp: return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (429,500,502,503,504): time.sleep(min(2**a,20)); continue
            print("HTTP",e.code,url,e.read()[:200].decode(),file=sys.stderr); return {}
        except Exception as ex:
            if a==4: print("ERR",url,ex,file=sys.stderr); return {}
            time.sleep(2)
    return {}
def page_all(path, per_page=100, cap=100000, **params):
    """Walk cursor pagination, return all rows."""
    out=[]; cur=None
    while True:
        d=get(path, per_page=per_page, cursor=cur, **params)
        rows=d.get("data") or []
        out.extend(rows)
        cur=(d.get("meta") or {}).get("next_cursor")
        if not cur or not rows or len(out)>=cap: break
        time.sleep(0.1)
    return out
