# -*- coding: utf-8 -*-
"""Turn a raw Otto reply body into (a) the text the prospect actually typed and
(b) their stated acquisition mandate.

Otto's `text_body` carries the WHOLE thread — the prospect's line plus every
quoted round of Perry Street's own outbound copy. Parsing that directly makes
PSP's pitch ("...owners who are open to a sale conversation and hand them to
you") come back as the prospect's buy box, so the quoted history has to go
first.
"""
import re

SENIORITY = {"senior", "entry", "manager", "owner", "founder", "partner", "mid-level",
             "director", "c-level", "executive", "vp", "associate", "principal",
             "staff", "junior"}


def valid_sector(v):
    """`sector_list` is only a mandate when it names a SECTOR. In campaign 1291 it
    holds seniority bands ("senior", "entry"), which say nothing about a buy box."""
    if not v:
        return None
    s = v.strip()
    if s.lower() in SENIORITY or len(s) < 4:
        return None
    return s


# Everything from here on is quoted history, a forward, a signature or legal boilerplate.
_CUTS = [
    r"\bOn (Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,? .{5,200}?\bwrote:",
    r"\bOn \w{3,9} \d{1,2},? \d{4}.{0,200}?\bwrote:",
    r"\bOn .{5,200}?<[^@]+@[^>]+>\s*wrote:",
    r"-{2,}\s*Original Message\s*-{2,}",
    r"-{2,}\s*Forwarded message\s*-{2,}",
    r"\bFrom:\s*\S+.{0,200}?\bSent:",
    r"\n\s*_{5,}",
    r"\bCONFIDENTIALITY NOTICE",
    r"\bThis (e-?mail|message) (and any|is intended|contains)",
    r"\n\s*Sent from my ",
    r"\n\s*Get Outlook for",
    r"\n\s*Unsubscribe\b",
]


def strip_quoted(text):
    """Return only what the sender typed in this message."""
    if not text:
        return ""
    t = text.replace("\r\n", "\n")
    t = "\n".join(ln for ln in t.split("\n") if not ln.lstrip().startswith((">", "|>")))
    for p in _CUTS:
        m = re.search(p, t, re.I)
        if m:
            t = t[:m.start()]
    return " ".join(t.split()).strip()


MANDATE_PATTERNS = [
    r"(?:we(?:'re| are)?\s+(?:currently\s+|actively\s+)?(?:looking (?:for|at|to acquire)|buying|acquiring|focused on|interested in|targeting|seeking|in the market for)\s+)([^.!?\n]{10,200})",
    r"(?:our\s+(?:buy[\s-]?box|focus|mandate|criteria|thesis|sweet spot|target|niche)\s*(?:is|are|:|includes)?\s*)([^.!?\n]{8,200})",
    r"(?:we\s+(?:invest|acquire|buy|specialize)\s+(?:in\s+)?)([^.!?\n]{8,200})",
    r"((?:\$\s?\d[\d.,]*\s*(?:k|m|mm|million|b|bn)?\s*(?:-|to|–|—)\s*\$?\s?\d[\d.,]*\s*(?:k|m|mm|million|b|bn)?)[^.!?\n]{0,140})",
    r"((?:ebitda|revenue|arr|sde|topline)[^.!?\n]{4,150})",
    r"(?:interested in\s+)([^.!?\n]{8,200})",
]

# Perry Street's OWN outbound copy. A "mandate" matching one of these is PSP's
# pitch quoted back, not the prospect's buy box.
OWN_COPY = [
    r"open to a sale", r"hand them to you", r"seller[- ]lead engine", r"source mandates",
    r"learning more", r"buy ?box who are", r"qualified off[- ]market deal flow",
    r"a list of the companies and owners", r"business owners looking at an exit",
    r"good fit for your firm", r"acquirers with qualified",
    r"experienced team who can act", r"perry ?st", r"deyonker", r"\bhttps?://",
    r"blinq\.me", r"view my contact", r"signed 7", r"800 leads", r"11 LOIs",
    r"you don'?t pay",
]

# Signature / footer fragments the loose patterns pick up.
NOISE = [
    r"\[image", r"www\.", r"\bsuite\b", r"^\W",
    r"warrant|representation|express or implied",
    r"\bstreet\b|\bave\b|\bblvd\b|\bcenter dr\b",
    r"^\s*(arr|arry|arrow|arrant|earing|hearing|nterest|ounds)\b",
]


def _matches(s, pats):
    return any(re.search(p, s, re.I) for p in pats)


# Campaign-level fallback: what the offer they replied to was actually about.
_CAMPAIGN_MANDATE = {
    960:  "Healthcare IT / patient-communication SaaS (~$2.7M ARR live mandate)",
    1340: "Sector-specific owner-operated businesses exploring exit",
    1291: "Seller/mandate flow for their own brokerage buy box",
    1574: "Off-market acquisition deal flow - buy box not stated",
    867:  "Off-market acquisition deal flow - buy box not stated",
    1578: "Vertical SaaS",
}


def extract_mandate(prospect_text, sector_list, campaign_ids, firm_type=None):
    """Return (mandate, source). `source` records how much to trust it."""
    t = " ".join((prospect_text or "").split())
    hits, seen = [], set()
    for p in MANDATE_PATTERNS:
        for m in re.finditer(p, t, re.I):
            g = (m.group(1) if m.lastindex else m.group(0)).strip(" -–,;:\"'")
            if not (8 <= len(g) <= 220):
                continue
            if _matches(g, OWN_COPY) or _matches(g, NOISE) or len(g.split()) < 3:
                continue
            k = g.lower()[:50]
            if k in seen:
                continue
            seen.add(k)
            hits.append(g)
    if hits:
        return " | ".join(hits[:2]), "stated in reply"

    sec = valid_sector(sector_list)
    if sec:
        return sec, "campaign targeting (sector variable)"

    for cid in (campaign_ids or []):
        if cid in _CAMPAIGN_MANDATE:
            return _CAMPAIGN_MANDATE[cid], "campaign targeting"
    return "Not stated", "unknown"
