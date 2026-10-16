# -*- coding: utf-8 -*-
"""Transcript -> compte rendu markdown.

Deux modes, et le premier ne coute RIEN :

  deterministe (defaut)  regroupage des segments, temps de parole par
                         personne, engagements / decisions / questions
                         reperes par formules declencheuses (FR + EN).
                         Zero appel reseau, zero centime.

  --ai                   en plus, un resume redige par Claude (API Anthropic,
                         facturee au token). Utile quand la reunion est longue
                         et qu'on veut un paragraphe presentable.

Variables d'environnement pour --ai :
  ANTHROPIC_API_KEY  (obligatoire pour --ai)
  MEETING_MODEL      defaut claude-opus-5-5
"""
import os
import re
from collections import OrderedDict

# --- formules declencheuses -------------------------------------------------
# Volontairement bilingues : les reunions passent du francais a l'anglais.

ACTION_CUES = [
    # anglais
    r"\bI'?ll\b", r"\bI will\b", r"\bwe'?ll\b", r"\bwe will\b", r"\bwe need to\b",
    r"\blet'?s\b", r"\bcan you\b", r"\bcould you\b", r"\bwill you\b",
    r"\bnext step\b", r"\bfollow up\b", r"\baction item\b", r"\bto[- ]?do\b",
    r"\bsend (?:me|you|over|the)\b", r"\bget back to\b", r"\bI'?m going to\b",
    r"\bby (?:monday|tuesday|wednesday|thursday|friday|tomorrow|next week|end of)\b",
    # francais
    r"\bje vais\b", r"\bon va\b", r"\bje m'en occupe\b", r"\bil faut\b",
    r"\bje te (?:envoie|renvoie|fais)\b", r"\bje t'envoie\b", r"\bje vous envoie\b",
    r"\bon fait\b", r"\bprochaine etape\b", r"\bje reviens vers\b",
    r"\btu peux\b", r"\bvous pouvez\b", r"\bje confirme\b", r"\bon se recale\b",
    r"\bd'ici (?:lundi|mardi|mercredi|jeudi|vendredi|demain|la semaine)\b",
]

DECISION_CUES = [
    r"\bwe (?:decided|agreed|settled on)\b", r"\blet'?s go with\b", r"\bwe'?re going with\b",
    r"\bagreed\b", r"\bdeal\b", r"\bthat works\b", r"\bsounds good\b", r"\bapproved\b",
    r"\bon part sur\b", r"\bon valide\b", r"\bon est d'accord\b", r"\bc'est valide\b",
    r"\bon acte\b", r"\bje valide\b", r"\bca marche\b", r"\bc'est bon pour moi\b",
]

OBJECTION_CUES = [
    r"\btoo expensive\b", r"\bbudget\b", r"\bnot sure\b", r"\bconcern\b", r"\bworried\b",
    r"\bproblem is\b", r"\bblocker\b", r"\bpush back\b", r"\bhesitat",
    r"\btrop cher\b", r"\bje ne suis pas sur\b", r"\bprobleme\b", r"\binquiet",
    r"\bbloquant\b", r"\bon verra\b", r"\bpas convaincu\b", r"\breticen",
]

# dates et echeances citees a l'oral
DATE_CUES = re.compile(
    r"\b("
    r"lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|demain|apres-demain|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|"
    r"la semaine prochaine|next week|this week|cette semaine|"
    r"end of (?:week|month|quarter)|fin (?:de semaine|du mois|de mois|du trimestre)|"
    r"q[1-4]|t[1-4]|"
    r"janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
    r")\b",
    re.I,
)

_ACTION_RE = re.compile("|".join(ACTION_CUES), re.I)
_DECISION_RE = re.compile("|".join(DECISION_CUES), re.I)
_OBJECTION_RE = re.compile("|".join(OBJECTION_CUES), re.I)


def clean_segments(segments):
    """Garde les segments confirmes, jette les brouillons et les doublons.

    Les segments live arrivent avec completed=false puis sont remplaces par la
    version confirmee. Si AUCUN segment n'est confirme (reunion encore en
    cours), on garde tout plutot que de rendre une page blanche.
    """
    if not segments:
        return []
    rows = [s for s in segments if isinstance(s, dict)]
    confirmed = [s for s in rows if s.get("completed") is True]
    keep = confirmed if confirmed else rows

    keep = sorted(keep, key=lambda s: (_num(s.get("start")), _num(s.get("end"))))

    out = []
    for seg in keep:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        spk = (seg.get("speaker") or "?").strip() or "?"
        # meme locuteur, texte identique colle au precedent -> doublon
        if out and out[-1]["speaker"] == spk and out[-1]["text"] == text:
            continue
        out.append({
            "speaker": spk,
            "text": text,
            "start": _num(seg.get("start")),
            "end": _num(seg.get("end")),
            "language": seg.get("language"),
        })
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def mmss(seconds):
    seconds = int(max(0, seconds))
    return "%02d:%02d" % (seconds // 60, seconds % 60)


def merge_turns(segments):
    """Colle les segments consecutifs d'un meme locuteur en tours de parole."""
    turns = []
    for seg in segments:
        if turns and turns[-1]["speaker"] == seg["speaker"]:
            turns[-1]["text"] += " " + seg["text"]
            turns[-1]["end"] = seg["end"]
        else:
            turns.append(dict(seg))
    return turns


def talk_time(segments):
    """Secondes de parole par locuteur, du plus bavard au moins bavard."""
    per = OrderedDict()
    for seg in segments:
        dur = max(0.0, seg["end"] - seg["start"])
        per[seg["speaker"]] = per.get(seg["speaker"], 0.0) + dur
    total = sum(per.values()) or 1.0
    rows = sorted(per.items(), key=lambda kv: kv[1], reverse=True)
    return [(spk, secs, 100.0 * secs / total) for spk, secs in rows], total


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\s*\n+\s*", text)
    return [p.strip() for p in parts if p and p.strip()]


def _hits(regex, segments):
    """Phrases (avec locuteur et horodatage) qui declenchent le motif."""
    found = []
    seen = set()
    for seg in segments:
        for sentence in split_sentences(seg["text"]):
            if len(sentence) < 8:
                continue
            if not regex.search(sentence):
                continue
            key = (seg["speaker"], sentence.lower())
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "speaker": seg["speaker"],
                "text": sentence,
                "at": seg["start"],
                "dates": sorted(set(m.group(0) for m in DATE_CUES.finditer(sentence))),
            })
    return found


def extract(segments):
    """Tout ce qu'on sait tirer du transcript sans modele."""
    return {
        "actions": _hits(_ACTION_RE, segments),
        "decisions": _hits(_DECISION_RE, segments),
        "objections": _hits(_OBJECTION_RE, segments),
    }


def transcript_text(segments, with_timestamps=True):
    lines = []
    for turn in merge_turns(segments):
        if with_timestamps:
            lines.append("[%s] **%s** : %s" % (mmss(turn["start"]), turn["speaker"], turn["text"]))
        else:
            lines.append("%s: %s" % (turn["speaker"], turn["text"]))
    return "\n\n".join(lines)


# --- resume par Claude (optionnel, paye au token) ---------------------------

SYSTEM_PROMPT = (
    "Tu es l'assistant de compte rendu d'un ingenieur go-to-market. On te donne "
    "le transcript horodate et attribue d'une reunion commerciale. Rends un "
    "markdown court et exploitable, dans la langue dominante de la reunion, "
    "avec exactement ces sections :\n"
    "## Resume (3 a 5 puces, ce qui s'est reellement dit)\n"
    "## Decisions (ce qui est acte ; si rien, ecris \"rien d'acte\")\n"
    "## Engagements (une ligne par engagement : qui -- quoi -- pour quand ; "
    "n'invente jamais de nom ni d'echeance absente du transcript)\n"
    "## Objections et risques\n"
    "## Prochaine etape (une seule phrase)\n"
    "Pas de preambule, pas de conclusion, pas de flatterie. Si le transcript "
    "est trop court ou inaudible, dis-le franchement au lieu de broder."
)


def ai_summary(segments, model=None):
    """Resume redige par Claude. Leve une exception explicite si indisponible.

    Le coeur du kit n'a aucune dependance : le SDK officiel n'est importe que
    si on demande vraiment --ai.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY absente : le resume Claude est l'option payante. "
            "Sans elle, le compte rendu deterministe fonctionne deja."
        )
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "SDK Anthropic absent : `pip install anthropic` (seulement necessaire pour --ai)"
        )

    body = transcript_text(segments)
    if len(body.split()) < 25:
        raise RuntimeError("transcript trop court pour un resume (moins de 25 mots)")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model or os.environ.get("MEETING_MODEL") or "claude-opus-5-5",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        # effort medium : un compte rendu n'a pas besoin du mode le plus cher
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": "Transcript :\n\n" + body}],
    )
    if response.stop_reason == "refusal":
        detail = getattr(response.stop_details, "explanation", "") or ""
        raise RuntimeError("Claude a refuse de resumer ce transcript. %s" % detail)
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


# --- rendu markdown ---------------------------------------------------------

def render(meta, segments, summary=None):
    """meta : dict libre (titre, plateforme, id, date, statut, lien)."""
    seg = clean_segments(segments)
    facts = extract(seg)
    times, total = talk_time(seg)

    L = []
    title = meta.get("title") or "Reunion %s" % (meta.get("native_meeting_id") or "")
    L.append("# %s" % title)
    L.append("")

    info = []
    if meta.get("platform"):
        info.append("**Plateforme** : %s" % meta["platform"])
    if meta.get("native_meeting_id"):
        info.append("**Id** : `%s`" % meta["native_meeting_id"])
    if meta.get("start_time"):
        info.append("**Debut** : %s" % meta["start_time"])
    if meta.get("status"):
        info.append("**Statut** : %s" % meta["status"])
    info.append("**Duree de parole captee** : %s" % mmss(total))
    L.append(" · ".join(info))
    L.append("")

    if not seg:
        L.append("> Aucun segment transcrit. Le bot a rejoint mais rien n'a ete")
        L.append("> transcrit : verifie la STT (`./meetings/meet.py doctor`).")
        L.append("")
        return "\n".join(L)

    if summary:
        L.append(summary.strip())
        L.append("")
    else:
        L.append("## Engagements reperes")
        L.append("")
        if facts["actions"]:
            for a in facts["actions"]:
                when = (" — *%s*" % ", ".join(a["dates"])) if a["dates"] else ""
                L.append("- [ ] **%s** (%s) : %s%s" % (a["speaker"], mmss(a["at"]), a["text"], when))
        else:
            L.append("- rien qui ressemble a un engagement")
        L.append("")

        L.append("## Decisions")
        L.append("")
        if facts["decisions"]:
            for d in facts["decisions"]:
                L.append("- **%s** (%s) : %s" % (d["speaker"], mmss(d["at"]), d["text"]))
        else:
            L.append("- rien d'acte")
        L.append("")

        L.append("## Objections et risques")
        L.append("")
        if facts["objections"]:
            for o in facts["objections"]:
                L.append("- **%s** (%s) : %s" % (o["speaker"], mmss(o["at"]), o["text"]))
        else:
            L.append("- aucune objection reperee")
        L.append("")

    L.append("## Temps de parole")
    L.append("")
    L.append("| Personne | Temps | Part |")
    L.append("|---|---|---|")
    for spk, secs, pct in times:
        L.append("| %s | %s | %.0f%% |" % (spk, mmss(secs), pct))
    L.append("")

    L.append("## Transcript")
    L.append("")
    L.append(transcript_text(seg))
    L.append("")
    return "\n".join(L)
