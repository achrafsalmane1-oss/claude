# Otto → PE / VC / M&A deal-flow extraction

Pulls campaigns, leads and replies from the Otto sending platform
(`send.ottoresults.com`), isolates acquirer-side firms that replied positively,
and writes `pe_vc_ma_dealflow.csv`.

## Scope of the current API key

The key in use is **bound to the `Perry Street Partners` workspace only**.
`GET /api/workspaces` lists all 30 client workspaces, but every data endpoint
(`/api/campaigns`, `/api/leads`, `/api/replies`, `/api/sender-emails`) resolves
against the key's own workspace — no header, query param or nested route
overrides it. To cover the other 29 clients, one API key per workspace is needed.

## Run

```bash
export OTTO_API_KEY='<key>'
python3 build_dealflow_csv.py     # expects replies*.jsonl pulled from the API
```

## How a row qualifies

A lead is included when **both** hold:

1. **Firm type** — company name / email domain / title matches PE, VC, M&A,
   brokerage, family-office, search-fund or corp-dev signals, and is not an
   operating home-services business.
2. **Positive intent** — either Otto's own `interested` flag is set, or the
   prospect personally wrote a reply whose positive signals outweigh negative
   ones (bounces, auto-replies and out-of-office are excluded).

`confidence = High` when Otto flagged interest *and* the prospect replied in
person; `Medium` when only one of the two holds.

## Mandate column

`mandate_source` tells you where the mandate came from:

- `stated in reply` — quoted from what the prospect actually typed.
- `campaign targeting (sector variable)` — the `sector_list` variable the
  campaign personalised on (validated: seniority values like `senior` are
  rejected, they are not sectors).
- `campaign targeting` — inferred from which campaign's offer they answered.

Reply bodies from Otto contain the **whole quoted thread**, so `extract.py`
strips quoted history, forwarded chains and signatures before parsing — without
this the "mandate" comes back as Perry Street's own outbound copy quoted back.

## Buy-side campaigns in this workspace

| ID | Campaign | Offer |
|---|---|---|
| 1574 | Buyside!! | Off-market deal flow for acquirers |
| 867 | PE Firms Campaign | Deal-sourcing systems for PE firms |
| 1340 | Origin Buyer Outreach | "I have a few {SECTOR} owners looking at an exit" |
| 960 | Rhinogram Strategic Buyers | Live mandate: healthcare texting SaaS, ~$2.7M ARR |
| 1291 | Origin - Business Brokers | Seller-lead engine for brokers' own buy box |
