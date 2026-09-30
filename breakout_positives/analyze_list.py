import csv, collections, re, sys

def load(path):
    return list(csv.DictReader(open(path)))

def outcomes(rows):
    sent = sum(1 for r in rows if (r.get("Emails Sent") or "0").strip() not in ("", "0"))
    repl = sum(1 for r in rows if (r.get("Replies") or "0").strip() not in ("", "0"))
    intr = sum(1 for r in rows if (r.get("Interested") or "").strip() not in ("", "0"))
    return sent, repl, intr

def rate_table(rows, keyfn, label, minimum=200, top=22):
    buckets = collections.defaultdict(list)
    for r in rows:
        k = keyfn(r)
        if k is None: continue
        buckets[k].append(r)
    out = []
    for k, rs in buckets.items():
        s, rp, i = outcomes(rs)
        if len(rs) < minimum: continue
        out.append((k, len(rs), rp, 100*rp/len(rs), i, 100*i/len(rs)))
    out.sort(key=lambda x: -x[5])
    print(f"\n{label} (segments with >={minimum} leads, sorted by positive rate)")
    print(f'{"segment":<34}{"leads":>7}{"repl":>7}{"repl%":>7}{"pos":>6}{"pos%":>7}')
    for k, n, rp, rpp, i, ip in out[:top]:
        print(f'{str(k)[:33]:<34}{n:>7,}{rp:>7}{rpp:>7.2f}{i:>6}{ip:>7.2f}')
    return out

SENIOR = [
    ("founder/owner/CEO", re.compile(r"\b(founder|co-?founder|owner|ceo|chief executive|president|proprietor|managing (director|partner))\b", re.I)),
    ("other C-level", re.compile(r"\b(cfo|coo|cto|cmo|cro|chief \w+ officer)\b", re.I)),
    ("VP/Director/Head", re.compile(r"\b(vp|vice president|director|head of|partner|principal)\b", re.I)),
    ("manager/other", re.compile(r".", re.S)),
]
def seniority(r):
    t = (r.get("Title") or "").strip()
    if not t: return "no title"
    for name, pat in SENIOR:
        if pat.search(t): return name
    return "manager/other"

FREEMAIL = re.compile(r"@(gmail|yahoo|hotmail|outlook|aol|icloud|me|msn|live|protonmail|gmx|yandex)\.", re.I)
CCTLD = {"uk","de","fr","es","it","nl","be","ch","at","se","no","dk","fi","pl","pt","ie","cz","gr",
 "ro","hu","ca","au","nz","za","ng","ke","eg","ma","ae","sa","il","tr","in","sg","hk","jp","kr",
 "cn","tw","my","id","ph","th","vn","br","mx","ar","cl","pe","uy","ec","eu","ua","rs","dk","lt","lv","ee","is","mt","lu","si","sk","hr","bg","cy","pk","bd","lk","gh","tz","ug","zw","qa","kw","bh","om","jo","lb"}
def geo(r):
    dom = (r.get("Email") or "").split("@")[-1].lower()
    tld = dom.rsplit(".", 1)[-1] if "." in dom else ""
    if FREEMAIL.search(r.get("Email") or ""): return "freemail (gmail/yahoo/...)"
    if tld in CCTLD: return f"ccTLD .{tld}"
    return f"generic .{tld}"

def localpart(r):
    lp = (r.get("Email") or "").split("@")[0].lower()
    if re.match(r"^(info|contact|hello|sales|admin|office|team|support|enquiries|inquiries|mail)$", lp):
        return "role address (info@, sales@)"
    if "." in lp: return "first.last@"
    if "_" in lp: return "first_last@"
    if len(lp) <= 2: return "initials@"
    return "single token@"

INVESTOR_CO = re.compile(r"\b(capital|ventures?|equity|partners|holdings?|fund|investments?|asset management|family office|advisors?)\b", re.I)
def is_investor_company(r):
    return "investment-firm-shaped company" if INVESTOR_CO.search(r.get("Company") or "") else "operating company"

if __name__ == "__main__":
    rows = load(sys.argv[1] if len(sys.argv) > 1 else "c287_contacts.csv")
    s, rp, i = outcomes(rows)
    print(f"LIST: {len(rows):,} leads | sent {s:,} | replied {rp:,} ({100*rp/len(rows):.2f}%) | "
          f"positive {i:,} ({100*i/len(rows):.2f}% of leads, {100*i/max(rp,1):.1f}% of repliers)")
    rate_table(rows, lambda r: (r.get("niche") or "").strip().lower() or None, "BY NICHE", 300)
    rate_table(rows, seniority, "BY SENIORITY", 300, 8)
    rate_table(rows, geo, "BY EMAIL DOMAIN / GEO", 200, 14)
    rate_table(rows, localpart, "BY EMAIL LOCAL-PART SHAPE", 200, 8)
    rate_table(rows, is_investor_company, "BY COMPANY TYPE", 200, 4)
