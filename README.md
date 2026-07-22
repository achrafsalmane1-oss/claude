# Colddrops — Permission-based outbound

Colddrops is a ringless voicemail platform: it delivers a personal, personalized voice
message straight into a prospect's voicemail inbox — **no ring, no interruption**.
Positioning: *cold calling is the enemy; permission-based outbound is the future.*

ICP: B2B sales teams, founders selling their own product, real estate agents — anyone
doing outbound.

## Deploy it (free, ~5 minutes, no credit card)

The app runs at **$0** out of the box — SMS shows the verification code in-app,
voice uses free gTTS, delivery is dry-run. Add keys later to go live.

**Render (recommended):**

1. Go to **[render.com](https://render.com)** and sign up with GitHub (free).
2. **New → Blueprint**, pick this repo, and set the branch to
   `claude/ai-cold-caller-voicemail-rvspgp` (or `main` if merged).
   Render reads [`render.yaml`](render.yaml) and provisions everything.
3. Click **Apply**. In ~3–5 min you get a public URL like
   `https://colddrops.onrender.com` — open `/login.html` and click around.
4. (Optional) set `PUBLIC_BASE_URL` to that URL in the service's Environment tab.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

The free tier spins down when idle (first hit after a pause takes ~30–50s) and
has no persistent disk, so the SQLite DB resets on redeploy/spin-down — fine for
demoing and first clicks. For real customer data, put `COLDDROPS_DB` on a paid
disk or move to Postgres.

**Any Docker host** works too (Fly.io, Railway, a VPS, Hugging Face Spaces):
`docker build -t colddrops . && docker run -p 8000:8000 colddrops`.

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
