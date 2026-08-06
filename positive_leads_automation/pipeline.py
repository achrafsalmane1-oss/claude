# -*- coding: utf-8 -*-
"""
Positive-lead pipeline (PlusVibe -> GHL -> reply+CC), going forward.

For every NEW positive (INTERESTED) reply in the PlusVibe unibox, across both
workspaces (Cold-B2B + Warm-B2C), this script:
  1. Creates/updates the contact in GHL  (source=PlusVibe, tags NEW LEAD +
     Investor LQ + language, round-robin assigned by language).
  2. Sends the prospect a reply from PlusVibe in their language (phone number +
     availability request), CC the assigned agent + Thibaut.
  3. Records the email in state.json so it is never processed twice.

Dedup + round-robin position are persisted in state.json (committed back by the
GitHub Actions workflow), so re-runs are idempotent and assignment stays even.

Credentials come from environment variables (repo secrets):
  PLUSVIBE_API_KEY, GHL_TOKEN, GHL_LOCATION_ID
Optional: THIBAUT_EMAIL (defaults to tgueant@landquire.com)

Set DRY_RUN=1 to log what would happen without creating contacts or sending mail.
"""
import json, os, time, subprocess, urllib.request, urllib.error, sys, re
from collections import Counter

PVKEY = os.environ.get("PLUSVIBE_API_KEY", "")
PVBASE = "https://api.plusvibe.ai/api/v1"
PIT = os.environ.get("GHL_TOKEN", "")
LOC = os.environ.get("GHL_LOCATION_ID", "bu3JqdsMUIMYcVSRBSXs")
THIB = os.environ.get("THIBAUT_EMAIL", "tgueant@landquire.com")
DRY = os.environ.get("DRY_RUN", "") not in ("", "0", "false", "False")
GHLBASE = "https://services.leadconnectorhq.com"

WS = {"B2B": "6a3179f64517eb5ecd7c1642", "B2C": "6a4645cc305ead1e2243e94f"}

# Round-robin agent pools by language: (name, GHL user id)
FR = [("Fabienne", "aBXFUOaJTNd3S6xuoe2p"), ("Mathieu", "NSXvGpjwu2kq3I6bhCO5"),
      ("PaulG", "Qw0kNzYf8z7wB8ACQEWZ"), ("PierreR", "fSr7OAL4VXxZIngOL7Ey"),
      ("Timothee", "aCKmPd1GI1IikvbT3ERB"), ("PierreLoup", "lOSuNBiTo8BlFi5gAHdF"),
      ("Kevin", "7l60QOUa5c2EvVr96frH"), ("Clement", "bOQhh8LhNjSOT1CvxtYW")]
BR = [("Herminia", "PXQVZgou0EbKB18H5Wh3"), ("Luci", "tvp9ana9YZWwFBUyXMf0"),
      ("Fabiano", "xUvVav7DQywx2WYZnLMI")]
EN = [("Mathieu", "NSXvGpjwu2kq3I6bhCO5"), ("PierreR", "fSr7OAL4VXxZIngOL7Ey"),
      ("Kevin", "7l60QOUa5c2EvVr96frH"), ("Sophie", "PIudlTQkBqQCWJ2bVL0l")]
ES = [("Carlos", "fQjewvPSzRh3ui2ZCf2W")]
POOLS = {"FR": FR, "PT": BR, "EN": EN, "ES": ES}

# GHL user id -> email (for CC), used to CC the assigned agent
UID2EMAIL = {
    "aBXFUOaJTNd3S6xuoe2p": "fdepart@landquire.com", "NSXvGpjwu2kq3I6bhCO5": "mverloove@landquire.com",
    "Qw0kNzYf8z7wB8ACQEWZ": "pgeorges@landquire.com", "fSr7OAL4VXxZIngOL7Ey": "prizk@landquire.com",
    "aCKmPd1GI1IikvbT3ERB": "tcarrel@landquire.com", "lOSuNBiTo8BlFi5gAHdF": "pbaudreux@landquire.com",
    "7l60QOUa5c2EvVr96frH": "kevinlanson@landquire.com", "bOQhh8LhNjSOT1CvxtYW": "cdiot@landquire.com",
    "PXQVZgou0EbKB18H5Wh3": "hmoraes@landquire.com", "tvp9ana9YZWwFBUyXMf0": "lferraz@landquire.com",
    "xUvVav7DQywx2WYZnLMI": "fsantos@landquire.com", "PIudlTQkBqQCWJ2bVL0l": "splummer@landquire.com",
    "fQjewvPSzRh3ui2ZCf2W": "carlosurdinineasejas@gmail.com"}

BODY = {
'FR': "Bonjour {fn},<br><br>Je vous remercie pour votre reponse.<br><br>Pourriez-vous, s'il vous plait, me communiquer le numero de telephone sur lequel vous etes le plus facilement joignable, ainsi qu'un ou deux creneaux de disponibilite, en heure de France, pour un echange demain ?<br><br>Une fois le creneau convenu, je vous adresserai par e-mail une invitation afin que notre echange, par telephone ou en visioconference, puisse etre directement integre a nos agendas respectifs.<br><br>Bien cordialement,<br>Thibaut Gueant",
'EN': "Hello {fn},<br><br>Thank you for your reply.<br><br>Could you please share the phone number where you are most easily reachable, along with one or two availability slots (France time) for a call tomorrow?<br><br>Once we agree on a slot, I will send you a calendar invitation so that our call, by phone or video, is added directly to both our agendas.<br><br>Best regards,<br>Thibaut Gueant",
'ES': "Hola {fn},<br><br>Gracias por su respuesta.<br><br>Podria indicarme el numero de telefono en el que es mas facil localizarle, asi como uno o dos horarios de disponibilidad (hora de Francia) para hablar manana?<br><br>Una vez acordado el horario, le enviare una invitacion por correo para que nuestra llamada, por telefono o videoconferencia, quede integrada en ambas agendas.<br><br>Un cordial saludo,<br>Thibaut Gueant",
'PT': "Ola {fn},<br><br>Obrigado pela sua resposta.<br><br>Poderia indicar-me o numero de telefone onde e mais facilmente contactavel, bem como um ou dois horarios de disponibilidade (hora de Franca) para uma conversa amanha?<br><br>Assim que combinarmos o horario, enviar-lhe-ei um convite por e-mail para que a nossa conversa, por telefone ou videochamada, fique integrada nas nossas agendas.<br><br>Com os melhores cumprimentos,<br>Thibaut Gueant"}

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


def pv_get(path, retries=6):
    for a in range(retries):
        try:
            req = urllib.request.Request(PVBASE + path,
                headers={"x-api-key": PVKEY, "Accept": "application/json", "User-Agent": "curl/8.5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                time.sleep(min(2 ** a, 15)); continue
            raise
        except Exception:
            if a == retries - 1: raise
            time.sleep(2)


def pv_post(path, body):
    if DRY:
        return 200, "DRY_RUN"
    req = urllib.request.Request(PVBASE + path, data=json.dumps(body).encode(), method="POST",
        headers={"x-api-key": PVKEY, "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "curl/8.5.0"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.getcode(), r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def ghl_upsert(body):
    if DRY:
        return {"contact": {"id": "DRY_RUN"}}
    cmd = ["curl", "-s", "-X", "POST", GHLBASE + "/contacts/upsert",
           "-H", "Authorization: Bearer " + PIT, "-H", "Version: 2021-07-28",
           "-H", "Content-Type: application/json", "-H", "Accept: application/json",
           "-d", json.dumps(body)]
    for a in range(4):
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        try:
            return json.loads(out.stdout)
        except Exception:
            if a == 3:
                return {"error": out.stdout[:150]}
            time.sleep(2)


def lang_of(name):
    n = (name or "").upper()
    for lg in ("FR", "EN", "ES", "PT"):
        if n.startswith(lg + " ") or n.startswith(lg + "-"):
            return lg
    return "FR"


def strip_html(h):
    return re.sub(r"<[^>]+>", " ", h or "").replace("&nbsp;", " ")


def firstname(email):
    tok = email.split("@")[0].replace(".", " ").replace("_", " ").replace("-", " ").split()
    return tok[0].capitalize() if tok else ""


def load_state():
    try:
        s = json.load(open(STATE_PATH))
    except Exception:
        s = {}
    s.setdefault("processed", [])
    s.setdefault("rr", {"FR": 0, "PT": 0, "EN": 0, "ES": 0})
    return s


def save_state(s):
    s["processed"] = sorted(set(s["processed"]))
    json.dump(s, open(STATE_PATH, "w"), ensure_ascii=False, indent=0)


def campaign_langs():
    """map campaign_id -> language, from campaign names on both workspaces."""
    cl = {}
    for wid in WS.values():
        try:
            for c in pv_get(f"/campaign/list?workspace_id={wid}&limit=100"):
                cl[c["id"]] = lang_of(c.get("name", ""))
        except Exception as e:
            print("campaign list err", e, file=sys.stderr)
    return cl


def fetch_new_positives(cl, seen):
    """Return list of new INTERESTED replies not yet in `seen`."""
    out = {}
    for seg, wid in WS.items():
        trail = None
        while True:
            path = f"/unibox/emails?workspace_id={wid}&label=INTERESTED" + (f"&page_trail={trail}" if trail else "")
            d = pv_get(path)
            data = d.get("data", [])
            for it in data:
                if it.get("direction") != "IN" or it.get("label") != "INTERESTED":
                    continue
                em = (it.get("from_address_email") or "").strip().lower()
                if not em or "landquire" in em or em in seen or em in out:
                    continue
                out[em] = {
                    "email": em, "seg": seg, "wid": wid,
                    "lang": cl.get(it.get("campaign_id"), "FR"),
                    "reply_to_id": it.get("id"), "eaccount": it.get("eaccount"),
                    "subject": it.get("subject") or "",
                }
            trail = d.get("page_trail")
            if not trail or not data:
                break
            time.sleep(0.15)
    return list(out.values())


def agent_for(lang, rr):
    pool = POOLS.get(lang, EN)
    idx = rr.get(lang, 0) % len(pool)
    rr[lang] = rr.get(lang, 0) + 1
    return pool[idx]


def main():
    if not PVKEY or not PIT:
        print("Missing PLUSVIBE_API_KEY or GHL_TOKEN in environment.", file=sys.stderr)
        sys.exit(1)
    state = load_state()
    seen = set(state["processed"])
    cl = campaign_langs()
    new = fetch_new_positives(cl, seen)
    print(f"New positives to process: {len(new)}  (DRY_RUN={DRY})")
    if not new:
        return
    done = []
    for l in new:
        lang = l["lang"] if l["lang"] in BODY else "FR"
        aname, aid = agent_for(lang, state["rr"])
        fn = firstname(l["email"])
        # 1. GHL contact
        r = ghl_upsert({
            "locationId": LOC, "email": l["email"], "firstName": fn,
            "source": "PlusVibe",
            "tags": ["NEW LEAD", "Investor LQ", lang, "positive-reply", "otto-recovery"],
            "assignedTo": aid})
        if not (r.get("contact") or {}).get("id"):
            print("  GHL FAIL", l["email"], str(r)[:120], file=sys.stderr)
            continue
        # 2. reply + CC assigned agent + Thibaut
        agent_email = UID2EMAIL.get(aid)
        cc = THIB if not agent_email or agent_email == THIB else f"{agent_email}, {THIB}"
        subj = l["subject"] or "Re:"
        if not subj.lower().startswith("re"):
            subj = "Re: " + subj
        code, resp = pv_post(f"/unibox/emails/reply?workspace_id={l['wid']}", {
            "reply_to_id": l["reply_to_id"], "from": l["eaccount"], "to": l["email"],
            "subject": subj, "body": BODY[lang].format(fn=fn), "cc": cc})
        if code in (200, 201):
            state["processed"].append(l["email"])
            done.append((l["email"], lang, aname))
        else:
            print("  REPLY FAIL", l["email"], code, resp, file=sys.stderr)
        time.sleep(0.3)
    if not DRY:
        save_state(state)
    print("Processed:", len(done))
    print("by lang:", dict(Counter(x[1] for x in done)))
    print("by agent:", dict(Counter(x[2] for x in done)))


if __name__ == "__main__":
    main()
