# -*- coding: utf-8 -*-
"""Lecture d'une reponse entrante : intention, puis creneau choisi.

Deliberement deterministe. Le reglage retenu est "n'automatiser que les cas
francs" : tout ce qui n'est pas reconnu avec certitude remonte a l'humain et
le robot se tait. Un classifieur LLM pourra elargir la couverture plus tard
en remplacant `intent()` -- la frontiere est faite pour ca.
"""
import re
from datetime import datetime, timedelta

# Fins de message : tout ce qui suit est notre propre texte cite, pas le sien.
# Classer sans couper revient a lire notre argumentaire comme sa reponse -- et
# a prendre un "STOP" pour un oui.
QUOTE = [r"^\s*>", r"\bon\s.{3,120}?\swrote\s*:", r"-{2,}\s*original message",
         r"\bfrom\s*:\s*.{0,120}?\bsent\s*:", r"\bde\s*:\s*.{0,120}?\benvoy",
         r"\ble\s.{3,120}?\sa\s(?:e|\u00e9)crit\s*:", r"_{6,}",
         r"\bsent from my (?:iphone|ipad|android|mobile|blackberry)\b",
         r"\bget outlook for\b", r"\bcaution\s*:\s*external email",
         r"\bconfidentialit(?:y|e)\s+notice\b",
         r"\bthis (?:e-?mail|message) (?:and any attachments )?is confidential"]


def strip_quote(text):
    """Ne garde que ce que le prospect a reellement ecrit."""
    t = (text or "").replace("\r\n", "\n")
    cut = len(t)
    for pat in QUOTE:
        m = re.search(pat, t, re.I | re.M)
        if m:
            cut = min(cut, m.start())
    return t[:cut].strip()


# --- signaux, du plus contraignant au plus permissif -----------------------
OPTOUT = [r"\bunsubscribe\b", r"^\s*stop\s*$", r"^\s*stop\b",
          r"\bdesinscri", r"\bno more emails?\b", r"^\s*remove\b", r"\bopt[- ]?out\b", r"remove me\b", r"take me off\b",
          r"\bdo not (?:contact|email)\b", r"\bstop (?:emailing|contacting)\b",
          r"\bdesabonn", r"\bne plus (?:me )?(?:contacter|ecrire)"]

OOO = [r"out of (?:the )?office", r"\bon (?:annual |parental )?leave\b", r"\bon vacation\b",
       r"\bautomatic repl", r"\bauto[- ]?repl", r"\bmaternity\b", r"\bpaternity\b",
       r"\bje serai absent", r"\babsence du bureau", r"currently away",
       r"back (?:in|on) the office", r"limited access to (?:my )?email"]

NEGATIVE = [r"\bnot interested\b", r"\bno thanks?\b", r"\bnot (?:a )?(?:good )?fit\b",
            r"\bwe(?:'re| are) (?:all )?(?:good|set)\b", r"\bpass\b", r"\bno need\b",
            r"\balready (?:have|work with|using)\b", r"\bnot (?:at )?(?:this|the) time\b",
            r"\bnot right now\b", r"\bno interest\b", r"\bpas interesse"]

POSITIVE = [r"\b(?:i(?:'m| am)? )?interested\b", r"send (?:me )?(?:more )?info",
            r"\btell me more\b", r"\bsounds good\b", r"\bsounds interesting\b",
            r"\blet(?:'s| us) (?:talk|chat|connect|meet)\b", r"\bhappy to (?:chat|talk|meet)\b",
            r"\b(?:would|i'd) love to (?:chat|talk|meet|see)\b", r"\bset(?:ting)? up a (?:call|time)\b",
            r"\bworth a (?:call|chat|conversation)\b", r"\byes\b.{0,20}\b(?:call|chat|meet|info)\b",
            r"\bsend (?:it|the list|them) over\b", r"\bgo ahead\b", r"\bok+\b.{0,10}\bsend\b"]

# quelqu'un qui pose une vraie question ou qui n'est pas le bon interlocuteur
HUMAN = [r"\bhow much\b", r"\bwhat(?:'s| is) (?:the )?(?:price|cost|pricing)\b", r"\bhow many\b",
         r"\bwho (?:are|is) (?:you|this)\b", r"\bwhere did you get\b", r"\bgdpr\b", r"\bccpa\b",
         r"\blegal\b", r"\blawyer\b", r"\battorney\b", r"\bspam\b", r"\bfuck\b", r"\bscam\b",
         r"\bwrong person\b", r"\bno longer (?:with|at)\b", r"\bleft the company\b",
         r"\breach out to\b", r"\bspeak (?:to|with) my\b", r"\bnot my (?:area|department)\b"]

DAYS = {"monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5, "sunday": 6, "sun": 6}

# Volontairement sans "one"/"two"/"three" : "the 4:30 one" n'est pas un rang.
ORDINAL = {"first": 0, "1st": 0, "earliest": 0,
           "second": 1, "2nd": 1,
           "third": 2, "3rd": 2}

# un refus explicite d'interet : emporte tout signal positif du meme message
HARD_NO = [r"\bnot interested\b", r"\bno interest\b", r"\bzero interest\b",
           r"\bnot interested at all\b", r"\bpas interesse",
           r"\b0(?:\.0+)?\s*%\s*chance\b", r"\bno chance\b",
           r"\bwe (?:don'?t|do not) (?:sell|do|need|buy)\b",
           r"\bwrong\b.{0,40}\b(?:we|i)\b", r"^\s*wrong[!.]?",
           r"\bi know my (?:customers|market)\b",
           r"\bnot (?:our|my) (?:market|business|industry)\b"]


def _norm(t):
    t = re.sub(r"\s+", " ", (t or "")).strip().lower()
    return t


def any_hit(t, pats):
    return any(re.search(p, t, re.I) for p in pats)


def intent(text, has_auto_header=False):
    """Retourne une intention, ou 'unclear' si rien n'est franc.

    L'ordre compte : un desabonnement ou une absence l'emporte sur tout signal
    positif present dans le meme message (signature, citation...).
    """
    t = _norm(strip_quote(text))
    if not t:
        return "unclear"
    if any_hit(t, OPTOUT):
        return "optout"
    if has_auto_header or any_hit(t, OOO):
        return "out_of_office"
    if any_hit(t, HUMAN):
        return "human"                      # jamais de reponse automatique
    if any_hit(t, HARD_NO):
        return "negative"
    neg, pos = any_hit(t, NEGATIVE), any_hit(t, POSITIVE)
    if neg and not pos:
        return "negative"
    if neg and pos:
        return "unclear"                    # contradictoire -> humain
    if pos:
        return "positive"
    return "unclear"


def pick_slot(text, slots, now=None):
    """Retrouve lequel des creneaux proposes le prospect accepte.

    `slots` : liste de datetime aware, dans l'ordre ou ils ont ete proposes.
    Retourne (datetime, raison) ou (None, raison) si ce n'est pas certain.
    Ambigu = None : on prefere escalader que booker le mauvais creneau.
    """
    t = _norm(strip_quote(text))
    if not slots:
        return None, "aucun creneau en memoire"

    if re.search(r"\b(?:none|neither|don't work|doesn'?t work|no good|another|other) ", t) \
       and not re.search(r"\bworks?\b", t):
        return None, "refuse les creneaux proposes"

    hits = set()

    # 1. par jour de la semaine
    for word, dow in DAYS.items():
        if re.search(rf"\b{word}\b", t):
            for i, s in enumerate(slots):
                if s.weekday() == dow:
                    hits.add(i)

    # 2. par heure ("10am", "14h", "2 pm", "10:30")
    for m in re.finditer(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|h)?\b", t):
        h = int(m.group(1)); mi = int(m.group(2) or 0); suf = m.group(3)
        if h > 24:
            continue
        cands = {h}
        if suf == "pm" and h < 12:
            cands = {h + 12}
        elif suf == "am":
            cands = {h}
        elif suf is None and h <= 12:
            cands = {h, h + 12}          # "2 works" -> 2h ou 14h
        for i, s in enumerate(slots):
            if s.hour in cands and (mi == 0 or s.minute == mi):
                hits.add(i)

    # 3. par rang ("the first one", "option 2")
    for word, idx in ORDINAL.items():
        if re.search(rf"\b{word}\b", t) and idx < len(slots):
            hits.add(idx)
    if re.search(r"\b(?:last|latest)\b", t):
        hits.add(len(slots) - 1)
    m = re.search(r"\boption\s*(\d)\b", t)
    if m and 1 <= int(m.group(1)) <= len(slots):
        hits.add(int(m.group(1)) - 1)

    if len(hits) == 1:
        i = hits.pop()
        return slots[i], f"creneau {i + 1} reconnu"
    if not hits:
        # "any of those works", "all good" -> on prend le premier propose
        if re.search(r"\b(?:any|all|either|whichever|any of (?:those|these|them))\b", t) \
           and re.search(r"\b(?:works?|fine|good|ok)\b", t):
            return slots[0], "accepte n'importe quel creneau -> le premier"
        return None, "aucun creneau identifie"
    return None, f"{len(hits)} creneaux possibles -- ambigu"
