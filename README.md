# Colddrops — Permission-based outbound

Colddrops is a ringless voicemail platform: it delivers a personal, personalized voice
message straight into a prospect's voicemail inbox — **no ring, no interruption**.
Positioning: *cold calling is the enemy; permission-based outbound is the future.*

ICP: B2B sales teams, founders selling their own product, real estate agents — anyone
doing outbound.

## Status

| Piece | State |
|---|---|
| Landing page (`web/index.html`) | ✅ Premium light redesign, live |
| Lead data (Moltsets) | ✅ Integration verified end-to-end |
| Voice (ElevenLabs) | ⏳ Planned — needs API key |
| Delivery (Drop Cowboy → Twilio BYOC) | ⏳ Planned — needs account |
| Live demo callback (Vapi / Twilio) | ⏳ Planned |
| Auth + billing (Stripe) + dashboard | ⏳ Planned |
| Sending engine (queue) + compliance (DNC/TCPA) | ⏳ Planned |

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

The send pipeline (script merge → personalized voice render → RVM drop →
delivery webhook, with DNC/opt-out suppression) runs end-to-end in **dry-run
mode** out of the box — placeholder audio, simulated delivery. Set
ELEVENLABS_API_KEY + DROPCOWBOY_TEAM_ID + DROPCOWBOY_SECRET (see .env.example)
and the same pipeline goes live. Tests: `python3 -m pytest tests/`.

## Compliance

Ringless voicemail is regulated (U.S. TCPA and equivalents abroad). Do not launch
sending without DNC scrubbing, consent handling, and a legal review.
Secrets (API keys/tokens) live in environment variables only — never in the repo.
