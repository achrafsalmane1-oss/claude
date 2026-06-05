# Deliverable — Enriched Contacts

## Files
| File | Rows | What it is |
|------|-----:|------------|
| `importer_contacts.csv` | 653 | Clean importer decision-maker contacts |
| `exporter_contacts.csv` | 5,393 | Clean exporter decision-maker contacts |
| `removed_for_review.csv` | 114 | Contacts removed because the domain was a verified mismatch (audit trail) |
| `CLIENT_EMAIL.md` | — | Ready-to-send summary email for the client |

## Columns (both contact files)
`Company Name, Country, Commodity, HS Code, Website, Department, First Name,
Last Name, Job Title, Email, Mobile Phone, LinkedIn Profile, Location, Domain Match`

- **Department** — derived from Job Title (Procurement / Purchasing, Import /
  Customs, Supply Chain, Logistics, Export / Trade, Sales).
- **Domain Match** — confidence that the company's website is correct:
  - `High` — name clearly maps to the domain.
  - `Medium` — good match.
  - `Low` — abbreviation/parent-brand domain; usually valid, worth a glance.

## Cleaning rule applied
A contact was removed only when its domain was both a poor name match **and** a
known wrong target — i.e. a famous unrelated brand (att, bmwusa, nestle,
novanthealth, …) or a B2B directory / trade-data / fair site (importgenius,
globalsources, tendata, kompass, messefrankfurt, hktdc, iata, …). Legitimate
abbreviation/parent-company domains were kept.

## Coverage funnel
| | Importers | Exporters |
|---|---:|---:|
| Companies | 1,018 | 26,062 |
| Domain found | 828 | 16,337 |
| No domain (can't search people) | 190 | 9,725 |
| Domain but no target-title people found | 624 | 15,063 |
| Companies with ≥1 contact | 204 | 1,274 |
| Contacts | 653 | 5,393 |
| — with email | 374 | 1,896 |
| — with phone | 197 | 1,051 |

## Reproduce
`python3 ../clean_and_assemble.py <folder-with-the-4-clay-exports>`

## Open item
Client's workflow Step 3 ("add 4 more columns and resend for campaign") — the 4
columns are still undefined; awaiting the client's spec.
