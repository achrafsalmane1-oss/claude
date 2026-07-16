# Franklin — Campaign Performance Dashboard

A clean, shareable dashboard for a client (Franklin) showing outreach results
from Email Bison. You send Franklin **one link**; it refreshes **once a day**
on its own.

It shows:

- **Total emails sent to date**
- **Emails sent per day** (chart)
- **Total replies** (and replies per day)
- **Reply rate**
- **Campaign names + status**

By design it does **not** expose the API key or internal deliverability
figures — the browser only ever sees the curated numbers in `site/data.js`.

## How it works

```
build.py  ──calls Email Bison API──▶  site/data.js   (curated numbers only)
                                          │
site/index.html  ──reads data.js──▶  the dashboard the client sees
```

`build.py` pulls the numbers, strips everything the client shouldn't see, and
writes `site/data.js`. `site/index.html` is a single self-contained page (no
external libraries, works offline) that renders it. A GitHub Action re-runs
`build.py` every day and publishes the page to GitHub Pages.

## One-time setup (≈3 steps)

1. **Add the API key as a secret.**
   Repo → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `EMAIL_BISON_API_KEY`
   - Value: *(the Email Bison token)*

2. **Turn on GitHub Pages.**
   Repo → **Settings → Pages → Build and deployment → Source: GitHub Actions**

3. **Put the workflow on the default branch (`main`).**
   Scheduled daily runs only fire from `main`, so merge this branch into `main`
   (or ask me to open a pull request). After it's on `main`, go to
   **Actions → “Build & publish Franklin dashboard” → Run workflow** once to
   publish immediately.

Your shareable link then appears under **Settings → Pages** (it looks like
`https://<owner>.github.io/<repo>/`). Send that to Franklin.

> If the repo is private, publishing a Pages site may require a paid GitHub
> plan. The published data contains no secrets and is meant for the client, so
> a dedicated public repo is a fine alternative.

## Run it locally

```bash
pip install -r requirements.txt
cp .env.example .env          # then paste the key into .env
export $(grep -v '^#' .env | xargs)
python build.py               # regenerates site/data.js
# open site/index.html in a browser
```

## What the client sees (and doesn't)

| Shown | Hidden |
|---|---|
| Emails sent (total + per day) | Bounce counts / bounce rate |
| Replies (total + per day) | Unsubscribes |
| Reply rate | Per-step / internal campaign mechanics |
| Campaign names, status, launch date | The API key |

All shown numbers are the real, live figures — the curation is about *which*
metrics appear, never about changing them.

## Configuration

Set as GitHub **Variables** (Settings → Secrets and variables → Actions →
Variables) to override the defaults:

- `EMAIL_BISON_BASE_URL` — defaults to `https://send.breakoutcreatives.com/api`
- `CLIENT_NAME` — defaults to `Franklin`
