"""Build a HeyReach-ready CSV: linkedin_url, first_name, company_name, niche.

LinkedIn URLs come from the prospects' own reply signatures (exact, no guessing),
verified against the lead's name. Non-US leads rank first.
"""
import json, re, csv, sys, unicodedata, glob

SLUG = re.compile(r"(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|pub)/([A-Za-z0-9\-_%À-ÿ\.]{3,})", re.I)
PHONE_CC = re.compile(r"\+(\d{1,3})[\s\-.()\d]{6,}")

US_TLDS = {"com", "net", "org", "io", "ai", "co", "us", "app", "dev", "tech", "info", "biz", "xyz"}
CC_TLD = {
 "uk":"United Kingdom","de":"Germany","fr":"France","es":"Spain","it":"Italy","nl":"Netherlands",
 "be":"Belgium","ch":"Switzerland","at":"Austria","se":"Sweden","no":"Norway","dk":"Denmark",
 "fi":"Finland","pl":"Poland","pt":"Portugal","ie":"Ireland","cz":"Czechia","gr":"Greece",
 "ro":"Romania","hu":"Hungary","bg":"Bulgaria","hr":"Croatia","si":"Slovenia","sk":"Slovakia",
 "ee":"Estonia","lv":"Latvia","lt":"Lithuania","lu":"Luxembourg","is":"Iceland","mt":"Malta",
 "ca":"Canada","au":"Australia","nz":"New Zealand","za":"South Africa","ng":"Nigeria",
 "ke":"Kenya","eg":"Egypt","ma":"Morocco","ae":"UAE","sa":"Saudi Arabia","il":"Israel",
 "tr":"Turkey","in":"India","sg":"Singapore","hk":"Hong Kong","jp":"Japan","kr":"South Korea",
 "cn":"China","tw":"Taiwan","my":"Malaysia","id":"Indonesia","ph":"Philippines","th":"Thailand",
 "vn":"Vietnam","br":"Brazil","mx":"Mexico","ar":"Argentina","cl":"Chile","co.":"Colombia",
 "pe":"Peru","uy":"Uruguay","ec":"Ecuador","eu":"Europe","cy":"Cyprus","ua":"Ukraine",
 "rs":"Serbia","ge":"Georgia","kz":"Kazakhstan","pk":"Pakistan","bd":"Bangladesh","lk":"Sri Lanka",
}
PHONE_CC_MAP = {
 "44":"United Kingdom","33":"France","49":"Germany","34":"Spain","39":"Italy","31":"Netherlands",
 "32":"Belgium","41":"Switzerland","43":"Austria","46":"Sweden","47":"Norway","45":"Denmark",
 "358":"Finland","48":"Poland","351":"Portugal","353":"Ireland","420":"Czechia","30":"Greece",
 "40":"Romania","36":"Hungary","972":"Israel","971":"UAE","966":"Saudi Arabia","90":"Turkey",
 "91":"India","65":"Singapore","852":"Hong Kong","81":"Japan","82":"South Korea","86":"China",
 "60":"Malaysia","62":"Indonesia","63":"Philippines","66":"Thailand","84":"Vietnam",
 "55":"Brazil","52":"Mexico","54":"Argentina","56":"Chile","57":"Colombia","51":"Peru",
 "27":"South Africa","234":"Nigeria","254":"Kenya","20":"Egypt","212":"Morocco",
 "61":"Australia","64":"New Zealand","380":"Ukraine","995":"Georgia","92":"Pakistan",
}

SUFFIX = re.compile(
    r"[,\s]+(inc|inc\.|llc|l\.l\.c\.|ltd|ltd\.|limited|corp|corp\.|corporation|co|co\.|"
    r"gmbh|ag|bv|b\.v\.|nv|n\.v\.|sa|s\.a\.|sas|sarl|s\.r\.l\.|srl|spa|s\.p\.a\.|plc|"
    r"pty|pte|oy|ab|as|aps|kft|sp\. z o\.o\.|d\.o\.o\.|llp|lp|pc|pllc|group holdings)$", re.I)
SENIOR = [
    (re.compile(r"\b(founder|co-?founder|owner|ceo|chief executive|president|managing director|"
                r"managing partner|proprietor)\b", re.I), 5),
    (re.compile(r"\b(cfo|chief financial|coo|chief operating|cto|chief technology|"
                r"chief (product|revenue|commercial|investment|strategy) officer|c-?suite)\b", re.I), 4),
    (re.compile(r"\b(director|vp|vice president|head of|partner|principal|chair)\b", re.I), 3),
    (re.compile(r"\b(manager|lead|senior)\b", re.I), 1),
]

def deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))

def norm_company(company, email):
    c = (company or "").strip()
    c = re.split(r"\s*[|/•·]\s*", c)[0].strip()          # "BASCO | We Contain It All"
    c = re.sub(r"\s*[-–—]\s+.*$", "", c).strip()          # "Acme - the best widgets"
    prev = None
    while c and c != prev:                                # strip stacked legal suffixes
        prev = c
        c = SUFFIX.sub("", c).strip(" ,.")
    if not c or len(c) < 2:
        dom = (email.split("@")[-1] if "@" in email else "").split(".")[0]
        dom = re.sub(r"^(get|try|the|join|use|go)(?=[a-z]{4})", "", dom)
        c = dom
    if c.isupper() and len(c) > 4:
        c = c.title()
    elif c.islower():
        c = c.title()
    return re.sub(r"\s{2,}", " ", c).strip()

def slug_matches(slug, names):
    """names: iterable of (first, last) candidates - CRM name and the reply's display name."""
    s = deaccent(slug).lower()
    s = re.sub(r"[^a-z0-9]", "", s)
    s = re.sub(r"\d+$", "", s)
    for first, last in names:
        f, l = deaccent(first).lower(), deaccent(last).lower()
        f, l = re.sub(r"[^a-z]", "", f), re.sub(r"[^a-z]", "", l)
        if l and len(l) >= 4 and l in s:
            return True
        if f and len(f) >= 4 and f in s:
            return True
        if f and l:
            for cand in (f + l, f[0] + l, f + l[0], l + f, l + f[0], l[0] + f):
                if len(cand) >= 5 and cand in s:
                    return True
    return False


def name_candidates(lead, from_name):
    out = []
    f = (lead.get("first_name") or "").strip()
    l = (lead.get("last_name") or "").strip()
    if f or l:
        out.append((f, l))
    dn = re.sub(r"[<(\[].*?[>)\]]", " ", from_name or "").strip(" \"'")
    dn = re.split(r"\s*[|,/-]\s*", dn)[0].strip()
    toks = [t for t in re.split(r"\s+", dn) if len(t) > 1 and not t.isdigit()]
    if len(toks) >= 2:
        out.append((toks[0], toks[-1]))
    elif len(toks) == 1:
        out.append((toks[0], ""))
    return out


def seniority(title):
    t = title or ""
    for pat, score in SENIOR:
        if pat.search(t):
            return score
    return 0

def country_of(email, body, city):
    dom = email.split("@")[-1].lower() if "@" in email else ""
    tld = dom.rsplit(".", 1)[-1] if "." in dom else ""
    sld = ".".join(dom.rsplit(".", 2)[-2:]) if dom.count(".") >= 2 else ""
    if tld in CC_TLD and tld not in US_TLDS:
        return CC_TLD[tld], "domain"
    if sld.startswith("co.") or sld.startswith("com."):
        t2 = dom.rsplit(".", 1)[-1]
        if t2 in CC_TLD:
            return CC_TLD[t2], "domain"
    for cc in PHONE_CC.findall(body or "")[:6]:
        for n in (3, 2, 1):
            if cc[:n] in PHONE_CC_MAP:
                return PHONE_CC_MAP[cc[:n]], "phone"
            if cc[:n] == "1":
                break
    return "", ""

def load(paths):
    rows = {}
    for p in paths:
        for line in open(p):
            r = json.loads(line)
            if r.get("automated_reply"):
                continue
            lead = r.get("lead") or {}
            email = (lead.get("email") or r.get("from_email_address") or "").lower().strip()
            if not email:
                continue
            body = r.get("text_body") or ""
            cur = rows.setdefault(email, {"slugs": set(), "body": "", "date": "", "lead": lead,
                                          "campaigns": set(), "from_names": set()})
            if r.get("from_name"):
                cur["from_names"].add(r["from_name"])
            for s in SLUG.findall(body):
                cur["slugs"].add(s.rstrip("/.,)>\"'"))
            cur["campaigns"].add(r.get("campaign_id"))
            if (r.get("date_received") or "") > cur["date"]:
                cur["date"] = r.get("date_received") or ""
                cur["lead"] = lead or cur["lead"]
            cur["body"] += "\n" + body
    return rows

def main():
    company_side = {r["email"]: r for r in json.load(open("positives_company.json"))}
    rows = load(sorted(glob.glob("interested_replies.jsonl") + glob.glob("c287.jsonl")))
    # second pass: LinkedIn URLs found anywhere in the lead's thread, not just the
    # reply the team flagged as interested
    for path in glob.glob("lead_sig_slugs.jsonl"):
        for line in open(path):
            extra = json.loads(line)
            cur = rows.get(extra["email"])
            if cur is None:
                cs = company_side.get(extra["email"])
                if not cs:
                    continue
                cur = rows[extra["email"]] = {
                    "slugs": set(), "body": "", "date": cs["date_received"],
                    "lead": {"first_name": cs["first_name"], "last_name": cs["last_name"],
                             "title": cs["title"], "company": cs["company"],
                             "custom_variables": [{"name": "niche", "value": cs["niche"]}]},
                    "campaigns": set(), "from_names": set()}
            cur["slugs"].update(extra["slugs"])
            cur["from_names"].update(extra["from_names"])
    out = []
    for email, r in rows.items():
        if not r["slugs"]:
            continue
        lead = r["lead"] or {}
        first = (lead.get("first_name") or "").strip()
        last = (lead.get("last_name") or "").strip()
        if not first:
            continue
        cands = []
        for fn in list(r["from_names"]) or [""]:
            cands += name_candidates(lead, fn)
        verified = [s for s in r["slugs"] if slug_matches(s, cands)]
        if not verified:
            continue
        cs = company_side.get(email)
        niche = (cs or {}).get("niche") or ""
        if not niche:
            for cv in (lead.get("custom_variables") or []):
                if cv["name"].strip().lower() == "niche":
                    niche = (cv["value"] or "").strip()
        title = (cs or {}).get("title") or lead.get("title") or ""
        company = (cs or {}).get("company") or lead.get("company") or ""
        city = (cs or {}).get("city") or ""
        country, src = country_of(email, r["body"], city)
        out.append({
            "linkedin_url": "https://www.linkedin.com/in/" + sorted(verified, key=len)[0].lower(),
            "first_name": first,
            "company_name": norm_company(company, email),
            "niche": niche.lower(),
            "last_name": last,
            "title": title,
            "email": email,
            "country": country,
            "geo_source": src,
            "company_side": bool(cs),
            "seniority": seniority(title),
            "replied_at": r["date"][:10],
        })
    return out

if __name__ == "__main__":
    recs = [r for r in main() if r["company_side"] and r["niche"] and r["company_name"]]
    recs.sort(key=lambda r: (r["country"] == "", -r["seniority"], r["niche"] == "",
                             r["replied_at"]), reverse=False)
    recs.sort(key=lambda r: (0 if r["country"] else 1, -r["seniority"],
                             0 if r["niche"] else 1, r["replied_at"]))
    seen = set(); deduped = []
    for r in recs:                       # one row per LinkedIn profile
        if r["linkedin_url"] in seen:
            continue
        seen.add(r["linkedin_url"]); deduped.append(r)
    recs = deduped
    top = recs[:500]
    with open("heyreach_500.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["linkedin_url", "first_name", "company_name", "niche"])
        for r in top:
            w.writerow([r["linkedin_url"], r["first_name"], r["company_name"], r["niche"]])
    with open("heyreach_500_full.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        cols = ["linkedin_url", "first_name", "last_name", "company_name", "niche",
                "title", "country", "email", "replied_at"]
        w.writerow(cols)
        for r in top:
            w.writerow([r[c] for c in cols])
    print("verified linkedin + company-side:", len(recs), "| written:", len(top))
    print("non-US identified:", sum(1 for r in top if r["country"]))
    print("no niche:", sum(1 for r in top if not r["niche"]))
