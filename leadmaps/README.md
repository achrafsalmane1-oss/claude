# LeadMaps

A B2B SaaS built on top of [google-maps-scraper](https://github.com/gosom/google-maps-scraper):
customers sign up, run local-business searches, and download lead lists — on a
metered monthly plan you charge for.

The scraper is the engine. This is everything a business needs around it:
tenants, seats, API credentials, credit metering, plan enforcement, Stripe
subscriptions, a marketing site and a customer dashboard.

```
Visitor → landing / pricing → signup → dashboard search → CSV or REST API
                                  ↓
                            Stripe checkout
                                  ↓
                      plan + monthly lead allowance
                                  ↓
              quota check → scraping engine → metered results
```

## Run it in 60 seconds

```bash
pip install -r requirements.txt
export SECRET_KEY=$(openssl rand -hex 32)
uvicorn app.main:app --reload
```

Open http://localhost:8000. Sign up, run a search, download a CSV. Out of the
box it uses the **mock engine** (deterministic fake results) and **billing is
disabled** (plan changes apply without payment), so the whole product is
walkable with no external dependencies.

### Give yourself an unlimited account

Signing up through the site puts you on the free trial (100 leads). To get an
account with no cap and every feature on:

```bash
python -m app.cli create-admin --email you@example.com
```

It prompts for a password, or generates one if you press enter. Sign in at
`/login` with it. The account lands on the **Internal** plan: no lead ceiling,
100-page searches, email enrichment and API access all on. That plan is
deliberately absent from the pricing page and the plan switcher, so no customer
can select it.

Re-running the command on an existing email promotes that user and resets their
password — that is how you recover a locked-out admin.

```bash
python -m app.cli list-accounts                              # who exists, on what plan
python -m app.cli set-plan --email c@co.com --plan growth    # comp a customer
```

Run it against the same `DATABASE_URL` the app uses.

Two switches turn it into a real business:

| Switch | Development | Production |
|---|---|---|
| `ENGINE_MODE` | `mock` — fake results | `http` — a real scraper deployment |
| `STRIPE_SECRET_KEY` | empty — free plan changes | set — real Stripe checkout |

Just want to click around? [docs/TRY-IT.md](docs/TRY-IT.md).
Ready to deploy for real? [docs/DEPLOY.md](docs/DEPLOY.md).

## What is in the box

**Marketing** — landing page, pricing page with a plan comparison, API docs,
terms and privacy templates, sitemap and robots.

**Accounts** — email/password signup, Argon2 hashes, signed session cookies,
one account (tenant) per signup with an owner seat.

**Metering** — one credit per lead delivered. A search reserves credits up
front from its requested depth so a single deep search cannot overrun the plan,
then the reservation is reconciled to the real row count when the engine
finishes. Results are truncated to what remains, so a plan cap is exact:
the free plan delivers exactly 100 leads, never 140. Failed searches cost
nothing.

**Plans** — defined in one place, [`app/plans.py`](app/plans.py). Pricing page,
quota enforcement and Stripe checkout all read from it, so what you advertise
and what you enforce cannot drift apart.

| Plan | Price | Leads/mo | Seats | Pages/search | API | Email enrichment |
|---|---|---|---|---|---|---|
| Trial | Free | 100 | 1 | 2 | — | — |
| Starter | $49 | 5,000 | 2 | 10 | ✓ | — |
| Growth | $149 | 25,000 | 10 | 25 | ✓ | ✓ |
| Scale | $399 | 100,000 | 50 | 50 | ✓ | ✓ |
| Internal | — | unlimited | 1,000 | 100 | ✓ | ✓ |

The Internal plan is for you and your staff. It is not listed on the pricing
page and cannot be bought — assign it with the CLI above.

**Billing** — Stripe Checkout, the customer billing portal, and webhooks for
the subscription lifecycle (activation, upgrade, downgrade, cancellation,
failed payment). A past-due account is blocked from searching until the card
is fixed.

**Dashboard** — new search with advanced geo targeting, job history, a results
preview, CSV export, API key management, usage meter and plan switching.

**REST API** — `X-API-Key` authenticated endpoints for submitting searches,
polling, listing, CSV download and usage. OpenAPI schema at `/api/openapi.json`,
interactive explorer at `/api/docs`.

## Layout

```
app/
  config.py      settings from the environment
  models.py      Account, User, ApiKey, Job, UsageEvent
  plans.py       the commercial plan catalog — edit this to reprice
  quota.py       credit ledger, reservations, plan enforcement
  engine.py      adapters to the scraper (HTTP) and a mock for dev/tests
  billing.py     Stripe checkout, portal, webhook handling
  services.py    signup, job submission, syncing, CSV export
  security.py    password hashing, sessions, API keys
  cli.py         create-admin, set-plan, list-accounts
  routes/        marketing, auth, dashboard, api_v1, webhooks
  templates/     Jinja2 pages
  static/css/    one hand-written stylesheet, no build step
tests/           97 tests
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Covers auth, quota enforcement and exhaustion, job lifecycle, CSV export,
cross-account isolation, API key auth and revocation, every REST endpoint,
the engine adapter contract (against a mocked HTTP engine), Stripe webhook
handling, and unlimited internal accounts.

## Renaming it

`BRAND_NAME`, `BRAND_TAGLINE` and `SUPPORT_EMAIL` are environment variables and
appear everywhere the product is named. Nothing hardcodes "LeadMaps" except the
default value.

## Licence note

The upstream scraper is licensed by its authors; check its terms before
reselling access to it. This control plane is yours.
