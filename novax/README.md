# novaX

Detects newly registered domains within hours of registration, filters out the ~99% that are
garbage, enriches the survivors into a usable company record, and delivers them as an API, CSV,
webhook or daily digest.

**The raw feed of new domains is a commodity. The product is the filter.** Roughly 250,000–400,000
new domains appear per day; almost all are parked pages, dropcatches, typosquats, spam
infrastructure and SEO churn. novaX exists to surface the few hundred that are a real company being
born, and to tell you *why* each one surfaced.

- `SPEC.md` — the original product spec
- `PLAN.md` — build plan and file tree
- `DECISIONS.md` — every stack choice, its reasoning, and the alternative rejected
- `PHASE-REPORTS.md` — what was built, skipped, and remains uncertain, per phase

---

## Local setup from a clean clone

Verified on Node 22 and PostgreSQL 16.

### 1. Prerequisites

- Node 22+
- A PostgreSQL 15+ database (local, Neon, or Supabase)

```bash
git clone <this repo>
cd novax
npm install
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`. Only two values actually matter to get started:

```bash
DATABASE_URL=postgres://user@localhost:5432/novax
BETTER_AUTH_SECRET=$(openssl rand -hex 32)   # required in production
```

Everything else has a working default. `ANTHROPIC_API_KEY` and `RESEND_API_KEY` unlock the LLM
classifier and digest emails respectively; the pipeline runs without them.

<details>
<summary>Starting a throwaway Postgres locally</summary>

```bash
initdb -D /tmp/pgdata-novax -U novax --auth=trust
pg_ctl -D /tmp/pgdata-novax -o "-p 5433" -l /tmp/pg.log start
createdb -h 127.0.0.1 -p 5433 -U novax novax
# DATABASE_URL=postgres://novax@127.0.0.1:5433/novax
```
</details>

### 3. Create the schema

```bash
npm run db:migrate
```

### 4. Get real data in

```bash
# Download and ingest one day of the newly-registered-domain feed.
# ~400k domains, takes about a minute. Safe to re-run: it is idempotent.
npm run ingest:nrd -- --date=2026-08-13

# Optional: watch the Certificate Transparency poller for 60 seconds.
npm run ingest:ct -- --seconds=60
```

### 5. Run the pipeline

```bash
# Enrich a batch: DNS -> MX -> HTTP probe -> RDAP, cheap gates first.
npm run enrich -- --batch=300

# Score them. --rules-only skips the LLM entirely (free).
npm run score:run -- --rules-only --limit=500
```

### 6. Start the app

```bash
npm run dev       # web app + API on http://localhost:3000
npm run worker    # in another terminal: CT poller + queued jobs + schedules
```

Open <http://localhost:3000>, create an account, and you are looking at scored domains.

### 7. Issue an API key

```bash
# The account must exist first — sign up at /login, then:
npm run issue-key -- --name="Clay table" --email=you@example.com
```

---

## Using the API

The response is deliberately **flat** — one object per domain, every value a scalar, stable
`snake_case` keys, no nesting — so it drops straight into a Clay HTTP API column with each key
becoming a spreadsheet column.

```bash
curl -H "X-API-Key: nvx_live_..." \
  "http://localhost:3000/api/v1/domains?min_score=70&days=1&limit=100"
```

```jsonc
{
  "data": [
    {
      "domain": "northwindlogistics.com",
      "score": 84,
      "tier": "hot",
      "reason": "Specific freight-forwarding offer with named trade lanes. Signals: business email configured on Google Workspace; 1,840 characters of page content; site built with webflow; registered 2 days ago.",
      "company_name": "Northwind Logistics",
      "category": "logistics",
      "stage": "just_launched",
      "country": "US",
      "mx_provider": "Google Workspace",
      "has_business_email": true,
      "tech_list": "webflow, stripe",
      "registration_date": "2026-08-15T00:00:00.000Z",
      "registration_date_source": "rdap"
      // ...
    }
  ],
  "count": 1,
  "next_cursor": "NzQ6MTMx"
}
```

### Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/domains` | Filterable, keyset-paginated list |
| `GET /api/v1/domains/:domain` | One domain; `?trail=1` adds the full enrichment history |
| `GET /api/v1/export` | Same filters, CSV response |
| `GET`/`POST /api/v1/searches` | Saved filter sets, optionally with a daily digest |
| `GET`/`POST /api/v1/webhooks` | Register a URL to receive new matches |
| `GET /api/health` | Operational metrics; 503 when down |
| `POST /api/opt-out` | Public, unauthenticated domain-owner opt-out |

### Filters

`from`, `to`, `days`, `registered_after`, `registered_before`, `tld`, `country`, `mx_provider`,
`category`, `tech`, `registrar`, `tier`, `source`, `min_score`, `max_score`, `min_confidence`,
`has_business_email`, `is_real_business`, `q`, `limit`, `cursor`.

Comma-separate any categorical filter for an OR: `?tld=com,io&tech=shopify,webflow`.

### Auth and limits

Send the key as `X-API-Key: nvx_live_...` or `Authorization: Bearer nvx_live_...`. Every response
carries `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset`; a 429 adds
`Retry-After`. Keys are stored only as a SHA-256 hash and cannot be recovered.

### Webhooks

Each delivery carries `X-Novax-Signature: sha256=<hmac>` and `X-Novax-Timestamp`. Verify by
recomputing HMAC-SHA256 over `"<timestamp>.<raw body>"` with your signing secret and comparing in
constant time. Reject anything older than five minutes.

---

## How the filter works

```
    250k-400k domains/day
              │
   ┌──────────▼──────────┐
   │  DNS resolve        │  no A and no MX -> 72h requeue, stop
   │  (batched, free)    │  measured: kills ~43%
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │  MX classification  │  Google Workspace / M365 == a human configured
   │                     │  business email. Highest-signal cheap filter.
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │  HTTP probe         │  robots-respecting; parking/placeholder detection
   │  (512KB, 8s cap)    │  measured: ~40% serve an empty or placeholder page
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │  RDAP               │  registrar + creation date; redaction expected
   │  (rate-limited)     │  and never circumvented
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │  Rules layer        │  parked / blocked TLD / typosquat / random name /
   │  (deterministic)    │  no-MX-no-site / dead site. Free.
   └──────────┬──────────┘
              │  survivors only
   ┌──────────▼──────────┐
   │  LLM classifier     │  Batch API, JSON-schema output, cached prefix
   └──────────┬──────────┘
              │
      composite 0-100 score + tier + a reason you can read
```

Measured over 300 real domains from the 2026-08-13 feed: DNS killed 43%, 11% of survivors were
unreachable, 2% outright parked, 39% served an empty or placeholder page. Enrichment cost about
**15 micro-USD per domain** — 0.0015 cents — against a 200 micro-USD budget.

---

## Evaluation

Precision is the entire product, so scoring changes are measured, not eyeballed.

```bash
npm run eval -- --rules-only     # free, instant; run on every change
npm run eval                     # includes the classifier
npm run eval -- --verbose        # lists every misclassified domain
```

`eval/labels.csv` holds 380 domains sampled from a real feed day and hand-labelled against their
actual enrichment data. The harness reports precision and recall at each delivery threshold and
names every **false kill** — a real business the rules layer silently dropped, which is the
expensive error because nobody ever finds out.

Build a new labelled set:

```bash
npm run sample -- --n=400 --for-eval > eval/labels.csv   # then fill in the label column
```

---

## Operations

```bash
npm run sample -- --n=50                                  # eyeball quality by hand
npm run backfill -- --from=2026-08-10 --to=2026-08-13     # re-enrich a date range
npm run backfill -- --from=2026-08-10 --stage=score       # re-score only (free)
npm run digest                                            # send digests due now
```

`GET /api/health` reports seconds since the last CT event, the last successful feed download, queue
depth per job type, and the enrichment failure rate. It returns 503 when the pipeline is down, so a
plain status-code monitor works. The worker also POSTs alerts to `ALERT_WEBHOOK_URL` (Slack and
Discord compatible) when the CT stream goes silent past its threshold or the daily feed fails,
deduplicated so an hour-long outage is one message.

---

## Deployment

Two Railway services from one repo and one image, so web and worker can never drift:

| Service | Start command | Config |
|---|---|---|
| web | `npm run db:migrate && npm run start` | `railway.json` |
| worker | `npm run worker` | `railway.worker.json` |

The worker **must not** be serverless — it holds long-lived connections to CT logs and runs the
schedule. Managed Postgres (Neon) is assumed. Fly.io works identically.

---

## Compliance

This product reports on domains, which can be connected to identifiable people. That is treated as
a design constraint, not an afterthought:

- **Public opt-out** at `/opt-out`. The owner proves control with a DNS TXT record, and the domain
  is then suppressed from every output path, permanently. Enforcement lives in exactly one place
  (`src/compliance/suppression.ts`) because a compliance control with two code paths has one code
  path that is wrong.
- **Redacted RDAP data is dropped at parse time** and never persisted. No attempt is made to
  circumvent redaction. In practice registrant contact data is redacted essentially always, and
  nothing in the pipeline depends on it.
- **Provenance for every field group**: each record carries the source and the timestamp of every
  DNS, HTTP, RDAP and scoring observation, visible in the dashboard and via `?trail=1`.
- **robots.txt is respected** on every probe, with an identifying User-Agent carrying a contact URL.
  When a site disallows us, no page content is stored at all.
- **Company-level signal only.** No personal contact data is collected or resold.

---

## Tests

```bash
npm test        # 173 tests: parsers, PSL apex extraction, parking detection, scoring rules, API
npm run typecheck
```

Per the spec, tests cover the parsers, the Public Suffix List apex extraction, the parking
detector, the scoring rules and the API contract. UI is not tested. The CT fixtures are real
`leaf_input` values captured from live Google CT logs, covering both `x509_entry` and
`precert_entry` shapes.
