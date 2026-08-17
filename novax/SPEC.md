# SPEC.md — Newly Registered Domain Signal Engine

> This is the original product spec as handed to the build, preserved verbatim for provenance.
> Where the build deviates from it, the deviation is recorded in `DECISIONS.md`.

## 1. What we are building

A pipeline that detects newly registered domains within hours of registration, filters out the
~99% that are garbage, enriches the survivors into a usable company record, and delivers them as
an API / CSV / webhook / daily digest.

The raw feed of new domains is a commodity — anyone can get it. The product is the filter.
Roughly 250,000–300,000 new domains appear per day and almost all of them are parked pages,
dropcatches, typosquats, spam infrastructure, and SEO churn. The value is in reliably surfacing
the few hundred per day that represent a real company being born.

Judge every design decision against that: does it improve precision on "a real business just
started", or is it decoration?

## 2. Non-goals for v1

* No LinkedIn scraping. Not in v1, not as a "quick hack". It breaks the deployment and creates
  legal exposure.
* No multi-tenant billing/Stripe in v1. Manual API key issuance is fine until there are paying users.
* No Kubernetes, no microservices, no message bus beyond a job queue. One Postgres, one web app,
  one worker process.
* No ML model training. Rules plus an LLM classifier call is the v1 scoring layer.
* No mobile app, no Chrome extension.

## 3. Stack

Propose alternatives in DECISIONS.md if you disagree, but default to:

* Language: TypeScript end to end.
* Web: Next.js (App Router). Route handlers for the API, server components for the dashboard.
* DB: Postgres. Drizzle ORM. Neon or Supabase — pick one and justify.
* Queue: pg-boss (Postgres-backed, avoids a Redis dependency). If you can prove pg-boss won't hold
  up at ~300k jobs/day, use BullMQ + Redis and say so.
* Worker: a separate long-running Node process. It must not be serverless — the CT log ingester
  holds an open websocket.
* Deploy: worker + web on Railway or Fly.io (both need long-running processes and outbound
  network). DB managed. Do not assume Vercel.
* Email: Resend for digests.
* Auth: Better Auth or Clerk. Email + password is enough.

## 4. Data model

Design the schema, but it must cover at minimum:

* `domains` — apex domain, TLD, first_seen_at, source (ct_log | nrd_feed | czds), registration_date,
  current status.
* `domain_dns` — MX records, NS records, A/AAAA, TXT (SPF/DMARC presence), resolved_at. Keep
  history; nameserver changes are themselves a signal.
* `domain_http` — status code, final URL after redirects, page title, meta description, detected
  tech (from headers + HTML fingerprints), body text snippet (cap it), is_parked boolean, probed_at.
* `domain_rdap` — whatever RDAP returns: registrar, creation/expiry dates, status codes, registrant
  country/state where present. Expect the registrant name/email to be redacted almost always — do
  not build logic that depends on them.
* `domain_scores` — score, tier, classifier reason string, model version, scored_at.
* `companies` — the resolved entity: name, description, category, country, website, confidence.
* `saved_searches`, `users`, `api_keys`, `deliveries`, `opt_outs`.

Every enrichment table needs a `last_attempted_at` and a `failure_count` so retries don't loop
forever.

## 5. Phase 1 — Ingestion

Two sources. Build the daily feed first because it gets real data into the DB on day one with no
websocket complexity.

**5a. Daily NRD feed.** Download and parse the free daily newly-registered-domain dump (whoisds
publishes one; verify the current URL format and file structure yourself before writing the parser
— do not hardcode based on what you think you remember). Idempotent: re-running the same day must
not create duplicates.

**5b. Certificate Transparency stream.** This is the fast path — a domain shows up here within
minutes of a TLS cert being issued, which for a Cloudflare-fronted domain is essentially at setup
time. Consume CT logs via certstream or by polling CT log endpoints directly. The public certstream
server is flaky; build reconnection with exponential backoff and a health metric for "seconds since
last event".

Critical CT gotchas:

* CT gives you every SAN on every cert. Volume is millions of events/day and most are subdomains,
  renewals, and wildcards.
* Extract the apex using the Public Suffix List (the `tldts` package). Naive last-two-labels
  splitting breaks on `.co.uk`, `.com.au`, etc.
* Dedupe hard before anything else. A domain seen for the 40th time this week is not new.
* Cross-reference CT hits against the NRD feed / RDAP creation date. A cert on a 10-year-old domain
  is not a new registration.

**5c. CZDS (optional, phase 1 stretch).** ICANN zone files give complete gTLD coverage but only
daily snapshots with no ownership data, so you must diff against the previous day yourself.
Approval takes days to weeks and files are multi-GB. Write the request-and-diff tooling but treat
it as a later data-completeness upgrade, not a v1 blocker.

## 6. Phase 2 — Enrichment

Runs as queued jobs. Cheap checks gate expensive ones. Never enrich something that already failed
the previous gate.

Order of operations:

1. DNS resolve (cheapest). If no A record and no MX, the domain is unconfigured — park it in a
   low-priority requeue for 72h and stop.
2. MX classification. This is the single highest-signal cheap filter. Google Workspace or Microsoft
   365 MX records mean a human configured business email. Parked-domain MX or no MX means almost
   certainly noise. Build an MX provider classifier with a maintained lookup table.
3. HTTP probe. Follow redirects, capture status, final URL, title, meta description, first ~2000
   chars of visible body text. Detect parking pages (Sedo, Afternic, GoDaddy parking, registrar
   defaults, "coming soon" templates) with a pattern list and kill them here.
4. RDAP lookup. Registrar, creation date, status. Rate-limit per registry and cache aggressively.
   Expect redaction.
5. Tech fingerprint from response headers and HTML (Webflow, Framer, Shopify, Next.js, WordPress,
   etc.). Useful both as a filter and as an outreach signal.

Set a per-domain enrichment budget and log cost per domain. If enrichment costs more than a
fraction of a cent per domain at 300k/day, the unit economics break.

## 7. Phase 3 — Scoring

Two layers.

**Rules layer** (deterministic, runs on everything): hard-kill anything that is parked, has no MX
and no site, sits on a blocklisted TLD, matches typosquat patterns against a top-domains list, or
has a name that is random-character noise. This should eliminate the large majority before any LLM
cost is incurred.

**Classifier layer** (LLM, runs only on survivors): given the domain, page title, meta description,
body snippet, MX provider, and detected tech, output structured JSON:
`{ is_real_business: bool, category: string, stage_guess: string, confidence: 0-1, reason: string }`.
Force JSON-only output and parse defensively. Batch these calls.

Then a composite 0–100 score. Store `reason` — being able to tell a user why a domain surfaced is a
real differentiator over the black-box incumbents.

Build an evaluation set immediately. Hand-label 300–500 domains from a real day's feed as
good/garbage. Every scoring change gets measured against it. Without this you are tuning blind, and
precision is the entire product.

## 8. Phase 4 — API and delivery

* `GET /api/v1/domains` — filterable: date range, TLD, country, MX provider, score threshold,
  category, tech.
* `GET /api/v1/domains/:domain` — full enriched record.
* `POST /api/v1/searches` — save a filter set.
* `POST /api/v1/webhooks` — register a URL, get new matches pushed.
* CSV export.
* Daily digest email per saved search.

Design the API to be pasted straight into a Clay HTTP API column. Flat JSON response, one object per
domain, no deep nesting, stable key names, sub-2-second response. That is the distribution wedge —
GTM teams already live in Clay and will adopt a data source they can drop into an existing table
without an integration project.

API key auth via header. Per-key rate limits and usage counting from day one.

## 9. Phase 5 — Dashboard

Minimal. Next.js. A filterable table of scored domains, a saved-search builder, a detail view
showing the full enrichment trail and the classifier's reason, API key management, and CSV export.
Do not spend time on marketing pages.

## 10. Compliance — build this in phase 1, not later

This product surfaces information about identifiable people. Treat that seriously or it becomes
unsellable in Europe.

* Public `/opt-out` endpoint and page. Domain owner submits their domain, verifies control via a DNS
  TXT record, and the domain is permanently suppressed from all outputs. Every serious player in
  this category has one.
* Never store or output registrant personal data that RDAP redacted, and never attempt to circumvent
  redaction.
* Log the source and timestamp for every field so any record's provenance can be shown on request.
* Respect `robots.txt` on HTTP probes. Set an identifying User-Agent with a contact URL.
* Do not resell raw personal contact data in v1. Sell the company-level signal.

## 11. Operational requirements

* Structured logging throughout.
* A `/health` endpoint reporting: seconds since last CT event, last successful NRD feed download,
  queue depth per job type, enrichment failure rate.
* Alert if the CT stream is silent for more than 10 minutes or the daily feed fails.
* A `scripts/backfill.ts` that re-enriches a date range.
* A `scripts/sample.ts` that dumps N random scored domains from a given day as CSV so I can eyeball
  quality manually.
* `.env.example` with every variable documented.
* README with local setup that actually works from a clean clone.

## 12. Working agreement

* Verify external API shapes against live docs before writing parsers. Do not code from memory about
  third-party endpoints.
* If a data source turns out to be paywalled, dead, or different from what this spec describes, stop
  and tell me rather than building a workaround silently.
* Prefer boring, debuggable code. This pipeline will break at 3am and I need to read it.
* Tests on the parsers, the PSL apex extraction, the parking detector, and the scoring rules. Skip
  tests on UI.
* After each phase, write what you built, what you skipped, and what you are uncertain about.
