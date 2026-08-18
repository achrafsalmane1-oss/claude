# PHASE-REPORTS.md

Per spec §12: after each phase, what was built, what was skipped, and what is uncertain.

Written honestly. Where something is unverified, it says so.

---

## Phase 0 — Foundations

**Built.** Zod-validated environment that fails at boot with the offending key named; structured
JSON logger; backoff/jitter and bounded-concurrency helpers; per-key token bucket; the full Drizzle
schema (19 tables); pg-boss wrapper with typed job names and per-queue retry policies.

**Skipped.** Nothing.

**Uncertain.** Nothing material. Migration generated and applied cleanly against a live
PostgreSQL 16.

---

## Phase 1 — Ingestion and compliance

**Built.**

- whoisds daily NRD feed. URL construction and archive layout were verified against the live
  service before the parser was written, per spec §12.
- Certificate Transparency ingestion by direct RFC 6962 polling, checkpointed per log.
- A hand-written DER walker that extracts SANs from both `x509_entry` (full certificate) and
  `precert_entry` (bare TBSCertificate) leaves.
- PSL apex extraction with the private section deliberately disabled, plus a platform blocklist.
- Two-stage dedupe (in-process LRU, then the DB unique index).
- CZDS request/auth/download/diff tooling.
- Compliance in this phase rather than later: TXT-verified opt-out, public page and API, and the
  single `applySuppression()` gate.

**Verified live.** 413,154 real domains ingested from 2026-08-13; re-running inserted 0. The CT
poller processed ~13k entries across six logs from four operators, discovering ~6.4k apexes at a
35% dedupe hit rate.

**Skipped.**

- **CZDS is not scheduled.** The spec calls it a phase-1 stretch and explicitly not a v1 blocker.
  Approval is per-TLD and takes days to weeks.
- certstream, deliberately — see DECISIONS.md.

**Uncertain.**

1. **The free NRD feed is sometimes truncated.** 2026-08-15 returned exactly 70,000 lines against
   413,661 for 2026-08-13. A round number that size is an export cap, not a quiet day. Handled with
   a volume sanity check that records a warning and surfaces it on `/health`, but it means the free
   tier cannot be relied on for completeness. The paid feed or CZDS is the fix. **Flagged rather
   than worked around, per spec §12.**
2. **CZDS is written but never executed against the live service**, because it needs ICANN approval
   this build does not have. The request shapes follow ICANN's published API. Treat that module as
   unverified until someone runs it with real credentials.
3. CT logs start from the current tree head, so there is no historical backfill. That is
   intentional (backfilling means billions of entries) but means a fresh deployment sees no CT data
   for its first few minutes.

---

## Phase 2 — Enrichment

**Built.** The gated pipeline in the spec's order — DNS → MX → HTTP → RDAP → tech fingerprint —
with per-stage cost metering in micro-USD against a per-domain budget. Atomic work claiming with
`FOR UPDATE SKIP LOCKED`. Tiered parking detection. robots.txt honoured, with no page content
stored when disallowed. A redaction-safe RDAP parser.

**Verified live.** 1,300+ real domains enriched. Measured cost: **14.9 micro-USD per domain**
against a 200 micro-USD budget, comfortably inside the spec's unit-economics tripwire.

**Corrected mid-phase.** The design assumed the DNS gate would kill ~90% of a day's feed. Measured,
it kills **43%**. One job per domain for the HTTP stage would therefore have meant ~170k jobs/day —
exactly the load pg-boss is bad at. The HTTP and RDAP stages were re-cut as batched jobs with
per-item error isolation, bringing the steady state to ~14k jobs/day. DECISIONS.md carries the
measured table rather than the original estimate.

**Skipped.**

- **No headless browser.** It would cost roughly 100× per domain and break the unit economics the
  spec sets. A site that renders nothing without JavaScript is signal we lose knowingly.
- No WHOIS fallback where RDAP is unavailable — free-text WHOIS is unparseable and being retired.

**Uncertain.**

1. **Cost figures are amortised infrastructure estimates, not invoices.** DNS and RDAP are
   bandwidth and CPU on a box you already pay for. The *ratios* are right and the ledger is real;
   the absolute numbers should be re-based against your actual hosting bill.
2. **RDAP is still spent on domains that are obviously junk.** An empty page with no MX will be
   killed by the rules layer regardless, but it costs 5 micro-USD of RDAP first. Skipping RDAP for
   NRD-sourced domains with no content and no business MX would cut ~25% of that spend. Not done
   because the budget is not currently binding.
3. The MX, parking and tech tables are hand-maintained. They were extended twice from reading real
   pages and will drift; they need periodic review against a fresh sample.

---

## Phase 3 — Scoring

**Built.** The deterministic rules layer; the LLM classifier over the Anthropic Batch API with a
cached system prefix, `json_schema`-constrained output and a defensive parser; a transparent
weighted composite score; and the evaluation harness with 380 hand-labelled domains.

**The eval set earned its place immediately.** It found three real problems on its first run:

1. `redirects_off_domain` was killing real businesses whose site is served from a builder or
   hosting domain. It now requires the redirect to have no content behind it.
2. Every internationalised domain compared unequal to its own punycode final URL, so all IDNs
   looked like off-domain redirects. Both sides are now normalised to ASCII.
3. `.cyou` was hard-killing a real photo studio. `HARD_KILL_TLDS` was cut back to the Freenom
   free-registration family plus `.zip`/`.mov`; the rest were demoted to low-trust, where they cost
   points rather than ending the domain's life.

After those fixes: **140 rules kills, 100% correct, zero false kills.** Rules-only precision 61.7%
and recall 76.9% at threshold 50.

**Skipped.** No model training — a spec non-goal. The classifier is one API call, not a pipeline.

**Uncertain — read this before shipping.**

1. **The classifier has never been executed against the live API.** No `ANTHROPIC_API_KEY` was
   available in the build environment. The request construction follows the current SDK
   documentation and the response parser has 10 unit tests covering fenced, prefixed, truncated and
   malformed output — but the network path itself is unexercised. **Run `npm run eval` with a real
   key before trusting any precision number that includes the classifier.**
2. **All reported precision/recall figures are rules-only.** They are a floor, not the product's
   real performance. The gap is visible in the data: without the classifier, a slot-gambling site
   (`wakandaslot.dev`) scores 74 — identical to a real caregiving business — because every
   mechanical signal it has is real. Separating those two is precisely the classifier's job, and it
   is the single largest unvalidated assumption in this build.
3. **The eval set is 380 domains from one feed day, labelled by one reviewer.** The spec asks for
   300–500, so the size is right, but a single day skews toward whatever was registered that day
   (this one is heavy on Chinese sports-streaming SEO and Indonesian gambling), and single-reviewer
   labels carry that reviewer's judgement calls. Several are genuinely arguable — is a personal
   portfolio a business? is a grey-market pharmacy? The rule applied was "affirmative evidence of a
   real business", and the borderline calls are recorded in the `notes` column.
4. The classifier cost estimate (5,600 micro-USD/domain batched) is arithmetic from published
   pricing, not an observed bill.

---

## Phase 4 — API and delivery

**Built.** The flat Clay-shaped list endpoint, single-domain lookup with the full enrichment trail,
CSV export, saved searches, signed and queued webhooks, Resend digests, API-key auth with hashed
storage, Postgres fixed-window rate limiting with usage counting, and `/api/health`.

**Verified live.** List responds in ~80ms. Rate limiting allows exactly N then 429s with
`Retry-After`, and only successful requests count toward usage. The suppression gate was tested end
to end: after an opt-out, the domain disappears from list, detail (404) and CSV simultaneously.

**Found and fixed via the live response.** The meta-description regex ran across tag boundaries and
captured the viewport meta plus trailing markup. Regression tests added.

**Skipped.** No billing or Stripe — a spec non-goal; keys are issued by hand. No API versioning
beyond the `/v1` prefix.

**Uncertain.**

1. **Digest email has never been sent.** No `RESEND_API_KEY` was available. Rendering is unit
   tested, including HTML escaping of hostile page titles; the send path is not.
2. **Webhook delivery has never reached a real receiver.** Signing and verification are unit
   tested against each other, but no third-party endpoint has consumed a delivery.
3. Sub-2-second response is verified at ~1,500 scored rows. The keyset pagination and the composite
   index are designed for the real table size, but that has not been load-tested at 50M rows.

---

## Phase 5 — Dashboard, ops, docs

**Built.** Dashboard (filterable table, detail view with the full enrichment trail and classifier
reason, saved-search builder, API key management, CSV export), Better Auth email+password login,
the long-running worker process, alerting, `backfill.ts`, `sample.ts`, `issue-key.ts`,
`send-digests.ts`, `.env.example` with all 56 variables documented, README, Dockerfile and Railway
config.

**Verified live.** Every dashboard route renders real enrichment data behind an authenticated
session; unauthenticated requests redirect to `/login`.

**Found and fixed during verification.**

1. **`BETTER_AUTH_SECRET` was unset and silently regenerated at every boot**, so every restart
   signed out every user. It now fails at startup in production with instructions, and warns loudly
   in development. This is the kind of bug that looks fine locally and is a production incident.
2. **`issue-key.ts` created credential-less user rows**, which then permanently blocked that person
   from signing up ("user already exists"). It now refuses unless the account exists or `--api-only`
   is passed.

**Skipped.**

- No marketing pages — the spec says not to spend time there.
- No UI tests — the spec says skip them.
- No password reset flow. Accounts are issued by an operator in v1; adding one means wiring an
  email provider into the auth path for a feature nobody needs yet.

**Uncertain.**

1. **The worker has not been run as a long-lived process.** Its handlers, the CT poller and every
   scheduled task have each been exercised individually via scripts, and the process starts and
   registers cleanly — but it has not run for hours under real load. Restart behaviour, memory over
   a full day, and pg-boss archival at volume are unproven.
2. **Nothing has been deployed.** The Dockerfile and Railway configs are written from the
   documented shapes and are untested against a real build.
3. The alert path is unexercised end to end because no `ALERT_WEBHOOK_URL` was configured; the
   dedupe and resolution logic is straightforward but unproven against a real Slack endpoint.

---

## The three things to do first

1. **Set `ANTHROPIC_API_KEY` and run `npm run eval`.** Every precision number in this repo is
   rules-only. The classifier is the layer that separates a gambling site from a business, and it
   has never run.
2. **Run the worker for a full day** and watch `/api/health`. Everything about steady-state
   behaviour is inferred, not observed.
3. **Decide about the NRD feed.** The free tier truncates without warning. If completeness matters,
   that is either the paid feed or CZDS approval, and CZDS approval should be started now because
   it takes weeks.
