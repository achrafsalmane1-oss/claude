# Importer & Exporter Enrichment — Pipeline & Clay Run Plan

Turning the client's raw L4 trade data into campaign-ready contact lists.
Locked decisions: **full run both sides**, **up to 2–3 contacts/company**,
**any found email** (no verify gate), output **two CSVs** (exporters, importers).

## Pipeline
| Step | Script | Output |
|------|--------|--------|
| 1. Reshape + dedupe to unique companies, Ex-/Im- schema | `prepare_clay_inputs.py` | `clay_input_exporters.csv` (26,062), `clay_input_importers.csv` (1,018) |
| 2. Derive real physical Country from address; strip trade-lane tag | `detect_country.py` | (updates the input files) |
| 3. Resolve company → domain (best-effort, real lookups) | `resolve_domains.py` | `clay_input_*_domains.csv` (+`_url_match` score) |
| 4. **In Clay:** find people by title → email/phone waterfalls | (Clay UI) | Clay export of contacts |
| 5. Join contacts back + derive Department → final deliverable | `assemble_final.py` | final `exporters.csv`, `importers.csv` |

Steps 1–3 are done here. Step 4 runs in Clay (its enrichments are UI-built —
no API can construct them). Step 5 runs here once you export from Clay.

## Key data facts
- 27,665 rows. Email & phone 100% empty → all net-new enrichment.
- **The appended country is a trade-lane tag, not the company's country**: every
  importer row says `Argentina`, every exporter row says `China` (China→Argentina
  import data). Step 2 instead derives the **physical** country from the address
  (US state+ZIP, Argentine CPA codes, Panama free-zone, country names) and removes
  the tag from the address field. Importers resolved so far: Argentina 448, US 190,
  Panama 36, UK 2, Mexico 1; rest blank for Clay/AI to fill.
- Domain resolution hit-rate: importers **268/1,018 (26%)**. Lower expected for
  exporters (thin coverage of small Chinese mfrs). Blanks are left for your Clay
  AI/domain-finder step — never guessed.

## Target schema (per side, Ex-/Im- prefix)
`Comp, Address, Country, Comm, HSCode, Dept, FName, LName, JobTitle, Email,
Phone, Mobile, WA (WhatsApp), LinkedIn, URL`
- Pre-filled here: Comp, Address, Country, Comm, HSCode, URL (where resolved).
- Filled by Clay: FName, LName, JobTitle, Email, Phone, Mobile, WA, LinkedIn.
- Dept is derived from JobTitle by `assemble_final.py`.

## Clay table build (UI, ~15 min/side)
1. Import `clay_input_importers_domains.csv` / `clay_input_exporters_domains.csv`.
2. (Optional) AI/company step to fill blank `URL` and blank `Country`.
3. **Find People** at the domain, filtered to `target_job_titles.md` for that
   side; keep up to 2–3 best by seniority.
4. **Work Email** waterfall (keep any found). **Phone / Mobile** waterfall.
5. Export the contacts table.

## Step 5 — assemble the deliverable
```
python3 assemble_final.py --peek clay_export.csv      # see Clay's column names
# edit CONTACT_MAP in assemble_final.py if needed, then:
python3 assemble_final.py im clay_export.csv clay_input_importers_domains.csv importers.csv
python3 assemble_final.py ex clay_export.csv clay_input_exporters_domains.csv exporters.csv
```

## Open item — Step 3 of client's doc
"Add 4 more columns and resend for email campaign" — the 4 columns are **not
defined** in the source. Need the client to specify before that pass.

## Notes
- Clay API key is a *workspace* key (webhook ingestion only); it can't build or
  run enrichments, and does not auth the MCP (OAuth-only). The MCP is also not
  mounted in this Code session.
- Nothing is fabricated: unresolved domains/countries are left blank for Clay.
