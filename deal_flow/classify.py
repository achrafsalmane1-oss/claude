# -*- coding: utf-8 -*-
import json, re, csv, sys
from collections import defaultdict

BUYSIDE_CAMPAIGNS = {1574:"Buyside!! (off-market deal flow for acquirers)",
                     867:"PE Firms Campaign",
                     1340:"Origin Buyer Outreach (sector-specific sellers)",
                     960:"Rhinogram Strategic Buyers (Healthcare IT/SaaS)",
                     1291:"Origin - Business Brokers"}

# --- firm-type signals -------------------------------------------------------
PE_KW   = r"(capital|equity|partners|holdings?|ventures?|invest|fund|acquisitions?|acquire|group\s*holdings|holdco|family\s*office|private\s*equity|buyout|mezzanine|growth\s*partners)"
VC_KW   = r"(ventures?|vc\b|seed|early\s*stage|growth\s*equity)"
MA_KW   = r"(m&a|mergers|acquisitions|advisory|advisors|business\s*brok|broker|intermediar|investment\s*bank|sell[- ]side|buy[- ]side|transaction\s*advisory)"
TITLE_KW= r"(partner|principal|managing\s*director|md\b|associate|analyst|vice\s*president|vp\b|investor|investment|acquisition|corp\s*dev|corporate\s*development|deal|founder|ceo|president|owner|director)"

NEG_KW  = r"(roofing|plumbing|hvac|landscap|electric|paving|fenc|paint|pool|clean|pest|window|remodel|contractor|restaurant|dental|salon|auto|towing|nursery|lawn|tree\s*service)"

POSITIVE = [
 r"\b(yes|yeah|yep|sure|absolutely|definitely|happy to|glad to|would love|i'?d love|interested|very interested|keen)\b",
 r"\b(send (it|them|those|over|me)|share (more|the|a)|shoot (me|it)|pass (them|it) along|forward)\b",
 r"\b(let'?s (chat|connect|talk|set)|open to (a )?(chat|call|conversation|connect)|book|calendar|calendly|schedule|available|call)\b",
 r"\b(what (are|do) you|tell me more|more (info|information|details)|one[- ]pager|deck|cim|teaser)\b",
 r"\b(buy box|our (buy|mandate|focus|criteria|thesis)|we (are |'re )?(actively )?(buying|acquiring|looking))\b",
]
NEGATIVE = [
 r"\b(not interested|no thanks|no thank you|unsubscribe|remove me|take me off|opt out|stop (emailing|contacting))\b",
 r"\b(we (are |'re )?not (looking|buying|acquiring|interested)|not (a )?(fit|right time)|pass\b|no longer)\b",
 r"\b(out of office|automatic reply|auto[- ]reply|on (vacation|leave|pto)|maternity|away from|will be back|currently out)\b",
 r"\b(undeliverable|delivery (has )?failed|mailbox (is )?full|address not found|no longer with|has left the company|delivery status)\b",
]

def sig(text, pats): return sum(1 for p in pats if re.search(p, text, re.I))

def firm_type(company, email, title, text):
    dom = (email or "").split("@")[-1].lower()
    blob = f"{company or ''} {dom}".lower()
    t = (title or "").lower()
    scores = {}
    if re.search(MA_KW, blob) or re.search(MA_KW, t): scores["M&A / Broker / Advisory"] = 3
    if re.search(r"(venture|vc\b|seed capital)", blob): scores["VC"] = 3
    if re.search(PE_KW, blob): scores["PE / Investment firm"] = scores.get("PE / Investment firm",0)+3
    if re.search(r"(corp(orate)?\s*dev|m&a)", t): scores["Strategic / Corp Dev"] = scores.get("Strategic / Corp Dev",0)+2
    if re.search(r"\b(search fund|holdco|family office|etaship|acquisition entrepreneur)\b", blob+" "+text.lower()):
        scores["Search fund / Family office / HoldCo"] = scores.get("Search fund / Family office / HoldCo",0)+3
    if not scores: return None, 0
    best = max(scores, key=scores.get)
    return best, scores[best]
