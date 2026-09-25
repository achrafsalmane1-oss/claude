# -*- coding: utf-8 -*-
"""Haven St Capital -- pont bidirectionnel PlusVibe <-> Slack.

Sens 1 (entrant)  : toute reponse etiquetee INTERESTED dans le workspace HSC
                    est postee dans le canal Slack. Le fil Slack devient le
                    point de discussion de ce prospect.
Sens 2 (sortant)  : tout message ecrit par un humain DANS ce fil Slack est
                    envoye au prospect via PlusVibe, avec BCC_TO en copie
                    cachee pour pouvoir reprendre l'echange par email.

Le prospect ne voit jamais Slack. Les messages du bot ne sont jamais renvoyes.

Variables d'environnement :
  PLUSVIBE_API_KEY   (obligatoire)
  SLACK_BOT_TOKEN    (obligatoire) jeton xoxb- de l'app Slack
  SLACK_CHANNEL_ID   (defaut C0C4L761EMA -- #positivereplies)
  SLACK_MENTION      (defaut U0C5AT75UCQ) identifiant Slack mentionne sur chaque
                     alerte, pour declencher la notification telephone
  BCC_TO             (defaut achraf@havenstcapital.com)
  HSC_WORKSPACE_ID   (defaut 6a4d2d81fed50998a91ac742)
  DRY_RUN=1          journalise sans rien envoyer
"""
import json, os, re, sys, time, urllib.request, urllib.error, urllib.parse

KEY   = os.environ.get("PLUSVIBE_API_KEY", "")
TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
CHAN  = os.environ.get("SLACK_CHANNEL_ID", "C0C4L761EMA")
WHO   = os.environ.get("SLACK_MENTION", "U0C5AT75UCQ")
BCC   = os.environ.get("BCC_TO", "achraf@havenstcapital.com")
WID   = os.environ.get("HSC_WORKSPACE_ID", "6a4d2d81fed50998a91ac742")
DRY   = os.environ.get("DRY_RUN", "") not in ("", "0", "false", "False")
BASE  = "https://api.plusvibe.ai/api/v1"
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

QUOTE = [r"\bOn\s+.{3,200}?\s+wrote\s*:", r"\bLe\s+.{3,200}?\s+a\s+(?:é|e)crit\s*:",
         r"\bFrom\s*:\s*.{0,120}?Sent\s*:", r"\bDe\s*:\s*.{0,120}?(?:Envoy|Date)",
         r"_{10,}", r"-{5,}\s*Original"]


class PlusVibeDown(Exception):
    """PlusVibe n'a rien renvoye d'exploitable apres tous les essais."""


# ---------------------------------------------------------------- PlusVibe
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


def pv_reply(rec, text):
    """Envoie le message au prospect, avec l'utilisateur en copie cachee."""
    if DRY:
        print(f"  [DRY] -> {rec['email']} (bcc {BCC}) : {text[:70]}")
        return True
    body = {"reply_to_id": rec["reply_to_id"], "from": rec["eaccount"],
            "to": rec["email"], "cc": "", "bcc": BCC,
            "subject": rec.get("subject", ""), "body": text.replace("\n", "<br>")}
    req = urllib.request.Request(BASE + f"/unibox/emails/reply?workspace_id={WID}",
        data=json.dumps(body).encode(), method="POST",
        headers={"x-api-key": KEY, "Content-Type": "application/json", "User-Agent": "curl/8.5.0"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status in (200, 201)
    except urllib.error.HTTPError as e:
        print("  envoi refuse:", e.code, e.read()[:200], file=sys.stderr)
        return False


# -------------------------------------------------------------------- Slack
def slack(method, payload=None, get=False):
    url = "https://slack.com/api/" + method
    if get:
        url += "?" + urllib.parse.urlencode(payload or {})
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
    else:
        req = urllib.request.Request(url, data=json.dumps(payload or {}).encode(), method="POST",
            headers={"Authorization": "Bearer " + TOKEN,
                     "Content-Type": "application/json; charset=utf-8"})
    for a in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read())
                if not d.get("ok"):
                    print(f"  slack {method}: {d.get('error')}", file=sys.stderr)
                return d
        except Exception as e:
            if a == 3:
                print(f"  slack {method} echec: {e}", file=sys.stderr)
                return {"ok": False}
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


# -------------------------------------------------------------------- etat
def load_state():
    try: s = json.load(open(STATE))
    except Exception: s = {}
    s.setdefault("alerted", [])     # ids de messages PlusVibe deja postes
    s.setdefault("threads", {})     # ts Slack -> contexte du prospect
    return s


def save_state(s):
    s["alerted"] = s["alerted"][-2000:]
    json.dump(s, open(STATE, "w"), indent=1, ensure_ascii=False)


# ------------------------------------------------------------ sens entrant
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


def post_new(state):
    """Poste chaque message entrant jamais vu.

    Premier message d'un prospect  -> nouveau message racine dans le canal.
    Message suivant du meme prospect -> reponse DANS son fil existant, et le
    fil pointe desormais vers ce dernier message (c'est a lui qu'on repond).
    """
    seen = set(state["alerted"])
    new = [i for i in fetch_interested() if i.get("id") not in seen]
    # du plus ancien au plus recent : le fil existe avant ses relances
    new.sort(key=lambda i: i.get("timestamp_created") or "")
    by_email = {}
    for ts, rec in state["threads"].items():
        by_email[(rec.get("email") or "").lower()] = (ts, rec)
    posted = 0
    for it in new:
        fa = (it.get("from_address_json") or [{}])[0]
        name = fa.get("name") or ""
        em = (it.get("from_address_email") or "").strip()
        quoted = "\n".join("> " + l for l in (clean(it) or "(message vide)").split("\n"))
        when = (it.get("timestamp_created") or "")[:16].replace("T", " ")
        ping = f"<@{WHO}> " if WHO else ""
        prev = by_email.get(em.lower())

        if prev:                                  # relance dans un fil connu
            ts, rec = prev
            msg = (f"{ping}↩️ *{name or em} a répondu de nouveau*\n"
                   f"Reçue : {when} UTC\n\n{quoted}\n\n"
                   f"💬 Réponds dans ce fil comme d'habitude.")
            if DRY:
                print("  [DRY] relance dans le fil ->", em); posted += 1
                state["alerted"].append(it["id"]); continue
            r = slack("chat.postMessage", {"channel": CHAN, "thread_ts": ts,
                                           "text": msg, "reply_broadcast": True})
            if r.get("ok"):
                posted += 1
                state["alerted"].append(it["id"])
                rec["reply_to_id"] = it.get("id")   # repondre au dernier message
                rec["subject"] = it.get("subject", rec.get("subject", ""))
                rec["eaccount"] = it.get("eaccount") or rec.get("eaccount")
                print("  relance postee ->", em)
            time.sleep(0.4)
            continue

        msg = (f"{ping}🟢 *Nouvelle réponse positive — Haven*\n\n"
               f"*{name or em}* — `{em}`\n"
               f"Objet : {it.get('subject','')}\n"
               f"Boîte : {it.get('eaccount','')}\n"
               f"Reçue : {when} UTC\n\n"
               f"{quoted}\n\n"
               f"💬 *Pour répondre :* écris directement dans ce fil. "
               f"Ton message part au prospect depuis la boîte Haven, "
               f"et tu reçois une copie cachée sur {BCC}.")
        if DRY:
            print("  [DRY] post Slack ->", em); posted += 1
            state["alerted"].append(it["id"])
            by_email[em.lower()] = ("dry-" + it["id"], {"email": em})
            continue
        r = slack("chat.postMessage", {"channel": CHAN, "text": msg})
        if r.get("ok"):
            posted += 1
            state["alerted"].append(it["id"])
            rec = {"email": em, "eaccount": it.get("eaccount"),
                   "reply_to_id": it.get("id"), "subject": it.get("subject", ""),
                   "sent": []}
            state["threads"][r["ts"]] = rec
            by_email[em.lower()] = (r["ts"], rec)
            print("  poste ->", em)
        time.sleep(0.4)
    return posted


# ------------------------------------------------------------ sens sortant
def push_replies(state):
    me = slack("auth.test", {}, get=True).get("user_id") if not DRY else None
    sent = 0
    for ts, rec in list(state["threads"].items()):
        d = slack("conversations.replies", {"channel": CHAN, "ts": ts, "limit": 50}, get=True)
        if not d.get("ok"): continue
        for m in d.get("messages", []):
            if m.get("ts") == ts:            # le message d'alerte lui-meme
                continue
            if m.get("bot_id") or m.get("user") == me or m.get("subtype"):
                continue                      # jamais renvoyer nos propres messages
            if m["ts"] in rec["sent"]:
                continue
            text = (m.get("text") or "").strip()
            if not text:
                continue
            if pv_reply(rec, text):
                sent += 1
                rec["sent"].append(m["ts"])
                if not DRY:
                    slack("chat.postMessage", {"channel": CHAN, "thread_ts": ts,
                          "text": f"✅ Envoyé à {rec['email']} — tu es en copie cachée sur {BCC}"})
                print("  envoye ->", rec["email"])
            else:
                if not DRY:
                    slack("chat.postMessage", {"channel": CHAN, "thread_ts": ts,
                          "text": "⚠️ L'envoi a échoué, le prospect n'a rien reçu."})
            time.sleep(0.3)
    return sent


def main():
    if not KEY:
        print("PLUSVIBE_API_KEY absent.", file=sys.stderr); sys.exit(1)
    if not TOKEN and not DRY:
        print("SLACK_BOT_TOKEN absent.", file=sys.stderr); sys.exit(1)
    state = load_state()
    p = post_new(state)
    s = push_replies(state)
    if not DRY:
        save_state(state)
    print(f"nouvelles reponses postees: {p} | messages envoyes aux prospects: {s} | DRY_RUN={DRY}")


if __name__ == "__main__":
    try:
        main()
    except PlusVibeDown as e:
        print(f"PLUSVIBE INDISPONIBLE -- rien traite, nouvel essai au prochain passage.\n  {e}",
              file=sys.stderr)
        sys.exit(1)
