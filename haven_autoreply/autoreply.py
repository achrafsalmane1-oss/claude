# -*- coding: utf-8 -*-
"""Haven -- de la reponse positive au rendez-vous pose, sans toucher l'inbox.

  reponse positive        -> on propose 3 creneaux reellement libres
  le prospect en accepte  -> on pose le rendez-vous sur Calendly a sa place
  refus / desabonnement   -> on classe, on ne repond pas
  absence du bureau       -> on repousse jusqu'a la date annoncee
  tout le reste           -> on se tait et on alerte

Le prospect ne recoit jamais de lien de reservation : il est trop tentant de
ne pas cliquer. On lui demande seulement de dire oui a une heure.

Variables d'environnement :
  PLUSVIBE_API_KEY   (obligatoire)
  CALENDLY_TOKEN     (obligatoire) jeton personnel, plan payant
  CALENDLY_EVENT_SLUG   defaut haven-intro
  PV_WORKSPACE_ID    defaut HSC
  CAMPAIGN_IDS       ids separes par des virgules ; VIDE = toutes les campagnes
                     du workspace, campagnes futures comprises. Le garde-fou
                     est le workspace : PV_WORKSPACE_ID pointe Haven, jamais
                     un workspace client.
  SKIP_CAMPAIGN_IDS  campagnes a exclure explicitement (ex. un lead magnet ou
                     la reponse demande un travail humain).
  BCC_TO             copie cachee de chaque envoi (defaut achraf@havenstcapital.com)
  ALERT_TO           ou signaler ce qui doit passer par un humain
  MIN_DELAY_MIN / MAX_DELAY_MIN   fenetre d'attente avant de repondre (2-9 min)
  MAX_SENDS          envois automatiques maximum par prospect (defaut 3)
  START_AFTER        OBLIGATOIRE. Horodatage ISO : aucun message anterieur ne
                     sera jamais lu, encore moins traite. C'est la ligne de
                     demarcation avec les fils en cours, traites a la main.
                     Sans cette variable, le robot refuse de demarrer.
  AUTOREPLY_ENABLED=0   coupe-circuit
  DRY_RUN=1          journalise sans rien envoyer ni poser
"""
import json, os, random, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify, calendly

PVKEY = os.environ.get("PLUSVIBE_API_KEY", "")
WID   = os.environ.get("PV_WORKSPACE_ID", "6a4d2d81fed50998a91ac742")
CAMPS = [c.strip() for c in os.environ.get("CAMPAIGN_IDS", "").split(",") if c.strip()]
SKIP  = [c.strip() for c in os.environ.get("SKIP_CAMPAIGN_IDS", "").split(",") if c.strip()]
BCC   = os.environ.get("BCC_TO", "achraf@havenstcapital.com")
ALERT = os.environ.get("ALERT_TO", BCC)
MIND  = int(os.environ.get("MIN_DELAY_MIN", "2"))
MAXD  = int(os.environ.get("MAX_DELAY_MIN", "9"))
MAXS  = int(os.environ.get("MAX_SENDS", "3"))
MAXAL = int(os.environ.get("MAX_ALERTS", "12"))
AFTER = os.environ.get("START_AFTER", "").strip()
ON    = os.environ.get("AUTOREPLY_ENABLED", "1") not in ("0", "false", "False")
DRY   = os.environ.get("DRY_RUN", "") not in ("", "0", "false", "False")
PVBASE = "https://api.plusvibe.ai/api/v1"
STATE  = os.path.join(HERE, "state.json")
LOG    = os.path.join(HERE, "audit.log")


class PlusVibeDown(Exception):
    pass


def audit(**kw):
    kw["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- PlusVibe
def pv(method, path, body=None, retries=5):
    last = ""
    for a in range(retries):
        try:
            req = urllib.request.Request(
                PVBASE + path,
                data=json.dumps(body).encode() if body is not None else None,
                method=method,
                headers={"x-api-key": PVKEY, "Accept": "application/json",
                         "Content-Type": "application/json", "User-Agent": "curl/8.5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503):
                last = f"HTTP {e.code}: {detail}"
                time.sleep(min(2 ** a, 10)); continue
            raise PlusVibeDown(f"{method} {path} -> HTTP {e.code}: {detail}")
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            if a == retries - 1:
                break
            time.sleep(2)
    raise PlusVibeDown(f"{path} injoignable -- {last}")


def inbound():
    """Messages entrants des campagnes surveillees, du plus ancien au plus recent."""
    out, trail = [], None
    while True:
        p = f"/unibox/emails?workspace_id={WID}" + (f"&page_trail={trail}" if trail else "")
        d = pv("GET", p)
        items = d.get("data") or []
        for i in items:
            if i.get("direction") != "IN":
                continue
            if AFTER and (i.get("timestamp_created") or "") <= AFTER:
                continue          # anterieur a la mise en service : jamais touche
            cid = i.get("campaign_id")
            if CAMPS and cid not in CAMPS:
                continue          # liste blanche seulement si elle est fournie
            if cid in SKIP:
                continue
            out.append(i)
        trail = d.get("page_trail")
        if not trail or not items:
            break
        time.sleep(0.15)
    out.sort(key=lambda i: i.get("timestamp_created") or "")
    return out


def send(rec, text):
    if DRY:
        print(f"    [DRY] -> {rec['email']} : {text[:80]}...")
        return True
    body = {"reply_to_id": rec["reply_to_id"], "from": rec["eaccount"],
            "to": rec["email"], "cc": "", "bcc": BCC,
            "subject": rec.get("subject", ""),
            "body": text.replace("\n", "<br>")}
    try:
        pv("POST", f"/unibox/emails/reply?workspace_id={WID}", body=body)
        return True
    except Exception as e:
        print("    envoi refuse:", e, file=sys.stderr)
        return False


# -------------------------------------------------------------------- etat
def load():
    try:
        s = json.load(open(STATE))
    except Exception:
        s = {}
    s.setdefault("seen", [])      # ids de messages deja lus
    s.setdefault("leads", {})     # email -> dossier
    s.setdefault("suppressed", [])
    return s


def save(s):
    s["seen"] = s["seen"][-5000:]
    json.dump(s, open(STATE, "w"), indent=1, ensure_ascii=False)


# ---------------------------------------------------------------- redaction
def fmt_slots(slots, tz_label):
    lines = []
    for t in slots:
        lines.append("- " + t.strftime("%A %d %B, %-I:%M %p") + f" {tz_label}")
    return "\n".join(lines)


def msg_slots(first, slots, tz_label):
    return (f"Hi {first},\n\n"
            "Great - happy to walk you through it.\n\n"
            "Do any of these work for a quick 20 minutes?\n\n"
            f"{fmt_slots(slots, tz_label)}\n\n"
            "Just reply with whichever suits and I'll send the invite.\n\n"
            "Achraf")


def msg_booked(first, when, tz_label):
    return (f"Hi {first},\n\n"
            f"Booked - {when.strftime('%A %d %B at %-I:%M %p')} {tz_label}. "
            "The calendar invite is on its way with the call link.\n\n"
            "Talk then.\n\n"
            "Achraf")


def msg_retry(first, slots, tz_label):
    return (f"Hi {first},\n\n"
            "No problem. Any of these instead?\n\n"
            f"{fmt_slots(slots, tz_label)}\n\n"
            "Achraf")


# ------------------------------------------------------------------ moteur
def first_name(it, email):
    lead = it.get("lead")
    # selon les endpoints, "lead" est tantot l'objet, tantot son seul identifiant
    lead = lead if isinstance(lead, dict) else {}
    n = (lead.get("first_name") or "").strip()
    if n:
        return n
    fa = (it.get("from_address_json") or [{}])[0]
    n = (fa.get("name") or "").strip()
    return n.split(" ")[0] if n else email.split("@")[0]


def due(ts_iso):
    """Attendre quelques minutes : une reponse a la seconde se lit comme un robot."""
    try:
        t = datetime.fromisoformat((ts_iso or "").replace("Z", "+00:00"))
    except Exception:
        return True
    wait = timedelta(minutes=random.randint(MIND, MAXD))
    return datetime.now(timezone.utc) - t >= wait


def escalate(rec, why, text):
    # compteur porte par la fonction : simple, et remis a zero a chaque passage
    """Signale par email, pas seulement dans le journal.

    L'envoi passe par le meme point de sortie que les reponses aux prospects,
    mais adresse a ALERT_TO seul : le prospect n'est ni en copie ni en copie
    cachee. On garde ainsi le fil et son contexte sous les yeux.
    """
    email = rec["email"]
    audit(event="escalade", email=email, why=why)
    print(f"    humain requis ({why}) -> {email}")
    if escalate.sent >= MAXAL:
        print("    (plafond d'alertes atteint, celle-ci reste au journal)")
        audit(event="alerte_plafonnee", email=email)
        return
    escalate.sent += 1
    body = (f"Reponse a traiter a la main.\n\n"
            f"Prospect : {email}\n"
            f"Objet    : {rec.get('subject','')}\n"
            f"Raison   : {why}\n\n"
            f"Son message :\n{(text or '').strip()[:1500]}\n\n"
            f"Le robot n'a rien repondu et ne repondra plus sur ce fil.")
    if DRY:
        print(f"    [DRY] alerte -> {ALERT}")
        return
    try:
        pv("POST", f"/unibox/emails/reply?workspace_id={WID}", body={
            "reply_to_id": rec["reply_to_id"], "from": rec["eaccount"],
            "to": ALERT, "cc": "", "bcc": "",
            "subject": "A traiter : " + (rec.get("subject") or email),
            "body": body.replace("\n", "<br>")})
    except Exception as e:
        print("    alerte non envoyee:", e, file=sys.stderr)
        audit(event="alerte_non_envoyee", email=email, err=str(e))


def run():
    if not ON:
        print("AUTOREPLY_ENABLED=0 -- rien ne part."); return
    if not AFTER:
        print("START_AFTER absent -- refus de demarrer : sans date de mise en "
              "service le robot pourrait repondre a des fils deja traites.",
              file=sys.stderr)
        return
    if not BCC:
        print("BCC_TO absent -- refus d'envoyer sans copie cachee.", file=sys.stderr)
        return
    scope = ", ".join(CAMPS) if CAMPS else "toutes les campagnes du workspace"
    print(f"Perimetre: {scope}" + (f" (sauf {', '.join(SKIP)})" if SKIP else ""))
    st = load()
    seen = set(st["seen"])
    sup = set(st["suppressed"])

    user = calendly.me()
    tz = user.get("timezone") or "UTC"
    et = calendly.event_type(user["uri"])
    et_uri = et["uri"]
    tz_label = tz.split("/")[-1].replace("_", " ")
    print(f"Calendly: {et.get('name')} ({et.get('duration')} min), fuseau {tz}")

    escalate.sent = 0
    msgs = inbound()
    # Double securite : START_AFTER a deja ecarte l'historique a la lecture ;
    # si malgre tout le premier passage voit des messages, on les enregistre
    # sans y repondre.
    if not st["seen"] and not st["leads"] and msgs:
        st["seen"] = [i["id"] for i in msgs if i.get("id")]
        if not DRY:
            save(st)
        print(f"amorcage : {len(st['seen'])} messages marques comme lus, "
              "aucune reponse envoyee.")
        return

    acted = 0
    alerts = 0
    for it in msgs:
        mid = it.get("id")
        if not mid or mid in seen:
            continue
        email = (it.get("from_address_email") or "").strip().lower()
        if not email or email in sup:
            seen.add(mid); continue

        text = it.get("content_preview") or re.sub(
            r"<[^>]+>", " ", (it.get("body") or {}).get("html", ""))
        who = first_name(it, email)
        lead = st["leads"].setdefault(email, {"stage": "new", "sends": 0, "slots": []})

        if lead["stage"] in ("booked", "dead", "escalated"):
            seen.add(mid); continue
        if lead["sends"] >= MAXS:
            escalate({"email": email, "eaccount": it.get("eaccount"), "reply_to_id": mid,
                      "subject": it.get("subject", "")}, "plafond d'envois atteint", text)
            lead["stage"] = "escalated"; seen.add(mid); continue
        if not due(it.get("timestamp_created")):
            continue                      # on repassera au prochain tour

        auto_hdr = bool(re.search(r"auto[- ]?(?:submitted|reply|generated)",
                                  json.dumps(it.get("body") or {})[:2000], re.I))
        what = classify.intent(text, has_auto_header=auto_hdr)
        rec = {"email": email, "eaccount": it.get("eaccount"), "reply_to_id": mid,
               "subject": it.get("subject", "")}
        print(f"  {email} [{lead['stage']}] -> {what}")

        if what == "optout":
            lead["stage"] = "dead"; sup.add(email)
            audit(event="desabonnement", email=email)

        elif what == "negative":
            lead["stage"] = "dead"
            audit(event="refus", email=email)

        elif what == "out_of_office":
            audit(event="absence", email=email)      # on ne repond pas a un robot

        elif what in ("human", "unclear"):
            lead["stage"] = "escalated"
            escalate(rec, what, text)

        elif what == "positive":
            if lead["stage"] == "slots_sent":
                # deja relance : on attend un creneau, pas un nouveau oui
                lead["stage"] = "escalated"; escalate(rec, "oui sans creneau", text)
            else:
                slots = calendly.spread(calendly.available(et_uri), 3)
                if not slots:
                    lead["stage"] = "escalated"; escalate(rec, "aucune dispo", text)
                elif send(rec, msg_slots(who, slots, tz_label)):
                    lead.update(stage="slots_sent", sends=lead["sends"] + 1,
                                slots=[s.isoformat() for s in slots],
                                slots_at=datetime.now(timezone.utc).isoformat())
                    acted += 1
                    audit(event="creneaux_proposes", email=email,
                          slots=[s.isoformat() for s in slots])

        seen.add(mid)

        # Un message peut accepter un creneau sans etre franchement "positif".
        # Mais seulement s'il est arrive APRES notre proposition : sinon le
        # message qui declenche la proposition sert aussi a poser le rendez-vous,
        # et un "ok merci" devient une invitation ferme.
        after_slots = False
        if lead.get("slots_at"):
            try:
                after_slots = (it.get("timestamp_created") or "") > lead["slots_at"]
            except Exception:
                after_slots = False
        if lead["stage"] == "slots_sent" and after_slots \
           and what in ("positive", "unclear", "human"):
            slots = [datetime.fromisoformat(x) for x in lead.get("slots", [])]
            when, why = classify.pick_slot(text, slots)
            if when and calendly.still_free(et_uri, when):
                if DRY:
                    print(f"    [DRY] poserait {when.isoformat()} pour {email}")
                    lead["stage"] = "booked"; acted += 1
                else:
                    try:
                        calendly.book(et_uri, when, who, email, tz,
                                      location_kind=None)
                        send(rec, msg_booked(who, when.astimezone(), tz_label))
                        lead.update(stage="booked", sends=lead["sends"] + 1)
                        acted += 1
                        audit(event="rendez_vous_pose", email=email, when=when.isoformat())
                        print(f"    pose -> {when.isoformat()}")
                    except Exception as e:
                        lead["stage"] = "escalated"
                        escalate(rec, f"echec Calendly: {e}", text)
            elif when:
                fresh = calendly.spread(calendly.available(et_uri), 3)
                if fresh and send(rec, msg_retry(who, fresh, tz_label)):
                    lead.update(sends=lead["sends"] + 1,
                                slots=[s.isoformat() for s in fresh])
                    acted += 1
                    audit(event="creneau_pris_entre_temps", email=email)
            elif "refuse" in why:
                fresh = calendly.spread(calendly.available(et_uri, days=10), 3)
                if fresh and send(rec, msg_retry(who, fresh, tz_label)):
                    lead.update(sends=lead["sends"] + 1,
                                slots=[s.isoformat() for s in fresh])
                    acted += 1

    st["seen"] = list(seen)
    st["suppressed"] = sorted(sup)
    if not DRY:
        save(st)
    print(f"actions: {acted} | DRY_RUN={DRY}")


if __name__ == "__main__":
    for k, v in (("PLUSVIBE_API_KEY", PVKEY), ("CALENDLY_TOKEN", calendly.TOKEN)):
        if not v:
            print(f"{k} absent.", file=sys.stderr); sys.exit(1)
    try:
        run()
    except (PlusVibeDown, calendly.CalendlyError) as e:
        print(f"INDISPONIBLE -- rien traite, nouvel essai au prochain passage.\n  {e}",
              file=sys.stderr)
        sys.exit(1)
