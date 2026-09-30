"""Find the account's best day for positive replies.

The /api/replies endpoint lost pagination (15 rows, no cursor), so daily numbers
come from POST /api/campaigns/{id}/stats, which accepts a date range and still
returns sent / replies / interested plus a per-sequence-step breakdown.
"""
import calendar, datetime, json, sys
from concurrent.futures import ThreadPoolExecutor
import stats

def months(start="2025-03", end=None):
    end = end or datetime.date.today().strftime("%Y-%m")
    y, m = (int(x) for x in start.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= end:
        last = calendar.monthrange(y, m)[1]
        out.append((f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{last:02d}"))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out

def month_scan(cids, workers=10):
    jobs = [(c, s, e) for c in cids for s, e in months()]
    def f(j):
        c, s, e = j
        d = stats.day_stats(c, s, e) or {}
        return (c, s[:7], d.get("interested", 0), d.get("emails_sent", 0))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return [r for r in ex.map(f, jobs) if r[2] or r[3]]

def day_scan(pairs, workers=10):
    """pairs: (campaign_id, 'YYYY-MM') -> per-day rows for that month."""
    jobs = []
    for c, ym in pairs:
        y, m = (int(x) for x in ym.split("-"))
        for d in range(1, calendar.monthrange(y, m)[1] + 1):
            jobs.append((c, f"{y:04d}-{m:02d}-{d:02d}"))
    def f(j):
        c, d = j
        s = stats.day_stats(c, d) or {}
        return (d, c, s.get("interested", 0), s.get("emails_sent", 0),
                s.get("unique_replies_per_contact", 0))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return [r for r in ex.map(f, jobs) if r[2] or r[3]]

if __name__ == "__main__":
    cids = [int(x) for x in sys.argv[1:]] or [287]
    rows = month_scan(cids)
    json.dump(rows, open("month_scan.json", "w"))
    top = sorted(rows, key=lambda r: -r[2])[:12]
    for c, ym, i, s in top:
        print(f"campaign {c:>4} {ym} interested {i:>4} sent {s:>7,}")
