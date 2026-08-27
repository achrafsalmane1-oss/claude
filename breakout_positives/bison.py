import json, os, sys, time, urllib.parse, urllib.request

BASE = "https://send.breakoutcreatives.com/api"
TOK = os.environ["BISON_TOKEN"]

def get(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + TOK,
        "Accept": "application/json",
    })
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)

def paginate(path, max_pages=10000, **params):
    cursor = None
    pages = 0
    while pages < max_pages:
        p = dict(params)
        if cursor:
            p["cursor"] = cursor
        d = get(path, **p)
        for row in d.get("data", []):
            yield row
        meta = d.get("meta", {}) or {}
        cursor = meta.get("next_cursor")
        pages += 1
        if not cursor:
            break

if __name__ == "__main__":
    print(json.dumps(get(sys.argv[1], **dict(a.split("=",1) for a in sys.argv[2:])), indent=1)[:4000])
