# Colddrops — Permission-based outbound

Colddrops is a ringless voicemail platform: it delivers a personal, personalized voice
message straight into a prospect's voicemail inbox — **no ring, no interruption**.
Positioning: *cold calling is the enemy; permission-based outbound is the future.*

ICP: B2B sales teams, founders selling their own product, real estate agents — anyone
doing outbound.

## Deploy it

The app runs at **$0** out of the box — SMS shows the verification code in-app,
voice uses free gTTS, delivery is dry-run. Add keys later to go live. The same
Docker image runs on any host; the config files are included.

### Fly.io — recommended for long-term (durable data, ~$0 idle → a few $/mo)

Fly runs the Docker image with a **persistent volume**, so the SQLite database
survives redeploys and restarts — no database migration, durable from day one.
Uses [`fly.toml`](fly.toml).

```bash
# one-time: install flyctl -> https://fly.io/docs/flyctl/install/
fly auth login
fly launch --copy-config --no-deploy        # pick a unique app name + region
fly volume create colddrops_data --size 1   # 1 GB durable disk for SQLite
fly deploy
fly open                                     # your live URL, e.g. https://<app>.fly.dev
```

Turn on live features later without redeploying code:

```bash
fly secrets set TELNYX_API_KEY=... TELNYX_SMS_FROM=+1... \
                ELEVENLABS_API_KEY=... MOLTSETS_API_KEY=...
```

It scales to zero when idle (first hit wakes it in ~1s), so you pay only for
what you use. Bump `[[vm]]` / add machines in `fly.toml` when traffic grows.

### Railway — easiest, no CLI (GitHub auto-deploy)

1. **[railway.app](https://railway.app)** → sign in with GitHub.
2. **New Project → Deploy from GitHub repo** → pick this repo + the
   `claude/ai-cold-caller-voicemail-rvspgp` branch. Railway auto-detects the
   Dockerfile and deploys.
3. In the service: **add a Volume** mounted at `/data`, then set an env var
   `COLDDROPS_DB=/data/colddrops.db` (durable storage).
4. **Settings → Networking → Generate Domain** for your public URL.

### Render — free tier for a quick look (no card, ephemeral data)

**New → Blueprint** on [render.com](https://render.com), pick this repo + branch;
it reads [`render.yaml`](render.yaml). Free web tier sleeps when idle and has no
disk, so the DB resets on redeploy — fine for a first look. For durable data on
Render, upgrade to Starter + add a disk and set `COLDDROPS_DB=/var/data/colddrops.db`.

### Any Docker host / VPS

```bash
docker build -t colddrops . && docker run -p 8000:8000 -v colddrops_data:/data \
  -e COLDDROPS_DB=/data/colddrops.db colddrops
```

> Scaling note: SQLite-on-a-volume is great for a single instance (comfortably
> thousands of users). If you later run multiple instances, move `COLDDROPS_DB`
> to managed Postgres — that's the only piece that would need a data-layer change.

## Status

| Piece | State |
|---|---|
| Landing page (`web/index.html`) | ✅ Premium light redesign, live |
| Login → phone → SMS → onboarding → dashboard | ✅ End-to-end, $0 dev mode (no paid number needed) |
| Lead data (Moltsets) | ✅ Integration verified end-to-end |
| Voice | ✅ ElevenLabs (paid) → gTTS (free) → chime fallback |
| Delivery (Telnyx BYOC + AMD) | ✅ Live when keyed, else dry-run |
| SMS verification (Telnyx) | ✅ Live when keyed, else dev code shown in-app |
| Auth + billing (Stripe) + dashboard | ✅ Stub billing works keyless; dashboard live |
| Sending engine (queue) + compliance (DNC/TCPA) | ✅ Metered send, suppression list, quiet hours |

## Architecture (planned)

```
Landing (web/)  ──►  App (auth, dashboard, campaigns)
                        │
                        ├─ Moltsets      → search people + carrier-verified mobiles
                        ├─ ElevenLabs    → personalized natural-voice audio per contact
                        ├─ Drop Cowboy   → ringless voicemail delivery (Twilio BYOC at scale)
                        ├─ Stripe        → subscriptions (Starter/Growth/Scale)
                        └─ Queue         → batch send, retries, delivery webhooks
```

## Landing page

`web/index.html` — a self-contained static page (no build step). Open it directly or
serve the `web/` folder:

```bash
python3 -m http.server 8000 --directory web   # http://localhost:8000
```

Design language: light/airy, editorial serif display type, near-black pill CTAs, a live
voice orb, and a live-demo module. Copy centers on permission-based outbound.

## Pricing (drops per month, not minutes)

| Plan | Drops/mo | Monthly |
|---|---|---|
| Starter | 1,000 | $90 |
| Growth | 5,000 | $290 |
| Scale | 15,000 | $690 |

Annual = 2 months free.


## Run it

```bash
pip install -r requirements.txt
MOLTSETS_API_KEY=ms_xxx uvicorn server.main:app --reload
# open http://localhost:8000  (landing) and /app.html (workspace)
```

The Lead finder in the app goes live automatically when served by this server.
API: POST /api/leads/search · /api/leads/mobiles · /api/script/preview ·
/api/campaigns (+/contacts, /send, detail) · /api/suppressions ·
/api/webhooks/dropcowboy · GET /api/health.

### Voice + delivery are pluggable

**Voice** (`VOICE_BACKEND=auto`): ElevenLabs when a paid key is present, else
free **gTTS** (real speech, $0), else an offline chime. Fallback is automatic —
a paywall or outage never breaks a send.

**Delivery** (`DELIVERY_BACKEND=auto`): self-operated **Telnyx** Call Control
(dial + answering-machine detection → play the drop into voicemail; we own
routing, caller-ID and cost — no reseller), else **dry_run** (simulated).

The full pipeline — script merge → personalized voice render → drop →
delivery/AMD webhook, with DNC/opt-out suppression — runs end-to-end today in
dry-run + free-voice mode. Add a paid ElevenLabs key and/or Telnyx creds
(see .env.example) to go live, same code path. Tests: `python3 -m pytest tests/`.


## Accounts & plans

Multi-tenant: every user belongs to a **workspace**; all campaigns, contacts,
drops and suppressions are scoped to it. Sign up / sign in at `/login.html`.
Auth is bearer-token (`POST /api/auth/signup|login`, `GET /api/auth/me`).

Plans meter **drops per calendar month** and the cap is enforced at send time:
Starter 1,000 · Growth 5,000 · Scale 15,000 (`GET /api/usage`). Stripe will map
to these plans later — the metering is already here.

Export a campaign's contacts: `GET /api/campaigns/{id}/contacts.csv`.

## Compliance

Ringless voicemail is regulated (U.S. TCPA and equivalents abroad). Do not launch
sending without DNC scrubbing, consent handling, and a legal review.
Secrets (API keys/tokens) live in environment variables only — never in the repo.
