**Subject: Master Version #2 — enriched Matched Trade table (ready for import)**

Hi [Client] / Will,

Got it — following the exact process from the Enrichment Plan & Workflow. Attached
is **Master Version #2**: your original Matched Trade table, untouched, with the
**30 enrichment columns appended** (15 exporter `Ex…` + 15 importer `Im…`). It's
ready for Will to import and generate the Magic Link + Arbitrage ID.

**Format**
- All 27,665 original rows and original columns are preserved exactly.
- 30 new columns per the workflow schema, for each side:
  Address, Country, Commodity, Department, Company Name, Email, Phone, Mobile,
  WhatsApp, LinkedIn, Job Title, HS Code, Website URL, First Name, Last Name.
- One primary decision-maker per company is mapped onto every trade row for that
  company (so the same exporter/importer carries the same contact across its rows).

**How the data was produced**
1. Structured the raw data and derived each company's real country from its address.
2. Found each company's website/domain (automated + AI).
3. Found the right people **by job title** — Sales/Export/Trade/Logistics for
   exporters; Procurement/Purchasing/Supply Chain/Import for importers.
4. **Waterfall enrichment** for emails, then again for phone/mobile (multiple data
   providers queried in sequence, first valid result kept).
5. QA: removed contacts where the domain step matched a company to an unrelated
   brand (e.g. AT&T, BMW) so no wrong contacts made it in.

**Coverage (expected, not 100%)**
A company has no contact when either (a) no domain could be verified, or (b) a
domain was found but no people in the target roles are publicly discoverable —
common with small/private manufacturers. Where we found people, the waterfall
doesn't always return both an email and a phone, so some rows have one or the other.

| | Exporters | Importers |
|---|---:|---:|
| Trade rows with an enriched contact | 1,473 | 7,481 |
| Rows with an email | 658 | 6,038 |
| Rows with a website | 17,358 | 22,214 |

Two notes:
- Emails/phones are in the new `ExEmail / ExMobile / ImEmail / ImMobile` columns;
  the original `Ex Email / Im Email` placeholder columns are left as-is. Happy to
  also backfill those originals if your import expects it.
- `Phone` and `WhatsApp` columns are included per the schema but mostly blank — the
  providers returned mobile numbers, not separate landline/WhatsApp.

Let me know once Will generates the Magic Links and I'll take Master FINAL into the
campaigns.

Best,
Achraf
