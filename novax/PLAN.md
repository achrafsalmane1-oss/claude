# PLAN.md — novaX

Build plan for the newly-registered-domain signal engine. Phases are ordered so that each one leaves
the system in a working, demonstrable state.

**Guiding constraint** (from `SPEC.md` §1): the raw feed is a commodity, the filter is the product.
Every phase below is judged on whether it improves precision on *"a real business just started"*.

---

## Phase 0 — Foundations

Nothing product-visible; everything after this depends on it.

- `package.json`, `tsconfig.json` (path alias `@/*` → `src/*`), `vitest.config.ts`, `.gitignore`
- `src/config/env.ts` — Zod-validated environment, fails loudly at boot with the missing key named
- `src/lib/logger.ts` — structured JSON logs (level, msg, ts, plus arbitrary context)
- `src/db/schema.ts` — full Drizzle schema (see §4 of the spec; expanded below)
- `src/db/index.ts` — connection, pooled for web, single for worker
- `drizzle.config.ts` + generated SQL migration
- `src/queue/index.ts` — pg-boss wrapper: `enqueue`, `work`, `queueDepths`, typed job names

**Done when:** `npm run typecheck` and `npm run db:migrate` succeed against a local Postgres.

## Phase 1 — Ingestion + compliance

Compliance ships here, not later, per spec §10.

- `src/ingest/nrd.ts` — whoisds daily feed: build URL, download, unzip in-memory, normalise, bulk
  upsert idempotently, record a `feed_runs` row
- `src/ingest/ct/log-list.ts` — fetch and cache the Google CT log list, select usable logs
- `src/ingest/ct/der.ts` — DER walker: MerkleTreeLeaf → cert/TBS bytes → SAN dNSNames
- `src/ingest/ct/poller.ts` — per-log `get-sth`/`get-entries` loop, checkpointed in `ct_log_state`,
  exponential backoff, `seconds_since_last_ct_event` metric
- `src/ingest/apex.ts` — PSL apex extraction, wildcard stripping, platform-suffix blocklist
- `src/ingest/dedupe.ts` — LRU + `ON CONFLICT DO NOTHING`
- `src/ingest/czds.ts` — ICANN CZDS auth, zone download, day-over-day diff (built, not scheduled)
- `src/compliance/opt-out.ts` + `src/compliance/suppression.ts` — TXT-verified opt-out and the single
  `applySuppression()` gate every output path uses
- Tests: apex extraction, DER parsing, NRD parsing, dedupe, CZDS diff

**Done when:** `npm run ingest:nrd -- --date=YYYY-MM-DD` fills `domains`, re-running it inserts
nothing new, and the CT poller advances its checkpoint against a live log.

## Phase 2 — Enrichment

Queued jobs, cheap gates first, hard budget.

- `src/enrich/dns.ts` — batched resolve (A/AAAA/MX/NS/TXT); no A and no MX → 72h low-priority
  requeue and stop
- `src/enrich/mx.ts` — MX provider classifier + lookup table (Google Workspace, M365, Zoho, Fastmail,
  Proton, Migadu, registrar-parking MX, …)
- `src/enrich/http.ts` — robots-respecting probe, redirects, title/meta/body-snippet, size and time caps
- `src/enrich/parking.ts` — parking/for-sale/coming-soon detector (Sedo, Afternic, GoDaddy, Bodis,
  registrar defaults, template phrases)
- `src/enrich/rdap.ts` — IANA bootstrap, per-registry token bucket, redaction-safe parser
- `src/enrich/tech.ts` — header + HTML fingerprints
- `src/enrich/pipeline.ts` — gate orchestration, `enrichment_costs` metering, failure counts
- Tests: MX classification, parking detection, RDAP redaction handling, tech fingerprints, gate order

**Done when:** a domain flows DNS → MX → HTTP → RDAP → tech, cost is recorded, and a domain that
fails a gate provably never reaches the next one.

## Phase 3 — Scoring

- `src/score/rules.ts` — deterministic hard-kills (parked, no MX + no site, blocklisted TLD,
  typosquat vs top-domains list, random-character noise) → most of the feed dies here
- `src/score/classifier.ts` — Anthropic Batch API, `json_schema` output, prompt-cached prefix,
  defensive parse
- `src/score/composite.ts` — transparent weighted 0–100 score + tier + reason string
- `src/score/pipeline.ts` — rules → batch submit → poll → persist `domain_scores` + `companies`
- `eval/labels.csv` + `src/eval/run.ts` — precision/recall/F1 against the hand-labelled set,
  compared per `SCORING_VERSION`
- Tests: every rule, composite arithmetic, defensive parsing of malformed model output

**Done when:** `npm run eval` prints precision/recall against the labelled set and a rules change
moves the number.

## Phase 4 — API and delivery

- `app/api/v1/domains/route.ts` — flat, filterable, keyset-paginated, suppression-gated
- `app/api/v1/domains/[domain]/route.ts` — full enriched record with provenance
- `app/api/v1/searches/route.ts` — saved searches
- `app/api/v1/webhooks/route.ts` — registration; `src/delivery/webhooks.ts` — signed, queued, retried
- `app/api/v1/export/route.ts` — CSV streaming
- `src/delivery/digest.ts` — Resend daily digest per saved search
- `src/api/auth.ts` — API key hashing/verification; `src/api/rate-limit.ts` — Postgres fixed window
- `app/api/health/route.ts` — the four metrics from spec §11
- Tests: filter → SQL translation, key auth, rate limiting, CSV shaping, webhook signature

**Done when:** a `GET /api/v1/domains?min_score=70` returns flat JSON in under 2s and pastes into a
Clay HTTP column unmodified.

## Phase 5 — Dashboard, ops, docs

- `app/(dashboard)/domains` — filterable table; `app/(dashboard)/domains/[domain]` — enrichment trail
  and classifier reason; `app/(dashboard)/searches`; `app/(dashboard)/keys`
- `app/opt-out` — public opt-out page and TXT verification flow
- `scripts/backfill.ts`, `scripts/sample.ts`, `scripts/issue-key.ts`, `scripts/label-helper.ts`
- `src/ops/alerts.ts` — CT silence > 10 min, NRD feed failure
- `.env.example`, `README.md` verified from a clean clone, `Dockerfile`, `railway.json`
- `PHASE-REPORTS.md` — built / skipped / uncertain, per phase

**Done when:** a clean clone reaches a running dashboard by following the README only.

---

## File tree

```
novax/
├── SPEC.md                       # original spec, preserved
├── PLAN.md                       # this file
├── DECISIONS.md                  # stack choices + rejected alternatives
├── PHASE-REPORTS.md              # built / skipped / uncertain, per phase
├── README.md                     # clean-clone setup
├── .env.example                  # every variable, documented
├── Dockerfile
├── railway.json
├── package.json
├── tsconfig.json
├── next.config.ts
├── vitest.config.ts
├── drizzle.config.ts
│
├── src/
│   ├── config/env.ts             # Zod-validated environment
│   ├── lib/
│   │   ├── logger.ts             # structured JSON logging
│   │   ├── http.ts               # undici fetch w/ timeout, size cap, identifying UA
│   │   ├── backoff.ts            # exponential backoff + jitter
│   │   └── token-bucket.ts       # per-registry rate limiting
│   ├── db/
│   │   ├── schema.ts             # Drizzle schema (all tables)
│   │   ├── index.ts              # connection
│   │   └── migrations/           # generated SQL
│   ├── queue/
│   │   ├── index.ts              # pg-boss wrapper, typed job names
│   │   └── jobs.ts               # job name + payload types
│   ├── ingest/
│   │   ├── apex.ts               # PSL apex extraction + platform blocklist
│   │   ├── dedupe.ts             # LRU + DB conflict dedupe
│   │   ├── nrd.ts                # whoisds daily feed
│   │   ├── czds.ts               # ICANN zone request + diff (unscheduled)
│   │   └── ct/
│   │       ├── der.ts            # MerkleTreeLeaf + DER SAN extraction
│   │       ├── log-list.ts       # CT log discovery
│   │       └── poller.ts         # checkpointed get-entries loop
│   ├── enrich/
│   │   ├── pipeline.ts           # gate orchestration + cost metering
│   │   ├── dns.ts  mx.ts  http.ts  parking.ts  rdap.ts  tech.ts
│   │   └── data/mx-providers.ts  parking-patterns.ts  tech-fingerprints.ts
│   ├── score/
│   │   ├── rules.ts  classifier.ts  composite.ts  pipeline.ts
│   │   └── data/blocked-tlds.ts  top-domains.ts
│   ├── compliance/
│   │   ├── opt-out.ts            # TXT-verified opt-out
│   │   └── suppression.ts        # the single applySuppression() gate
│   ├── api/
│   │   ├── auth.ts               # API key hash + verify
│   │   ├── rate-limit.ts         # Postgres fixed window
│   │   ├── filters.ts            # query params → SQL
│   │   └── serialize.ts          # flat, Clay-shaped JSON
│   ├── delivery/
│   │   ├── webhooks.ts           # signed, queued, retried
│   │   └── digest.ts             # Resend daily digest
│   ├── ops/
│   │   ├── health.ts             # the four spec metrics
│   │   └── alerts.ts             # CT silence, feed failure
│   └── eval/run.ts               # precision/recall harness
│
├── worker/index.ts               # long-running process: registers all job handlers + CT poller
│
├── app/                          # Next.js App Router
│   ├── layout.tsx  globals.css
│   ├── api/
│   │   ├── health/route.ts
│   │   └── v1/
│   │       ├── domains/route.ts
│   │       ├── domains/[domain]/route.ts
│   │       ├── searches/route.ts
│   │       ├── webhooks/route.ts
│   │       └── export/route.ts
│   ├── opt-out/                  # public opt-out page + verify
│   └── (dashboard)/
│       ├── domains/  searches/  keys/
│
├── scripts/
│   ├── backfill.ts               # re-enrich a date range
│   ├── sample.ts                 # N random scored domains from a day, as CSV
│   ├── issue-key.ts              # manual API key issuance
│   └── label-helper.ts           # build the eval set
│
├── eval/labels.csv               # hand-labelled evaluation set
└── tests/                        # vitest: parsers, apex, parking, rules, API filters
```

## Data model summary

Beyond the spec's minimum, every enrichment table carries `last_attempted_at`, `failure_count`, and
a `source` + observed-at pair for provenance.

| Table | Purpose |
|---|---|
| `domains` | apex, tld, first_seen_at, source, registration_date, status, is_suppressed |
| `domain_dns` | append-only: a/aaaa/mx/ns/txt, has_spf, has_dmarc, resolved_at |
| `domain_http` | status, final_url, title, meta_description, body_snippet, tech[], is_parked, probed_at |
| `domain_rdap` | registrar, created/expires, statuses, country/state (redaction-safe), fetched_at |
| `domain_scores` | score, tier, reason, rules_verdict, classifier JSON, model, scoring_version |
| `companies` | name, description, category, country, website, confidence |
| `users`, `sessions`, `accounts`, `verifications` | Better Auth |
| `api_keys` | hashed key, prefix, rate limit, usage counters |
| `api_usage` | fixed-window rate limit + usage counting |
| `saved_searches` | filter set + digest opt-in |
| `webhooks`, `deliveries` | endpoints, signed delivery attempts, retry state |
| `opt_outs` | domain, token, verified_at, permanent suppression |
| `feed_runs`, `ct_log_state` | ingestion checkpoints and health |
| `enrichment_costs` | per-domain, per-stage micro-dollars |

## Risks

| Risk | Mitigation |
|---|---|
| Free NRD feed truncates or disappears | Volume sanity check + alert; CT poller is an independent second source; CZDS tooling is the documented upgrade path |
| CT volume overwhelms the pipeline | LRU dedupe before any DB write; CT produces *candidates*, and DNS is the real gate |
| Classifier precision below the eval bar | The eval set is built before tuning; the composite score is transparent and adjustable without retraining |
| Registry rate-limits / bans the RDAP caller | Per-registry token bucket, aggressive caching, identifying UA with a contact URL |
| pg-boss throughput | Batched DNS jobs + gate attrition keep it at tens of thousands/day; BullMQ swap is isolated behind `src/queue/index.ts` |
