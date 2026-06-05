**Subject: Enriched contact data — Importers & Exporters (delivered)**

Hi [Client name],

The contact enrichment is complete. Attached are two files, ready for your email
outreach:

- **`importer_contacts.csv`** — decision-makers at the importing companies
- **`exporter_contacts.csv`** — decision-makers at the exporting companies

Here's exactly what we did and what the numbers look like.

---

### What we did

1. **Structured the raw trade data.** We took your raw L4 list, deduplicated it
   to unique companies, and separated each company's real country from its
   physical address (the source had every importer tagged "Argentina" and every
   exporter tagged "China" — that's the trade lane, not where each company sits,
   so we corrected it from the actual address).

2. **Found each company's website/domain.** Using a combination of automated
   lookups and AI matching on company name + address. The website is the key that
   lets us search for the right people.

3. **Found the right people — by job title.** For each company we searched for
   the specific roles you asked for:
   - **Importers:** Procurement, Purchasing, Strategic Sourcing, Supply Chain,
     Import/Customs and Trade Compliance leaders.
   - **Exporters:** Sales, Export, International Trade and Logistics leaders.
   We kept up to ~3 decision-makers per company.

4. **Emails — waterfall enrichment.** For each person we ran a "waterfall": we
   query multiple data providers in sequence, and take the first valid result.
   This maximizes how many real, deliverable emails we recover versus relying on
   a single source.

5. **Phone numbers — waterfall enrichment.** Same approach, across multiple
   phone/mobile providers.

6. **Quality cleaning.** The AI domain step occasionally matched a company to a
   famous but unrelated brand (e.g. a small trader incorrectly linked to AT&T or
   BMW). We detected and **removed those wrong matches** so you don't email the
   wrong people. We kept legitimate parent-company/abbreviation domains (e.g.
   Schlumberger → slb.com, Aceitera General Deheza → agd.com).

---

### Results

| | Importers | Exporters |
|---|---:|---:|
| Companies in list | 1,018 | 26,062 |
| Website/domain found | 828 (81%) | 16,337 (62%) |
| Companies with at least one contact | 204 | 1,274 |
| **Contacts delivered** | **653** | **5,393** |
| — with an email | 374 | 1,896 |
| — with a mobile/phone | 197 | 1,051 |
| Wrong-domain contacts removed | 12 | 102 |

---

### Why coverage isn't 100% (and that's expected)

A company drops out of the contact list for one of two reasons:

- **No domain could be verified** — without a confirmed website we can't reliably
  search for that company's people (190 importers, 9,725 exporters). Many are
  small or private manufacturers with no real web presence.
- **A domain was found, but no people in the target roles are publicly
  discoverable** (624 importers, 15,063 exporters). This is common with smaller
  Chinese manufacturers, where named procurement/sales staff simply aren't listed
  in the data providers we waterfall across.

And within the contacts we *did* find, the waterfall doesn't always return a
verified email **and** a phone for every person — so some rows have an email but
no phone, or vice versa. We included every contact where we found at least a name
and a verified profile, so you have the maximum to work with.

---

### How to read the files

Each row is one contact, with: Company Name, Country, Commodity, HS Code, Website,
Department, First/Last Name, Job Title, Email, Mobile Phone, LinkedIn, Location,
and a **Domain Match** column (High / Medium / Low). "Low" means the company's
domain was a confident-but-not-obvious match (e.g. an abbreviation) — worth a
quick eyeball before sending, but generally valid. We've also included a
`removed_for_review.csv` listing the wrong-domain contacts we pulled, in case you
want to audit.

If you'd like, we can take another pass at the no-domain companies to lift
coverage further.

Best,
[Your name]
