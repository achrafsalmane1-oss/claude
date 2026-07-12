# HavenX

Self-serve deal-origination platform for acquisition buyers (search funds,
independent sponsors, micro-PE, buy-side M&A boutiques). HavenX runs
multi-channel outreach in the customer's name and delivers interested owner
introductions into a live dashboard.

Built with Next.js (App Router) + TypeScript, Tailwind, Prisma + Postgres,
Stripe, and magic-link auth. Deployable to Vercel.

## Quick start

```bash
npm install
cp .env.example .env          # point DATABASE_URL at a Postgres instance
npm run setup                 # prisma generate + db push + seed demo data
npm run dev
```

Open http://localhost:3000 and click **View live demo** to enter the seeded
demo account (`demo@havenx.app`): a 25-day-old pipeline with 187 sourced
owners, a full funnel, and 6 interested introductions.

Or run the real flow: **Start now → checkout (mock, no card) → buy-box
intake → dashboard** (day 1 of warmup, sourcing already populated).

## Architecture

```
src/
  app/                    # marketing site, checkout, onboarding, dashboard
    api/
      checkout/activate   # mock-billing activation (dev)
      webhooks/stripe     # Stripe activation + first-cycle invoice (prod)
      replies             # inbound owner-reply seam (classify → notify)
      auth/…              # magic-link verify, logout, demo login
  services/               # ALL external dependencies live behind interfaces
    types.ts              #   OutreachService, EnrichmentService,
    index.ts              #   ReplyClassificationService, BillingService,
    …                     #   NotificationService — mock impls wired here
  lib/                    # prisma client, sessions, account activation
  components/             # marketing + dashboard UI
prisma/
  schema.prisma           # Postgres schema (Prisma 7, driver adapter)
  seed.ts                 # realistic demo pipeline
```

**Service seams.** The UI and server actions import services only from
`src/services/index.ts`. Swapping a mock for a real provider (Instantly /
Salesforge for outreach, Clay for enrichment, an LLM for reply
classification, Resend for email) means implementing the interface and
changing one line of wiring — no UI changes.

**Product language rule.** The customer-facing app never exposes channel
mechanics (mailboxes, warmup status, deliverability, sending volume).
Outreach is described only as "multi-channel outreach conducted in your
name"; the customer sees a pipeline and interested introductions.

## Billing model

Single plan, **$499/month**:

- $499 charged immediately (invoice one)
- days 1–10: setup + infrastructure warmup (sourcing/enrichment already live)
- day 11: outreach begins
- first billing cycle runs **40 days**, then renews every 30 days

With no `STRIPE_SECRET_KEY`, the mock billing service simulates the charge
and drops the user straight into onboarding. With Stripe configured, checkout
creates a $499/mo subscription with a 40-day trial (so recurring billing
starts at day 40) and the webhook bills invoice one immediately on
`checkout.session.completed`. Set `STRIPE_PRICE_ID` to the recurring price
and point a webhook at `/api/webhooks/stripe`.

## Environment

See `.env.example`. Notable flags:

- `DEMO_MODE=true` — enables the one-click demo login on the homepage
- `RESEND_API_KEY` — unset: emails are logged to the console
- `REPLY_WEBHOOK_SECRET` — protects `POST /api/replies` (always set in prod)

## Simulating an owner reply

```bash
curl -X POST http://localhost:3000/api/replies \
  -H "Content-Type: application/json" \
  -d '{"prospectId":"<id>","replyText":"Yes, I would take that conversation."}'
```

The reply is classified (interested / not now / not interested), the pipeline
updates, and an interested reply triggers the in-app + email notification.

## Fulfillment pipeline (self-serve, no manual work)

Once a client pays and defines their buy-box, two cron jobs run the entire
outreach operation with zero human involvement. Every step sits behind a
service interface with a working **mock**, so the full pipeline runs
end-to-end today; each real provider activates the moment its env key is set
(`src/services/index.ts`).

### The master switch: `FULFILLMENT_LIVE`

Unset/`false` (default): the **entire** outbound backend — sourcing,
enrichment, verification, copywriting, classification, inbox provisioning, and
sending — runs on free, synchronous **mocks**. No credits burned, no domains
bought, no real email sent; the app and the seeded demo work fully. Set it to
`true` (with the keys present) to run real clients. It flips everything at once,
so there's no half-live state.

### The four crons (`vercel.json`)

- **Provisioning** (`/api/cron/provision`, hourly) — resumable state machine in
  `src/lib/fulfillment.ts`. Per client: pick ~10 available lookalike domains for
  the client's brand → purchase/register them → create SMTP inboxes (≈3/domain)
  → enable native warmup. Days 1–10 warm up. On day 11 it generates the campaign
  copy and flips the account to **ACTIVE**. Each step records `lastCompletedStep`;
  a failure records `lastError` and retries next tick.
- **Enrichment top-up** (`/api/cron/topup`, weekdays) — keeps a ~2-day backlog of
  send-ready owners: source in the buy-box → find email → verify → generate the
  2–3-word lowercase **niche variant**. Bounded per run.
- **Send dispatch** (`/api/cron/send`, weekday business hours, hourly) — sends
  each active client's outreach in their name up to 2,000/day, paced across runs
  and rotated across inboxes, filling `{{firstName}}` / `{{companyName}}` /
  `{{niche}}`. Weekends skipped.
- **Reply poll** (`/api/cron/replies`, every 15 min) — pulls inbound mail from
  the provider account-wide, dedupes by message id, matches each reply to a
  prospect by sender email, classifies it, and notifies the customer on
  interest. Nothing about mailboxes/domains/warmup/volume is ever exposed in the
  customer UI.

### Service adapters (mock ↔ real), all gated by `FULFILLMENT_LIVE`

| Concern | Env key(s) | Real adapter | Status |
|---|---|---|---|
| Copywriting + niche variants + reply classification | `ANTHROPIC_API_KEY` | Claude (`claude-opus-4-8`) | wired; key needs credits |
| Lead sourcing | `CLAY_WEBHOOK_URL` | Clay (webhook table → `/api/webhooks/clay`) | wired |
| Email finding | `MOLTSETS_API_KEY` | Moltsets (LinkedIn→email, name+domain→email) | **verified live** |
| Email verification | `ORBISEARCH_API_KEY` | Orbisearch | **verified live** |
| Domains + inboxes + warmup + send + inbox polling | `WINNR_API_KEY` | Winnr | **auth+read verified live**; writes wired (unrun — they spend money/send) |
| Billing | `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID` | Stripe | wired; awaiting keys |
| Cron auth | `CRON_SECRET` | Vercel Cron `Authorization: Bearer` | wired |

**Winnr is both the inbox infra and the transport** — it hosts domains/inboxes,
warms them natively, sends, and receives. This app is the sequencer + reply
poller (Pulsevibe/Instantly aren't needed). One Winnr account holds every
client's domains; per-client separation lives in this app's DB.

**Clay note:** Clay has no public API to create a folder per client, so
per-client separation is in our DB (every row carries `clientId`), not Clay
folders. One pre-built Clay workbook with a webhook-source table receives
sourcing requests and POSTs enriched owners back to `/api/webhooks/clay`.

### Driving the pipeline locally (staging, all mocks)

```bash
# after `npm run setup` and `npm run dev`  (FULFILLMENT_LIVE unset)
curl "localhost:3000/api/cron/provision?force=1"  # DEMO_MODE: skip the day-11 wait
curl "localhost:3000/api/cron/topup?force=1"       # DEMO_MODE: run on a weekend too
curl "localhost:3000/api/cron/send?force=1"
curl "localhost:3000/api/cron/replies"
```

`force=1` only works when `DEMO_MODE=true`. In production the crons authenticate
with `CRON_SECRET` and respect the real day-11 and weekday/business-hour gates.
