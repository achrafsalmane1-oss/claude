# -*- coding: utf-8 -*-
"""
Positive-lead pipeline (PlusVibe -> GHL -> reply+CC), going forward.

For every NEW positive (INTERESTED) reply in the PlusVibe unibox, across both
workspaces (Cold-B2B + Warm-B2C), this script:
  1. Looks the contact up in GHL first.
       - If it already exists AND already has an owner (assignedTo), that owner
         is PRESERVED -- the round-robin never touches an already-assigned lead.
       - Only genuinely new / unassigned contacts get a round-robin owner.
     The contact is upserted with source=PlusVibe + tags (NEW LEAD + Investor LQ
     + language); assignedTo is sent ONLY when we are assigning a new lead.
  2. Sends the prospect a reply from PlusVibe in their language, using the
     prospect's REAL first name (from the reply's display name), and CCs the
     lead's actual owner (existing owner if any, else the new round-robin agent)
     + Thibaut.
  3. Records the email in state.json so it is never processed twice.

Two bugs this version fixes vs the first cut:
  * Greeting used the email prefix ("pfpelletier@..." -> "Pfpelletier"); it now
    uses the real display name and falls back to a plain "Bonjour," when there
    is no usable name -- never a mangled prefix.
  * Round-robin overwrote existing owners; it now preserves them.

Credentials come from environment variables (repo secrets):
  PLUSVIBE_API_KEY, GHL_TOKEN, GHL_LOCATION_ID
Optional: THIBAUT_EMAIL (defaults to tgueant@landquire.com)

Set DRY_RUN=1 to log what would happen without creating contacts or sending mail.
"""
import json, os, time, subprocess, urllib.request, urllib.error, sys, re
from collections import Counter
from email.header import decode_header

PVKEY = os.environ.get("PLUSVIBE_API_KEY", "")
PVBASE = "https://api.plusvibe.ai/api/v1"
PIT = os.environ.get("GHL_TOKEN", "")
LOC = os.environ.get("GHL_LOCATION_ID", "bu3JqdsMUIMYcVSRBSXs")
THIB = os.environ.get("THIBAUT_EMAIL", "tgueant@landquire.com")
DRY = os.environ.get("DRY_RUN", "") not in ("", "0", "false", "False")
GHLBASE = "https://services.leadconnectorhq.com"

# --- Current rules (per Paul's call, 13 Aug) ---------------------------------
# B2C positive reply -> DO NOTHING in GHL. Just log it as a note on the (already
#   existing) GHL contact so the assigned agent is notified, and it is recorded
#   for the agent + Thibaut. No contact creation, no auto-reply.
# B2B positive reply -> CREATE the contact in GHL in the NEW format only:
#   tag "plusvibe", source "cold emailing", Language custom field, first/last/
#   email/phone(if available). NO agent assignment, NO notification (Paul's GHL
#   automation picks it up via the "plusvibe" tag).
B2B_WID = "6a3179f64517eb5ecd7c1642"
LANG_FIELD = "Vr0luh4Dz7YIbM4BtawP"   # GHL "Language" (French/English/Spanish/Portuguese)
LANG_TEXT  = "adsXOWOrmfJXcMNvdwx0"   # GHL "Lead preferred language" (text)
LMAP = {"FR": "French", "EN": "English", "ES": "Spanish", "PT": "Portuguese"}

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

# Leading "{greet}" is filled with "<word> <FirstName>" when a real name is known,
# or just "<word>" (no name) otherwise -- never a mangled email prefix.
GREETWORD = {"FR": "Bonjour", "EN": "Hello", "ES": "Hola", "PT": "Ola"}
BODY = {
'FR': "{greet},<br><br>Je vous remercie pour votre reponse.<br><br>Pourriez-vous, s'il vous plait, me communiquer le numero de telephone sur lequel vous etes le plus facilement joignable, ainsi qu'un ou deux creneaux de disponibilite, en heure de France, pour un echange demain ?<br><br>Une fois le creneau convenu, je vous adresserai par e-mail une invitation afin que notre echange, par telephone ou en visioconference, puisse etre directement integre a nos agendas respectifs.<br><br>Bien cordialement,<br>Thibaut Gueant",
'EN': "{greet},<br><br>Thank you for your reply.<br><br>Could you please share the phone number where you are most easily reachable, along with one or two availability slots (France time) for a call tomorrow?<br><br>Once we agree on a slot, I will send you a calendar invitation so that our call, by phone or video, is added directly to both our agendas.<br><br>Best regards,<br>Thibaut Gueant",
'ES': "{greet},<br><br>Gracias por su respuesta.<br><br>Podria indicarme el numero de telefono en el que es mas facil localizarle, asi como uno o dos horarios de disponibilidad (hora de Francia) para hablar manana?<br><br>Una vez acordado el horario, le enviare una invitacion por correo para que nuestra llamada, por telefono o videoconferencia, quede integrada en ambas agendas.<br><br>Un cordial saludo,<br>Thibaut Gueant",
'PT': "{greet},<br><br>Obrigado pela sua resposta.<br><br>Poderia indicar-me o numero de telefone onde e mais facilmente contactavel, bem como um ou dois horarios de disponibilidade (hora de Franca) para uma conversa amanha?<br><br>Assim que combinarmos o horario, enviar-lhe-ei um convite por e-mail para que a nossa conversa, por telefone ou videochamada, fique integrada nas nossas agendas.<br><br>Com os melhores cumprimentos,<br>Thibaut Gueant"}

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


def _mime(s):
    try:
        return "".join((b.decode(enc or "utf-8", "ignore") if isinstance(b, bytes) else b)
                       for b, enc in decode_header(s))
    except Exception:
        return s or ""


def clean_first(display_name):
    """Real first name from a reply's display name. Returns '' when unusable
    (so the greeting falls back to a plain hello -- never an email prefix)."""
    if not display_name:
        return ""
    nm = _mime(display_name).strip()
    nm = nm.split(" - ")[0].split(" | ")[0].strip()      # drop "- Company" suffix
    nm = re.sub(r'["<>]', "", nm).strip()
    if "@" in nm:                                        # it's an email, not a name
        return ""
    toks = [t for t in re.split(r"[ ,]+", nm) if t]
    if not toks:
        return ""
    # "LASTNAME Firstname" -> take the non-uppercase token; else first token
    fn = toks[1] if (len(toks) >= 2 and toks[0].isupper() and not toks[1].isupper()) else toks[0]
    fn = fn.strip(".-_")
    if len(fn) < 2 or any(c.isdigit() for c in fn):
        return ""
    return fn[:1].upper() + fn[1:]


def last_name_of(display_name, first):
    """Best-effort last name from a reply display name."""
    if not display_name:
        return ""
    nm = _mime(display_name).split(" - ")[0].split(" | ")[0]
    nm = re.sub(r'["<>]', "", nm).strip()
    if "@" in nm:
        return ""
    toks = [t for t in re.split(r"[ ,]+", nm) if t and t.lower() != (first or "").lower()]
    if not toks:
        return ""
    caps = [t for t in toks if t.isupper() and len(t) > 1]
    ln = caps[0] if caps else toks[-1]
    return ln if ln.isupper() else ln[:1].upper() + ln[1:].lower()


def ghl_users():
    """Map GHL user id -> login email, so any agent (not just a hardcoded few)
    can be resolved when looping the assigned agent in on a B2C reply."""
    if DRY:
        return {}
    cmd = ["curl", "-s", GHLBASE + f"/users/?locationId={LOC}",
           "-H", "Authorization: Bearer " + PIT, "-H", "Version: 2021-07-28"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=40).stdout
        return {u.get("id"): u.get("email") for u in json.loads(out).get("users", []) if u.get("id")}
    except Exception:
        return {}


def ghl_lookup(email):
    """Return (contact_id, assignedTo) for an existing GHL contact, or (None, None)."""
    if DRY:
        return None, None
    cmd = ["curl", "-s", GHLBASE + f"/contacts/?locationId={LOC}&query={email}",
           "-H", "Authorization: Bearer " + PIT, "-H", "Version: 2021-07-28"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
        cs = json.loads(out.stdout).get("contacts", [])
        c = next((x for x in cs if (x.get("email") or "").lower() == email.lower()), None)
        if c:
            return c.get("id"), c.get("assignedTo")
    except Exception:
        pass
    return None, None


PHONE_RE = re.compile(r"(\+?\d[\d .()\-]{7,}\d)")


def extract_phone(text):
    """Phone from a reply signature -- only returns an already-international
    (+countrycode) number GHL will accept. A national-format number (leading 0,
    no country code) is left for the agent to add, rather than sending an invalid
    value that would make the whole contact create fail."""
    for m in PHONE_RE.finditer(text or ""):
        raw = m.group(1).strip()
        digits = re.sub(r"\D", "", raw)
        if raw.startswith("+") and 8 <= len(digits) <= 15 and digits[0] != "0":
            return "+" + digits
    return ""


TERMINAL_STATUS = {"REPLIED", "COMPLETED", "UNSUBSCRIBED", "BOUNCED", "SKIPPED"}


def stop_lead_automation(email):
    """Set the lead to COMPLETED on every campaign (BOTH workspaces) where it is
    still active, so no further automated sequence email goes out after handoff."""
    if DRY:
        return 0
    stopped = 0
    for wid in WS.values():
        try:
            d = pv_get(f"/lead/workspace-leads?workspace_id={wid}&email={email}")
        except Exception:
            continue
        recs = d if isinstance(d, list) else (d.get("data") or [])
        for r in recs:
            st = (r.get("status") or "").upper(); cid = r.get("campaign_id")
            if not cid or st in TERMINAL_STATUS:
                continue
            code, _ = pv_post("/lead/update/status",
                              {"workspace_id": wid, "campaign_id": cid, "email": email, "new_status": "COMPLETED"})
            if code in (200, 201):
                stopped += 1
            time.sleep(0.2)
    return stopped


def ghl_note(contact_id, body, user_id=None):
    """Log the prospect's reply as a note on their GHL contact so the assigned
    agent sees it (GHL notifies the owner). Used to forward ongoing replies."""
    if DRY or not contact_id:
        return False
    payload = {"body": body}
    if user_id:
        payload["userId"] = user_id
    cmd = ["curl", "-s", "-X", "POST", GHLBASE + f"/contacts/{contact_id}/notes",
           "-H", "Authorization: Bearer " + PIT, "-H", "Version: 2021-07-28",
           "-H", "Content-Type: application/json", "-d", json.dumps(payload)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    try:
        return bool((json.loads(out.stdout).get("note") or {}).get("id"))
    except Exception:
        return False


def forward_to_team(l, agent_email, to_agent=False):
    """Forward the prospect's positive reply to Thibaut + the assigned agent.
    Recipients are ONLY the addresses we set in to/cc (Thibaut, agent) -- the
    prospect is never a recipient, so this can never reach the prospect.
    to_agent=True addresses the agent directly (cc Thibaut); otherwise to Thibaut."""
    if DRY:
        return True
    if to_agent and agent_email and agent_email != THIB:
        to = agent_email
        cc = THIB
    else:
        to = THIB
        cc = agent_email if agent_email and agent_email != THIB else ""
    subj = l.get("subject") or "Reponse positive"
    if not subj.lower().startswith(("fwd", "tr", "fw")):
        subj = "Fwd: " + subj
    body = ("Reponse positive d'un prospect - a reprendre en main.<br>"
            f"Prospect : {l['email']}<br>Agent : {agent_email or '-'}<br><br>"
            "--- Message du prospect ---<br>" + (l.get("reply_text") or "")[:2000])
    code, _ = pv_post(f"/unibox/emails/reply?workspace_id={l['wid']}", {
        "reply_to_id": l["reply_to_id"], "from": l["eaccount"],
        "to": to, "cc": cc, "subject": subj, "body": body})
    return code in (200, 201)


def forward_pending_b2b(state, users):
    """B2B leads wait here until Paul's GHL automation assigns an owner; then the
    reply is forwarded to that EXACT owner (+ Thibaut), so the agent who gets the
    email is always the one tagged on the lead. Falls back to Thibaut after ~1h
    if still unassigned, so nothing is lost."""
    pending = state.get("b2b_pending", {})
    sent = 0
    for em in list(pending.keys()):
        rec = pending[em]
        rec["tries"] = rec.get("tries", 0) + 1
        _, owner = ghl_lookup(em)
        owner_email = users.get(owner) or ""
        if owner_email:
            if forward_to_team(rec, owner_email, to_agent=True):
                sent += 1
                pending.pop(em, None)
        elif rec["tries"] >= 4:
            forward_to_team(rec, "")
            pending.pop(em, None)
        time.sleep(0.2)
    return sent


def fetch_all_inbound():
    """All inbound INTERESTED messages across both workspaces (for reply forwarding)."""
    msgs = []
    for seg, wid in WS.items():
        trail = None
        while True:
            path = f"/unibox/emails?workspace_id={wid}&label=INTERESTED" + (f"&page_trail={trail}" if trail else "")
            d = pv_get(path)
            data = d.get("data", [])
            for it in data:
                if it.get("direction") != "IN":
                    continue
                em = (it.get("from_address_email") or "").strip().lower()
                if not em or "landquire" in em:
                    continue
                txt = it.get("content_preview") or strip_html((it.get("body") or {}).get("html", ""))
                msgs.append({"email": em, "id": it.get("id"), "wid": wid,
                             "text": txt, "subject": it.get("subject") or ""})
            trail = d.get("page_trail")
            if not trail or not data:
                break
            time.sleep(0.15)
    return msgs


def forward_new_replies(state, inbound):
    """For leads already handed to an agent, log any NEW inbound reply as a GHL
    note on their contact so the assigned agent picks it up. No emails sent."""
    handoff = state.get("handoff", {})
    fwd = 0
    for m in inbound:
        h = handoff.get(m["email"])
        if not h:
            continue
        seen = h.setdefault("seen", [])
        if m["id"] in seen or m["id"] == h.get("first_reply_id"):
            continue
        body = f"[Réponse prospect via PlusVibe] {m.get('subject','')}\n\n{(m.get('text') or '')[:1500]}"
        if ghl_note(h.get("contact_id"), body, h.get("agent_id")):
            fwd += 1
        seen.append(m["id"])
        time.sleep(0.2)
    return fwd


def load_state():
    try:
        s = json.load(open(STATE_PATH))
    except Exception:
        s = {}
    s.setdefault("processed", [])
    s.setdefault("rr", {"FR": 0, "PT": 0, "EN": 0, "ES": 0})
    s.setdefault("handoff", {})
    s.setdefault("b2b_pending", {})
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
                faj = it.get("from_address_json") or []
                display = faj[0].get("name") if faj else ""
                body_txt = it.get("content_preview") or strip_html((it.get("body") or {}).get("html", ""))
                out[em] = {
                    "email": em, "seg": seg, "wid": wid,
                    "lang": cl.get(it.get("campaign_id"), "FR"),
                    "reply_to_id": it.get("id"), "eaccount": it.get("eaccount"),
                    "subject": it.get("subject") or "",
                    "display_name": display, "reply_text": body_txt,
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
    users = ghl_users()          # id -> agent email, for looping the B2C owner in
    b2b_created = []; b2c_forwarded = []
    for l in new:
        lang = l["lang"] if l["lang"] in LMAP else "FR"
        fn = clean_first(l.get("display_name"))

        if l["wid"] == B2B_WID:
            # ---- B2B: create in GHL, new format, no agent, no notification ----
            ln = last_name_of(l.get("display_name"), fn)
            phone = extract_phone(l.get("reply_text"))
            body = {"locationId": LOC, "email": l["email"],
                    "source": "cold emailing", "tags": ["plusvibe"],
                    "customFields": [{"id": LANG_FIELD, "value": LMAP[lang]},
                                     {"id": LANG_TEXT, "value": LMAP[lang]}]}
            if fn: body["firstName"] = fn
            if ln: body["lastName"] = ln
            if phone: body["phone"] = phone
            r = ghl_upsert(body)
            c_id = (r.get("contact") or {}).get("id")
            if c_id or DRY:
                state["processed"].append(l["email"])
                # keep the reply content on the contact, then defer the forward until
                # Paul's GHL automation has assigned an owner -- so the forward ALWAYS
                # goes to exactly the agent tagged on the lead, never a different one.
                ghl_note(c_id, f"[Reponse positive - cold outreach]\nProspect: {l['email']}\n\n"
                               f"{(l.get('reply_text') or '')[:1500]}")
                state["b2b_pending"][l["email"]] = {
                    "reply_to_id": l["reply_to_id"], "eaccount": l["eaccount"], "wid": l["wid"],
                    "subject": l.get("subject", ""), "email": l["email"],
                    "reply_text": (l.get("reply_text") or "")[:2000], "tries": 0}
                b2b_created.append((l["email"], lang, bool(phone)))
            else:
                print("  B2B GHL FAIL", l["email"], str(r)[:120], file=sys.stderr)
        else:
            # ---- B2C: do NOTHING in GHL. Forward the reply to Thibaut + agent. ----
            contact_id, owner = ghl_lookup(l["email"])
            agent_email = users.get(owner) or ""
            note = (f"[Réponse positive B2C — à reprendre en main]\n"
                    f"Prospect: {l['email']}\nAgent assigné: {agent_email or 'non assigné'}\n\n"
                    f"{(l.get('reply_text') or '')[:1500]}")
            ghl_note(contact_id, note)               # note on the existing contact
            forward_to_team(l, agent_email)          # email to Thibaut + assigned agent
            state["processed"].append(l["email"])
            state["handoff"][l["email"]] = {"seg": "B2C", "agent_email": agent_email,
                                            "contact_id": contact_id,
                                            "first_reply_id": l["reply_to_id"], "seen": [],
                                            "eaccount": l["eaccount"], "wid": l["wid"],
                                            "subject": l.get("subject", "")}
            b2c_forwarded.append((l["email"], lang, agent_email or "unassigned"))
        time.sleep(0.2)

    # B2B: forward the reply to each lead's GHL owner once assigned (== tagged agent).
    pending_forwarded = forward_pending_b2b(state, users)

    if not DRY:
        save_state(state)
    print("B2B forwarded to their GHL-assigned owner this run:", pending_forwarded,
          "| still awaiting assignment:", len(state.get("b2b_pending", {})))
    print("B2B created in GHL (plusvibe / cold emailing / language, no agent):", len(b2b_created))
    print("B2C forwarded to agent + Thibaut (no GHL create):", len(b2c_forwarded))
    print("B2B by lang:", dict(Counter(x[1] for x in b2b_created)))


if __name__ == "__main__":
    main()
