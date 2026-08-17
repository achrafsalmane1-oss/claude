# DECISIONS.md — novaX

Every stack and design choice, why it was made, and what was rejected. One line of reasoning each.
Where a choice deviates from `SPEC.md`, it is marked **[deviation]** and justified.

## Live verification performed before any parser was written

Per §12 of the spec, these were checked against the live services on 2026-08-17, not from memory:

| Thing | What was verified | Result |
|---|---|---|
| whoisds NRD daily feed | URL construction, HTTP status, archive layout | `https://www.whoisds.com/whois-database/newly-registered-domains/{base64("YYYY-MM-DD.zip") minus trailing "="}/nrd` → HTTP 200, ZIP containing a single `domain-names.txt`, one apex per line. 2026-08-13 = 413,661 domains (164k `.com`, 68k `.xyz`). **Free-tier caveat: 2026-08-15 returned exactly 70,000 lines — a suspiciously round number that indicates a truncated/partial free-tier file.** Handled with a volume sanity check, not ignored. |
| CT log list | `https://www.gstatic.com/ct/log_list/v3/log_list.json` | HTTP 200, `version 89.22`, `operators[].logs[]` with `url`, `state.usable`, `temporal_interval`. Used to auto-discover currently-usable logs instead of hardcoding. |
| CT `get-sth` / `get-entries` | RFC 6962 endpoints on a live Google log | `get-sth` → `{tree_size, timestamp, sha256_root_hash, ...}`. `get-entries?start=&end=` → `{entries:[{leaf_input, extra_data}]}`. Server caps the returned batch; response honours fewer entries than requested. |
| CT leaf parsing | Wrote a DER walker and ran it against real entries | Both `x509_entry` and `precert_entry` leaves parse; SANs extracted correctly from full certs *and* from bare TBSCertificates (precerts). Confirmed on live data: `["*.powiatprzemysl.pl","powiatprzemysl.pl"]`, `["tumblr.untrainedeats.com"]`. |
| RDAP | `https://rdap.org/domain/stripe.com`, `https://data.iana.org/rdap/dns.json` | rdap.org 302-redirects to the authoritative registry (`rdap.verisign.com`). Response has `events[]` (`registration`/`expiration`/`last changed`), `status[]`, `entities[]` with `roles`, `nameservers[]`. Confirmed: registrar entity's vCard carried only `version` and `fn` — **registrant contact data was fully redacted, exactly as the spec predicts.** |
| `tldts` PSL behaviour | `parse()` on `.co.uk`, `.com.au`, `github.io` | `foo.bar.co.uk → bar.co.uk`, `x.com.au → x.com.au`, `a.b.github.io → github.io`. See "PSL private section" below — the default is the behaviour we want. |

Nothing in the spec turned out to be paywalled or dead. One material finding — the free NRD feed is
sometimes truncated — is reported in `PHASE-REPORTS.md` rather than silently worked around.

## Language and runtime

| Decision | Reason | Rejected |
|---|---|---|
| TypeScript end to end, Node 22 | Spec mandate; one language for web + worker means shared types for the domain record, which is the object every layer touches. | Python for the pipeline (better DNS/DER ecosystem) — rejected because it forces a second toolchain and duplicate models for a marginal library win. |
| `tsx` to run the worker, `tsc --noEmit` for typechecking | Boring: no bundler in the worker path, stack traces point at the real `.ts` line at 3am. | `esbuild`/`tsup` prebuild — rejected, adds a build artifact to debug through for zero runtime gain. |
| Single package at the repo root, not a monorepo | Web and worker share one `src/` via a `@/` tsconfig path. One `package.json`, one `node_modules`, one install. Two Railway services run different start commands off the same image. | npm workspaces with `packages/core` — rejected: workspace hoisting plus Next.js transpilation of a linked package is a category of bug we do not need at this size. |

## Web and API

| Decision | Reason | Rejected |
|---|---|---|
| Next.js 15 App Router | Spec mandate. Route handlers give the API and server components give the dashboard with no second framework. | Fastify API + separate SPA — rejected as two deployables where one suffices. |
| API responses are **flat** — every field a scalar at the top level | The distribution wedge is Clay's HTTP API column, which maps JSON keys to spreadsheet columns and handles nesting badly. `mx_provider` beats `dns.mx.provider`. | Nested resource-shaped JSON — rejected; it is prettier and unusable in the channel we are selling through. |
| Keyset (cursor) pagination on `(first_seen_at, id)` | Sub-2s responses at any offset; `OFFSET 50000` on a 50M-row table is not sub-2s. | `LIMIT/OFFSET` — rejected on latency at depth. |

## Database

| Decision | Reason | Rejected |
|---|---|---|
| **Neon** Postgres | Scale-to-zero and instant branching mean a throwaway branch per eval run, and the storage/compute split matters when `domains` grows by ~300k rows/day. | Supabase — rejected *for this workload*: we use none of its auth/realtime/storage surface, so it is a heavier product for the same Postgres. Choose Supabase instead if you later want its auth to replace Better Auth. |
| Drizzle ORM | Spec mandate, and its SQL-shaped API means the generated query is the query you read — important for a filter API where the plan matters. | Prisma — rejected: extra engine, slower cold starts, less direct control over the composite index our filter API leans on. |
| Enrichment tables are **append-only history**, with a partial unique index for "latest" | Spec requires nameserver-change history; a mutable row throws away the signal. `domain_dns` keeps every observation. | Single mutable row per domain — rejected, destroys the change signal the spec explicitly asks for. |
| `domains.apex` is the natural key, `citext`-style lowercase-normalised at write time | Every source produces the same apex; deduping on it is what makes re-ingest idempotent. | Surrogate-key-only with a separate uniqueness check — rejected as a race waiting to happen at 300k inserts/day. |

## Queue

| Decision | Reason | Rejected |
|---|---|---|
| **pg-boss**, with the load reshaped so it never sees 300k jobs/day | Spec's preference, and it removes Redis from the deployment. See the sizing note below — the naive "one job per domain" design is what breaks pg-boss, not pg-boss itself. | BullMQ + Redis — rejected because the fix (batching) is cheap and correct anyway; a second stateful service is not. Documented as the escape hatch if throughput is ever the real constraint. |

**Sizing, since the spec asked for proof either way.** pg-boss at one job per domain per stage would
be ~1.2M jobs/day (4 stages × 300k) — every job is an INSERT, a polled UPDATE for the fetch, and a
completion write, against a table that also has to be archived. That is the regime where people
report pg-boss struggling. novaX does not run that way:

- **DNS is batched.** One `dns.resolve.batch` job carries 500 apexes → 600 jobs/day, not 300k.
- **DNS is also the gate.** ~85–95% of a day's feed has no A and no MX record and never produces a
  second job. The stages after it see thousands, not hundreds of thousands.
- **The LLM classifier runs through the Anthropic Batch API**, so a whole day is one job, not one
  job per domain.

Realistic steady state is **low tens of thousands of jobs/day**, which pg-boss handles on a small
Postgres without argument. `QUEUE_DNS_BATCH_SIZE` is the tuning knob. If a future source pushes this
past ~500k jobs/day, swap to BullMQ — the queue is behind `src/queue/index.ts` for exactly that
reason.

## Ingestion

| Decision | Reason | Rejected |
|---|---|---|
| **Poll CT logs directly (RFC 6962), do not use certstream** **[deviation]** | The spec permits either and warns the public certstream server is flaky. Its own maintainers state the public server is a demo not meant for production. Direct polling has no third party in the path, resumes from a stored `tree_size` after a crash with zero gaps, and parallelises across logs. | certstream websocket — rejected: an unreliable dependency whose failure mode (silent staleness) is exactly what the health metric exists to catch. The `seconds_since_last_ct_event` metric the spec asks for is kept and now measures *our* poller. |
| Hand-written ~90-line DER walker for SAN extraction | Verified against live x509 *and* precert entries. Precert leaves contain a bare TBSCertificate, which most X.509 libraries refuse to parse; a walker that scans for the SAN extension OID handles both uniformly with zero dependencies. | `@peculiar/x509` / `node-forge` — rejected: heavier, and neither parses a bare TBSCertificate without contortions. This is the single most-tested file in the repo. |
| `tldts` with `allowPrivateDomains: false` (the default) | We want the **registrable** domain — what someone paid a registrar for. `github.io` is a registration; `myapp.github.io` is not. The default gives `a.b.github.io → github.io`, which is correct for us, and then the platform-suffix blocklist kills it. | `allowPrivateDomains: true` — rejected: it would treat every Vercel/GitHub Pages subdomain as a separate new registration and flood the pipeline. This is subtle enough that it has a dedicated test. |
| Two-stage dedupe: in-process LRU, then `ON CONFLICT DO NOTHING` | CT emits millions of SANs/day, mostly repeats. The LRU absorbs the repeat traffic without a DB round-trip; the DB constraint is the correctness backstop. | DB-only dedupe — rejected on write amplification. LRU-only — rejected, it is not a correctness boundary. |
| A CT hit only becomes a *candidate*; RDAP creation date decides newness | The spec's own gotcha: a cert on a 10-year-old domain is not a new registration. Age is confirmed against the NRD feed or the RDAP `registration` event. | Trusting CT as a registration signal — rejected, it is a TLS signal that correlates with registration. |
| CZDS tooling written, not wired to the scheduler | Spec calls it a stretch and explicitly not a v1 blocker; approval takes weeks. The request client and the day-over-day diff exist and are tested against a synthetic zone file. | Blocking v1 on CZDS approval — rejected per spec. |

## Enrichment

| Decision | Reason | Rejected |
|---|---|---|
| Strict gate ordering: DNS → MX → HTTP → RDAP → tech | Spec mandate, and it is the cost order. The gate kills ~90% before anything expensive runs. | Parallel enrichment — rejected: it spends the HTTP and RDAP budget on domains DNS already disqualified. |
| Node's built-in `dns/promises` against a configurable resolver | Zero dependencies, and `Resolver` instances let us pin `DNS_SERVERS` and a per-query timeout. | `dns-packet`/raw UDP — rejected as needless. A third-party DNS API — rejected on cost at this volume. |
| HTTP probe is `undici` with a hard 8s timeout, 5 redirects, 512KB body cap, and `robots.txt` checked first | The cap is what keeps p99 latency and egress bounded; robots compliance is a spec requirement, not a nicety. | Headless browser rendering — rejected: ~100× the cost per domain and it breaks the unit economics the spec sets. A JS-rendered page that shows nothing without JS is a legitimate signal loss we accept. |
| RDAP via the IANA bootstrap file, cached, with a per-registry token bucket | Registries rate-limit per-IP and will ban a hot caller. Bootstrap gives the authoritative server per TLD; rdap.org is the fallback. | rdap.org for everything — rejected: single point of failure and an extra hop we cannot rate-limit politely. WHOIS — rejected: unparseable free text, being retired. |
| Tech fingerprints are a hand-maintained table of header + HTML patterns | ~40 rules covers Webflow/Framer/Shopify/Next/WordPress/Vercel/Wix/Squarespace, which is most of what a new company actually ships on. Auditable, no license question. | Wappalyzer rule import — rejected on licensing and weight. |
| Cost is metered per domain in `enrichment_costs` in micro-dollars | The spec sets a unit-economics tripwire; you cannot honour a budget you do not measure. `/health` exposes the rolling per-domain cost. | Estimating cost offline — rejected, it drifts from reality immediately. |

## Scoring

| Decision | Reason | Rejected |
|---|---|---|
| Rules layer is pure functions over a plain input object | Fully testable with no DB and no network, which is the only way the eval harness stays fast. | Rules as SQL — rejected as untestable and unreadable. |
| **`claude-opus-5`** as the classifier default, via the **Batch API** with prompt caching | Best precision, and precision is the entire product. Batch is 50% off and this workload has no latency requirement. The cached prefix (system prompt + taxonomy) is ~1.2k tokens and is reused across every request. | Defaulting to a cheaper model to save money — rejected: that is the operator's call, not the build's. `CLASSIFIER_MODEL` is an env var and `DECISIONS` documents the arithmetic below so the tradeoff is an informed one. |
| Structured output via `output_config.format` `json_schema`, plus a defensive parser | The spec says force JSON-only and parse defensively. The schema constrains the model; the parser still handles fence-wrapped and truncated output and falls back to `is_real_business: false` rather than throwing. | Prompted "reply only with JSON" — rejected as strictly weaker than a schema constraint. Assistant prefill — rejected: it is a 400 error on current models. |
| Composite score is a transparent weighted sum, versioned as `SCORING_VERSION` | The differentiator is being able to say *why* a domain surfaced. A weighted sum can be explained in one sentence; a model cannot. Version-stamping every score makes eval comparisons honest. | An opaque learned scorer — rejected, and the spec rules out model training in v1. |
| Eval set is 300–500 hand-labelled domains sampled from a real feed day, stored as a CSV in-repo | Spec mandate. Kept in-repo so a scoring change and its measured effect land in the same commit. | Labelling synthetic domains — rejected as tuning against a fiction. |

**Classifier cost arithmetic** (why this survives the unit-economics test). The classifier only sees
rules-layer survivors — a few thousand a day, not 300k. At ~1,500 input / ~150 output tokens per
domain and 5,000 survivors/day: Opus 5 at list price is ~$56/day, ~$28/day through Batch, and less
again once the cached prefix is discounted. Against 300k ingested domains that is well under
0.01¢/domain, inside the spec's budget. Set `CLASSIFIER_MODEL=claude-haiku-4-5` to cut it ~5× if
precision on the eval set holds — measure before you switch.

## Delivery, auth, compliance

| Decision | Reason | Rejected |
|---|---|---|
| **Better Auth** for dashboard login, email + password | Spec option; self-hosted, so no third-party dependency in the login path and no per-seat cost pre-revenue. Its tables live in the same Postgres and the same migration flow. | Clerk — rejected: an external dependency and a bill for a feature that is one form. |
| API keys are separate from user sessions: `nvx_live_<32 bytes>`, only a SHA-256 hash stored | Machine credentials and human sessions have different lifetimes and blast radii. Hash-only storage means a DB leak does not leak working keys. | Reusing session cookies for the API — rejected: unusable from Clay and wrong security-wise. |
| Rate limiting is a Postgres fixed-window counter | One less service, correct across multiple web instances, and the same table is the usage counter the spec wants from day one. | In-memory limiter — rejected, wrong the moment there are two instances. Redis — rejected, see queue. |
| Webhook deliveries are queued, signed (HMAC-SHA256 over timestamp + body), and retried with backoff | An unsigned webhook cannot be verified by the receiver; an unqueued one makes the API request wait on someone else's server. | Fire-and-forget in the request path — rejected on both counts. |
| Opt-out suppression is enforced in **one** query builder that every output path calls | A compliance control with two code paths has one code path that is wrong. Every read of scored domains goes through `applySuppression()`. | Filtering per endpoint — rejected: guaranteed to be missed on the next endpoint added. |
| Opt-out requires a DNS TXT proof (`novax-verify=<token>`), then suppresses permanently | Anyone can type a domain into a form; TXT control is the cheapest real proof of authority. Permanent because the spec says permanent. | Email verification to the RDAP contact — rejected: that contact is redacted, which is the whole point. |
| Redacted RDAP fields are dropped at parse time, never persisted | Spec requirement. The parser skips vCard entries flagged redacted, so redacted PII cannot reach the DB even by accident. | Storing and filtering on read — rejected: read filters get bypassed. |
| Every stored field carries `source` + observed-at | Spec requires per-field provenance so a record's origin can be shown on request. | A single row-level timestamp — rejected as insufficient to answer "where did this field come from". |

## Deployment

| Decision | Reason | Rejected |
|---|---|---|
| **Railway**, two services (web, worker) from one repo, Neon as the DB | Long-running processes with outbound network on both, which is non-negotiable for the CT poller; simpler than Fly for a two-process app. `railway.json` + `Dockerfile` are in-repo. | Fly.io — a fine alternative, slightly more config for the same result. Vercel — rejected outright: the worker cannot be serverless. |
| Alerting is a webhook POST (`ALERT_WEBHOOK_URL`), Slack/Discord-compatible | Works with whatever the operator already has and needs no vendor SDK. | Pager vendor SDK — rejected as premature. |

## Things deliberately not built

- LinkedIn scraping, in any form — spec non-goal, and it is the legal exposure the spec names.
- Stripe/billing — spec non-goal; API keys are issued by hand via `scripts/issue-key.ts`.
- Any ML training — spec non-goal; rules + LLM is the v1 scoring layer.
- Marketing pages — spec says do not spend time there.
- UI tests — spec says skip them. Parsers, PSL extraction, parking detection, and scoring rules are
  tested, per §12.
