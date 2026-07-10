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
