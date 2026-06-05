# Importer & Exporter Enrichment — Clay Run Plan

Prep + plan for enriching the client's raw L4 trade data into campaign-ready
contact lists. Decisions locked with Achraf: **full run both sides**, **up to
2–3 contacts/company**, **any found email** (no verification gate), output **two
CSVs** (exporters, importers).

## Files
| File | What it is |
|------|------------|
| `prepare_clay_inputs.py` | Reshapes raw CSV → Step-2 schema, splits country, dedupes to unique companies |
| `clay_input_exporters.csv` | **26,062** unique exporter companies, ready to import to Clay |
| `clay_input_importers.csv` | **1,018** unique importer companies, ready to import to Clay |
| `target_job_titles.md` | Exact title lists to target for each side |

## Raw data facts
- 27,665 rows. HS Code + addresses + company names 100% filled.
- **Email & Phone columns are 100% empty** → everything is net-new enrichment.
- Country is parsed from the address: exporters after the final ` / ` (all "China"
  in this batch); importers from the appended trailing token.
  ⚠️ **Importer source-country is unreliable** (e.g. a Michigan US address tagged
  "Argentina"). Clay's company enrichment will re-derive the authoritative HQ
  country, which should overwrite this column.

## Target schema (per side, Ex-/Im- prefix)
`Comp, Address, Country, Comm, HSCode, Dept, FName, LName, JobTitle, Email,
Phone, Mobile, WA (WhatsApp), LinkedIn, URL`
- Pre-filled from raw: Comp, Address, Country, Comm, HSCode.
- Filled by Clay: Dept, FName, LName, JobTitle, Email, Phone, Mobile, WA,
  LinkedIn, URL.

## Clay enrichment recipe (waterfall, per company)
1. **Company → Domain/URL**: company name + country → find official website/domain.
2. **Find People**: search contacts at the domain filtered to `target_job_titles.md`
   for that side; keep up to 2–3 best matches (seniority-ranked).
3. **Per contact**: First/Last name, Job Title, Department, LinkedIn URL.
4. **Work Email** (waterfall across providers) — keep any found (no verify gate).
5. **Phone / Mobile** (waterfall) — direct dial / mobile where available.
6. **WhatsApp**: populate where a mobile is found (= mobile unless flagged otherwise).
7. **Export** → join contacts back so each row carries the company's
   Comm/HSCode/Country → write final exporter & importer CSVs.

## Step 3 (later, not in this pass)
Doc says "add 4 more columns and resend for email campaign" — the 4 columns are
**not defined** in the source. Need the client to specify before we add them.

## ⚠️ How to run in Clay from here
The Clay MCP is **not connected to this Claude Code session** (only Google Drive,
Slack, GitHub are). To let me drive Clay directly, connect the Clay connector to
this session, then I can create the tables, run the waterfalls above, and export.
