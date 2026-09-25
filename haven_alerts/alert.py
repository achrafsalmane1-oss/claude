# -*- coding: utf-8 -*-
"""Haven St Capital -- alerte Slack sur reponse positive.

Surveille le workspace HSC dans PlusVibe. Des qu'une reponse porte le label
INTERESTED, poste le lead dans le canal Slack via un webhook entrant.

Variables d'environnement :
  PLUSVIBE_API_KEY    (obligatoire)
  SLACK_WEBHOOK_URL   (obligatoire) -- webhook entrant du canal #positivereplies
  HSC_WORKSPACE_ID    (defaut 6a4d2d81fed50998a91ac742)
  DRY_RUN=1           journalise sans rien poster
"""
import json, os, re, sys, time, urllib.request, urllib.error

KEY   = os.environ.get("PLUSVIBE_API_KEY", "")
HOOK  = os.environ.get("SLACK_WEBHOOK_URL", "")
BASE  = "https://api.plusvibe.ai/api/v1"
WID   = os.environ.get("HSC_WORKSPACE_ID", "6a4d2d81fed50998a91ac742")
DRY   = os.environ.get("DRY_RUN", "") not in ("", "0", "false", "False")
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

QUOTE = [r"\bOn\s+.{3,200}?\s+wrote\s*:", r"\bLe\s+.{3,200}?\s+a\s+(?:é|e)crit\s*:",
         r"\bFrom\s*:\s*.{0,120}?Sent\s*:", r"\bDe\s*:\s*.{0,120}?(?:Envoy|Date)",
         r"_{10,}", r"-{5,}\s*Original"]


class PlusVibeDown(Exception):
    """PlusVibe n'a rien renvoye d'exploitable apres tous les essais."""


def pv_get(path, retries=5):
    last = ""
    for a in range(retries):
        try:
            req = urllib.request.Request(BASE + path, headers={
                "x-api-key": KEY, "Accept": "application/json", "User-Agent": "curl/8.5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                try: last = f"HTTP {e.code}: {e.read()[:200].decode('utf-8','replace')}"
                except Exception: last = f"HTTP {e.code}"
                time.sleep(min(2 ** a, 10)); continue
            raise
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            if a == retries - 1: break
            time.sleep(2)
    raise PlusVibeDown(f"{path} injoignable apres {retries} essais -- {last or 'aucune reponse'}")


def slack(text):
    if DRY:
        print("  [DRY] " + text.replace("\n", " | ")[:160])
        return True
    data = json.dumps({"text": text}).encode()
    req = urllib.request.Request(HOOK, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    for a in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status == 200
        except Exception as e:
            if a == 3:
                print("  echec Slack:", e, file=sys.stderr)
                return False
            time.sleep(2 * (a + 1))


def clean(it):
    t = it.get("content_preview") or re.sub(r"<[^>]+>", " ", (it.get("body") or {}).get("html", ""))
    t = re.sub(r"&nbsp;|&amp;|&#39;", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    cut = len(t)
    for c in QUOTE:
        m = re.search(c, t, re.I)
        if m: cut = min(cut, m.start())
    return t[:cut].strip()[:700]


def load_state():
    try: s = json.load(open(STATE))
    except Exception: s = {}
    s.setdefault("alerted", [])
    return s


def fetch_interested():
    out, trail = [], None
    while True:
        p = f"/unibox/emails?workspace_id={WID}&label=INTERESTED" + (f"&page_trail={trail}" if trail else "")
        d = pv_get(p)
        items = d.get("data") or []
        out += [i for i in items if i.get("direction") == "IN"]
        trail = d.get("page_trail")
        if not trail or not items: break
        time.sleep(0.15)
    return out


def main():
    if not KEY:
        print("PLUSVIBE_API_KEY absent.", file=sys.stderr); sys.exit(1)
    if not HOOK and not DRY:
        print("SLACK_WEBHOOK_URL absent.", file=sys.stderr); sys.exit(1)
    state = load_state()
    seen = set(state["alerted"])
    items = fetch_interested()
    new = [i for i in items if i.get("id") not in seen]
    print(f"INTERESTED: {len(items)} | nouvelles: {len(new)} | DRY_RUN={DRY}")
    sent = 0
    for it in new:
        fa = (it.get("from_address_json") or [{}])[0]
        name = fa.get("name") or ""
        em = (it.get("from_address_email") or "").strip()
        txt = ("\n".join("> " + l for l in clean(it).split("\n"))) or "> (message vide)"
        msg = (f"🟢 *Nouvelle réponse positive — Haven*\n\n"
               f"*{name or em}* — `{em}`\n"
               f"Objet : {it.get('subject','')}\n"
               f"Boîte : {it.get('eaccount','')}\n"
               f"Reçue : {(it.get('timestamp_created') or '')[:16].replace('T',' ')} UTC\n\n"
               f"{txt}")
        if slack(msg):
            sent += 1
            state["alerted"].append(it["id"])
            print("  poste ->", em)
        else:
            print("  ECHEC ->", em, file=sys.stderr)
        time.sleep(0.3)
    if not DRY:
        state["alerted"] = state["alerted"][-2000:]
        json.dump(state, open(STATE, "w"), indent=1)
    print(f"alertes postees: {sent}")


if __name__ == "__main__":
    try:
        main()
    except PlusVibeDown as e:
        print(f"PLUSVIBE INDISPONIBLE -- aucune alerte, nouvel essai au prochain passage.\n  {e}",
              file=sys.stderr)
        sys.exit(1)
