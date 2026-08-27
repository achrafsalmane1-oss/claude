# Breakout — positive fundraising replies export

Pulls every reply flagged **interested** in the Breakout Bison workspace
(`send.breakoutcreatives.com`) and exports the company-side capital seekers —
the founders/CEOs/CFOs/directors at operating companies who replied positively
to the capital-raise outreach.

## Files

| File | What it is |
|---|---|
| `bison.py` | Thin API client (cursor pagination). Reads `BISON_TOKEN` from the environment. |
| `pull_parallel.py` | Pulls `/api/replies?folder=inbox&status=interested` per campaign, 8 campaigns in parallel, into `interested_replies.jsonl`. |
| `build.py` | Dedupes by email, splits company-side vs investor-side, writes the CSVs. |
| `fund_directors_positive_fundraising.csv` | The requested export: `first_name, last_name, niche, linkedin_url`. |
| `fund_directors_positive_fundraising_full.csv` | Same rows plus `email, title, company, city, replied_at, campaigns`. |

## Run

```bash
export BISON_TOKEN='...'          # Bison API token
python3 pull_parallel.py          # ~10 min for the full workspace
python3 build.py
```

## How the filter works

* **Positive** = the reply carries Bison's `interested` flag (what the team marks
  in the unibox); automated replies are dropped.
* **Company-side** = everything except (a) leads that came only from the
  investor-side campaigns (TUV PE/VC, TUV Family Offices, TUV Strategics,
  Buyside Relaunch, Buyside campaign, Breakout VC+PE, PE Offer, Sanket VC/PE
  lookalikes, Crunchbase data) and (b) leads whose title *and* company both read
  as a fund (Angel Investor, General/Managing Partner, Fund Manager at
  "… Capital / Ventures / Partners / Equity"). Campaigns that are not
  capital-raise outreach at all (Agency Partnerships, leads giveaway, Jericho AI)
  are excluded too.
* **niche** comes from the lead's `niche` custom variable in Bison.
* **linkedin_url** is empty: Bison stores no LinkedIn field on leads, so it needs
  an enrichment pass (DiscoLike exact-email match) to fill.

## Known gap in this export

One campaign — `287 Data backed campaign - Best performer` (~1,624 interested
replies) — was still downloading when the run was stopped, so its positives are
not in these CSVs. Re-run `pull_parallel.py` to pick it up.
