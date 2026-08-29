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

**Real Google Maps data.** `ENGINE_MODE` defaults to `local`, which runs the
google-maps-scraper CLI once per search. The first search pulls the scraper
Docker image, so it is slower; after that expect roughly a minute per page.

Searches run in the background — the job page refreshes itself until the rows
land.

Requirements: **Docker running**. Check with `docker info`. If you would rather
not use Docker, build the scraper once and point at the binary:

```bash
git clone https://github.com/gosom/google-maps-scraper.git
cd google-maps-scraper && go build -o google-maps-scraper .
export ENGINE_BINARY=$PWD/google-maps-scraper
```

Try:

- Run a search, wait for it to complete, then **Download CSV**
- **API keys** → create one, then:
  ```bash
  curl -X POST http://localhost:8000/api/v1/searches \
    -H "X-API-Key: PASTE_KEY" -H "Content-Type: application/json" \
    -d '{"keyword": "dentists in Manchester", "max_depth": 3}'
  ```
- **Billing** → switch plans (no payment, Stripe is off)
- Sign out and sign up as a normal customer to see the free-trial limits bite

### Use proxies before you scrape at volume

Google rate-limits datacentre IPs hard. One or two searches from a laptop is
fine; a working day of them is not. Set `ENGINE_PROXIES` to a comma-separated
list before you run this for customers:

```ini
ENGINE_PROXIES=http://user:pass@proxy-host:8080,http://user:pass@other:8080
```

Symptoms of being rate-limited: searches that complete with zero rows.

## 2. With Docker

```bash
cd leadmaps
cp .env.example .env          # set SECRET_KEY
docker compose up -d
docker compose exec app python -m app.cli create-admin --email you@example.com
```

Same app on http://localhost:8000, backed by Postgres instead of SQLite.

## 3. At volume: the queued engine

`local` runs one scrape subprocess per search on the same box as the app. That
is fine to launch on. When you need a real queue, retries and workers you can
scale out, deploy the full scraping engine — a separate service with its own
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

Restart. Nothing else changes — the dashboard, CSV export and API all work the
same.

**Never charge anyone while `ENGINE_MODE=mock`.** That mode returns generated
data; it exists for tests and UI work only.

## Troubleshooting

**`command not found: uvicorn`** — the install did not land on the Python you
are running. Use `python -m uvicorn app.main:app --reload`.

**`SECRET_KEY` errors on boot** — it is unset. The app runs with a dev default
if you skip it, but never do that in production.

**Password rejected** — minimum 10 characters.

**"Neither ENGINE_BINARY nor Docker is available"** — start Docker, or set
`ENGINE_BINARY` to a scraper binary.

**Searches complete with zero rows** — usually Google rate-limiting your IP.
Set `ENGINE_PROXIES`. Also check the query returns results in Google Maps by
hand.

**Searches fail mentioning playwright or a browser** — the scraper downloads
Chromium on first run. Give the first search longer, or raise
`ENGINE_JOB_TIMEOUT`.

**Searches are slow** — they are real. Roughly a minute per page of results;
`max_depth: 3` is about three minutes.

**A restart lost a running search** — `local` keeps in-flight scrapes in
memory. Re-run it. `ENGINE_MODE=http` survives restarts.

**"The scraping engine is unavailable"** — `http` mode only: this app cannot
reach `ENGINE_URL`, or `ENGINE_API_KEY` is wrong.
