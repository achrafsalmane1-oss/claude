# -*- coding: utf-8 -*-
"""Haven St Capital -- alerte instantanee sur reponse positive.

Surveille le workspace HSC dans PlusVibe. Des qu'une reponse est etiquetee
INTERESTED, envoie un email d'alerte a ALERT_TO depuis la boite Haven qui a
recu la reponse. Le prospect n'est JAMAIS destinataire : seul ALERT_TO est en
"to", il n'y a ni cc ni bcc.

Variables d'environnement :
  PLUSVIBE_API_KEY  (obligatoire)
  ALERT_TO          (defaut achraf@havenstcapital.com)
  HSC_WORKSPACE_ID  (defaut 6a4d2d81fed50998a91ac742)
  DRY_RUN=1         pour journaliser sans envoyer
"""
import json, os, re, sys, time, urllib.request, urllib.error

KEY   = os.environ.get("PLUSVIBE_API_KEY", "")
BASE  = "https://api.plusvibe.ai/api/v1"
WID   = os.environ.get("HSC_WORKSPACE_ID", "6a4d2d81fed50998a91ac742")
TO    = os.environ.get("ALERT_TO", "achraf@havenstcapital.com")
DRY   = os.environ.get("DRY_RUN", "") not in ("", "0", "false", "False")
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


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


def pv_post(path, body):
    if DRY:
        return 200
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
        headers={"x-api-key": KEY, "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "curl/8.5.0"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print("  envoi refuse:", e.code, e.read()[:200], file=sys.stderr)
        return e.code


def load_state():
    try:
        s = json.load(open(STATE))
    except Exception:
        s = {}
    s.setdefault("alerted", [])
    return s


def save_state(s):
    s["alerted"] = s["alerted"][-2000:]          # borne la taille du fichier
    json.dump(s, open(STATE, "w"), indent=1)


def strip_html(h):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h or "", flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'")
    return re.sub(r"\s+", " ", t).strip()


def fetch_interested():
    out, trail = [], None
    while True:
        p = f"/unibox/emails?workspace_id={WID}&label=INTERESTED" + (f"&page_trail={trail}" if trail else "")
        d = pv_get(p)
        items = d.get("data") or []
        for it in items:
            if it.get("direction") != "IN":
                continue
            out.append(it)
        trail = d.get("page_trail")
        if not trail or not items:
            break
        time.sleep(0.15)
    return out


def alert(it):
    faj = it.get("from_address_json") or [{}]
    name = faj[0].get("name") or ""
    em = (it.get("from_address_email") or "").strip()
    body_txt = it.get("content_preview") or strip_html((it.get("body") or {}).get("html", ""))
    subject = f"REPONSE POSITIVE - {name or em}"
    html = ("Nouvelle reponse positive sur Haven.<br><br>"
            f"<b>Prospect :</b> {name} &lt;{em}&gt;<br>"
            f"<b>Objet d'origine :</b> {it.get('subject','')}<br>"
            f"<b>Boite :</b> {it.get('eaccount','')}<br><br>"
            "--- Message ---<br>" + (body_txt or "")[:2000])
    code = pv_post(f"/unibox/emails/reply?workspace_id={WID}", {
        "reply_to_id": it.get("id"), "from": it.get("eaccount"),
        "to": TO, "cc": "", "subject": subject, "body": html})
    return code in (200, 201)


def main():
    if not KEY:
        print("PLUSVIBE_API_KEY absent.", file=sys.stderr)
        sys.exit(1)
    state = load_state()
    seen = set(state["alerted"])
    items = fetch_interested()
    new = [i for i in items if i.get("id") not in seen]
    print(f"reponses INTERESTED: {len(items)} | nouvelles: {len(new)} | DRY_RUN={DRY}")
    sent = 0
    for it in new:
        if alert(it):
            sent += 1
            state["alerted"].append(it["id"])
            print("  alerte envoyee ->", it.get("from_address_email"))
        else:
            print("  ECHEC alerte ->", it.get("from_address_email"), file=sys.stderr)
        time.sleep(0.3)
    if not DRY:
        save_state(state)
    print(f"alertes envoyees: {sent}")


if __name__ == "__main__":
    try:
        main()
    except PlusVibeDown as e:
        print(f"PLUSVIBE INDISPONIBLE -- aucune alerte, nouvel essai au prochain passage.\n  {e}", file=sys.stderr)
        sys.exit(1)
