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

**Provisioning** (`/api/cron/provision`, hourly) — a resumable state machine
in `src/lib/fulfillment.ts`. Per client: buy an inbox plan → buy ~10 lookalike
sending domains for the client's brand → create SMTP inboxes (≈3/domain) →
connect them to the sending tool with warmup enabled. Days 1–10 are warmup.
On day 11 it generates the campaign copy, creates the campaign (Mon–Fri
schedule, 2,000/day), and flips the account to **ACTIVE**. Each step records
`lastCompletedStep`; a failure records `lastError` and retries next tick.

**Daily top-up** (`/api/cron/topup`, weekdays 06:00 UTC) — keeps every active
campaign fed so it never runs out: source owners in the buy-box → find each
owner's email → verify it → generate a 2–3-word lowercase **niche variant** →
push verified leads into the campaign with `{{firstName}}`, `{{companyName}}`,
`{{niche}}` personalization. Sourcing/enrichment run during warmup too, so the
dashboard is never empty.

Replies flow in through `/api/webhooks/sender` (matched to a prospect by
email), get classified by Claude, and — when interested — notify the customer
in-app and by email. Nothing about mailboxes, domains, warmup, or send volume
is ever exposed in the customer-facing UI.

### Service adapters (mock ↔ real)

| Concern | Env key(s) | Real adapter |
|---|---|---|
| Copywriting + niche variants + reply classification | `ANTHROPIC_API_KEY` | Claude (`claude-opus-4-8`) |
| Lead sourcing | `CLAY_WEBHOOK_URL`, `CLAY_WEBHOOK_SECRET` | Clay (webhook table → `/api/webhooks/clay`) |
| Email finding | `EMAIL_FINDER_API_URL`, `EMAIL_FINDER_API_KEY` | your unlimited-enrichment provider |
| Email verification | `REOON_API_KEY` | Reoon |
| Domains + SMTP inboxes | `WINNER_API_KEY` | Winner (stub — see below) |
| Sending / warmup / campaigns | `INSTANTLY_API_KEY`, `SENDER_WEBHOOK_SECRET` | Instantly v2 |
| Billing | `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID` | Stripe |
| Cron auth | `CRON_SECRET` | Vercel Cron `Authorization: Bearer` |

### Going live — what's ready vs what needs your keys

Ready to switch on by dropping in a key (adapters written against each
provider's documented API — verify field mappings on first live run):
Claude, Clay, Reoon, Instantly, Stripe, and the generic email-finder.

**Winner (inbox/domain platform) needs its API docs.** `WinnerDomainInboxProvider`
is a typed stub — I couldn't find a public API surface for "Winner". Give me
its buy-plan / buy-domain / create-inbox endpoints and auth scheme and it
becomes ~4 HTTP calls with no other code change. Until then the mock provisions
inbox records so warmup/campaign creation still run.

**Clay caveat.** Clay has no public API to create a folder/table per client, so
per-client separation lives in this app's DB (every row carries `clientId`),
not in Clay folders. One pre-built Clay workbook with a webhook-source table
receives sourcing requests and POSTs enriched owners back to `/api/webhooks/clay`.

**Secrets.** SMTP passwords are stored as references (`smtpPasswordRef`), not
raw secrets — wire a real vault (e.g. the platform's secret store) before
production.

### Driving the pipeline locally

```bash
# after `npm run setup` and `npm run dev`
curl "localhost:3000/api/cron/provision?force=1"   # DEMO_MODE: skip the day-11 wait
curl "localhost:3000/api/cron/topup?force=1"        # DEMO_MODE: run on a weekend too
```

`force=1` only works when `DEMO_MODE=true`. In production the crons authenticate
with `CRON_SECRET` and respect the real day-11 and weekday gates.
