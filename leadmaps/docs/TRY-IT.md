# Trying the tool

Three ways, fastest first. All of them run on your own machine or server — there
is no hosted instance yet, because you have not deployed one.

## 1. On your laptop (about a minute)

Needs Python 3.11+.

```bash
git clone https://github.com/achrafsalmane1-oss/claude.git
cd claude/leadmaps
git checkout claude/maps-scraper-saas-f2dum2

pip install -r requirements.txt

export SECRET_KEY=$(openssl rand -hex 32)
python -m app.cli create-admin --email you@example.com
uvicorn app.main:app --reload
```

Open http://localhost:8000, click **Sign in**, use the email and password you
just set. You are on the Internal plan: no lead cap, every feature on.

On Windows PowerShell, swap the export line for:

```powershell
$env:SECRET_KEY = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Max 256) })
```

### What you are looking at

The results are **fake**. `ENGINE_MODE` defaults to `mock`, which generates
plausible, deterministic businesses so you can walk the whole product — search,
job history, CSV export, API keys, billing — without deploying a scraper. The
shape of the data is real; the businesses are not.

Try:

- Run a search, then **Download CSV**
- **API keys** → create one, then:
  ```bash
  curl -X POST http://localhost:8000/api/v1/searches \
    -H "X-API-Key: PASTE_KEY" -H "Content-Type: application/json" \
    -d '{"keyword": "dentists in Manchester", "max_depth": 3}'
  ```
- **Billing** → switch plans (no payment, Stripe is off)
- Sign out and sign up as a normal customer to see the free-trial limits bite

## 2. With Docker

```bash
cd leadmaps
cp .env.example .env          # set SECRET_KEY
docker compose up -d
docker compose exec app python -m app.cli create-admin --email you@example.com
```

Same app on http://localhost:8000, backed by Postgres instead of SQLite.

## 3. With real scraped data

The mock engine is for evaluating the product. For real Google Maps data you
need the scraping engine deployed — that is a separate service with its own
provisioning wizard, workers and database. Full steps in
[DEPLOY.md](DEPLOY.md). Short version:

```bash
curl -fsSL https://raw.githubusercontent.com/gosom/google-maps-scraper/main/PROVISION | sh
```

Then create an API key in the engine's admin UI and point this app at it:

```ini
ENGINE_MODE=http
ENGINE_URL=https://your-engine
ENGINE_API_KEY=...
```

Restart, and searches hit real Google Maps. Nothing else changes — the
dashboard, CSV export and API all work the same.

**Do not charge anyone while `ENGINE_MODE=mock`.** You would be selling
generated data.

## Troubleshooting

**`command not found: uvicorn`** — the install did not land on the Python you
are running. Use `python -m uvicorn app.main:app --reload`.

**`SECRET_KEY` errors on boot** — it is unset. The app runs with a dev default
if you skip it, but never do that in production.

**Password rejected** — minimum 10 characters.

**"The scraping engine is unavailable"** — only appears with
`ENGINE_MODE=http`. This app cannot reach `ENGINE_URL`, or `ENGINE_API_KEY` is
wrong.

**Searches sit at "queued" forever** — the engine has no worker running.
Provision one from its admin UI.
