# Deploying for real

Two systems: the **scraping engine** (Go, does the work) and this **control
plane** (Python, sells the work). Deploy the engine first.

## 1. Deploy the scraping engine

The engine is [google-maps-scraper](https://github.com/gosom/google-maps-scraper)
in SaaS mode. It ships a provisioning wizard that creates its database, runs its
migrations, deploys workers and creates an admin user — do not skip it and hand-roll
a container, because `serve` alone does not run migrations.

```bash
curl -fsSL https://raw.githubusercontent.com/gosom/google-maps-scraper/main/PROVISION | sh
```

The wizard walks through Docker image setup, cloud provider (VPS, DigitalOcean
or Hetzner), database creation, and admin user creation. State is saved to
`~/.gmapssaas/` so it can resume.

To update it later:

```bash
curl -fsSL https://raw.githubusercontent.com/gosom/google-maps-scraper/main/PROVISION | sh -s update
```

Then, in the engine's admin UI at `https://your-engine/admin`:

1. Sign in and set up 2FA.
2. Go to **API keys** and create one. This is the key *this app* uses to talk to
   the engine — it is not a customer key.
3. Go to **Workers** and provision at least one worker, or nothing will scrape.

The engine's own image is `ghcr.io/gosom/google-maps-scraper-saas`; the wizard
pulls it for you.

### Sizing

Scraping is browser work and it is the expensive part. One worker handles one
job at a time. Watch the queue depth in the engine's admin UI and add workers
before your `MAX_CONCURRENT_JOBS` ceiling starts backing customers up.

## 2. Deploy this control plane

```bash
cp .env.example .env
```

Fill in, at minimum:

```ini
SECRET_KEY=<openssl rand -hex 32>
PUBLIC_URL=https://yourdomain.com
DATABASE_URL=postgresql+psycopg://leadmaps:...@postgres:5432/leadmaps

ENGINE_MODE=http
ENGINE_URL=https://your-engine
ENGINE_API_KEY=<the key you made in step 1>
```

Then:

```bash
docker compose up -d
```

Put it behind a TLS terminator (Caddy, nginx, or your platform's load
balancer). `PUBLIC_URL` must be the `https://` address — session cookies are
marked `Secure` when it is, and Stripe redirect URLs are built from it.

Tables are created on boot. There is no separate migration step.

### Sanity check before you take money

```bash
curl https://yourdomain.com/healthz          # -> ok
```

Then sign up as yourself, run a real search, and confirm rows come back. If the
dashboard says the engine is unavailable, this app cannot reach `ENGINE_URL` or
`ENGINE_API_KEY` is wrong.

## 3. Turn on billing

In the Stripe dashboard:

1. Create a **Product** for each paid plan, each with a **recurring monthly
   price** matching `app/plans.py` ($49, $149, $399).
2. Copy the three price ids (`price_...`).
3. Create a webhook endpoint pointing at `https://yourdomain.com/webhooks/stripe`,
   subscribed to:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Copy the webhook signing secret.
5. Enable the **customer billing portal** under Settings → Billing.

Then set:

```ini
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICES=starter=price_xxx,growth=price_yyy,scale=price_zzz
```

Restart. The billing page stops saying "Stripe is not configured" and the plan
buttons now open a real checkout.

Test the whole loop with Stripe test keys first:

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
```

Pay with `4242 4242 4242 4242`, confirm the plan flips in the dashboard, then
cancel from the portal and confirm it drops back to Trial.

## 4. Before you take real payments

- [ ] `SECRET_KEY` is random and not in version control
- [ ] Postgres, not SQLite
- [ ] Automated database backups
- [ ] TLS, with `PUBLIC_URL` set to the https address
- [ ] A lawyer has read `/terms` and `/privacy` — the shipped text is a template
- [ ] Stripe webhook is delivering (check the Stripe dashboard's event log)
- [ ] A real search returns real rows
- [ ] At least one engine worker is running
- [ ] You have run the full loop yourself with a test card

## Changing plans and prices

Edit [`app/plans.py`](../app/plans.py) and update `STRIPE_PRICES` to match.
The pricing page, quota enforcement and checkout all read that one file.

Existing subscribers keep the Stripe price they signed up on until they change
plans — Stripe, not this app, is the source of truth for what someone pays.
