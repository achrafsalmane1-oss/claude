# Instantly → Slack positive-reply bridge

Posts every **positive reply** from Instantly into a Slack channel, with a
**"Write & send reply"** button. Click it, type your reply in Slack, hit Send —
and it goes out through Instantly as a native in-thread email. You never open
Instantly.

```
Positive reply in Instantly
   │  reply_received webhook
   ▼
This service  ──chat.postMessage──▶  #instantly-positive-replies
   ▲                                  (lead + their reply + a Reply button)
   │  click "Reply" → modal text box → Send
   └──────────────  POST /api/v2/emails/reply  ──────────────▶ Instantly
```

## What it needs (the 4 secrets)

| Variable | Where to get it |
| --- | --- |
| `INSTANTLY_API_KEY` | Instantly → Settings → Integrations → API |
| `SLACK_BOT_TOKEN` | Slack app → OAuth & Permissions → Bot User OAuth Token (`xoxb-…`) |
| `SLACK_SIGNING_SECRET` | Slack app → Basic Information → Signing Secret |
| `SLACK_CHANNEL_ID` | Open the channel in Slack → channel name → About → Channel ID |

See `.env.example` for the full list (plus two optional settings).

## Deploy on Railway (recommended)

1. Push this repo to GitHub (already done if you're reading this on GitHub).
2. Go to **railway.app** → **New Project** → **Deploy from GitHub repo** →
   pick this repo.
3. In the service **Settings → Root Directory**, set `instantly-slack-bridge`.
4. In **Variables**, add the four secrets above (+ optionally
   `INSTANTLY_WEBHOOK_SECRET`). Set `FORWARD_ALL_REPLIES=true` for the first
   test, then back to `false`.
5. Deploy. Under **Settings → Networking**, click **Generate Domain**. You now
   have a public URL like `https://your-app.up.railway.app`.

Your two callback URLs are:
- Instantly webhook → `https://your-app.up.railway.app/webhooks/instantly`
- Slack interactivity → `https://your-app.up.railway.app/slack/interactions`

## Slack app setup

1. **api.slack.com/apps** → Create New App → From scratch → pick the workspace.
2. **OAuth & Permissions** → Bot Token Scopes → add `chat:write` → Install to
   Workspace → copy the `xoxb-…` token.
3. **Basic Information** → copy the **Signing Secret**.
4. **Interactivity & Shortcuts** → toggle on → Request URL =
   `https://your-app.up.railway.app/slack/interactions` → Save.
5. In Slack, open the target channel and run `/invite @YourAppName` so the bot
   can post there.

## Instantly webhook setup

In Instantly → **Settings → Integrations → Webhooks** (or via the API), add a
webhook:
- **URL**: `https://your-app.up.railway.app/webhooks/instantly`
- **Event**: `reply_received`
- (optional) custom header `X-Webhook-Secret` = your `INSTANTLY_WEBHOOK_SECRET`

## Tuning "positive only"

Instantly doesn't publish an exhaustive webhook payload schema, so on every
event this service logs the full JSON. After your first real reply, check the
Railway logs and confirm which field carries the interest/sentiment signal;
adjust `POSITIVE_VALUES` / `is_positive()` in `app.py` if needed. Until then,
run with `FORWARD_ALL_REPLIES=true` to validate the end-to-end flow.

## Run locally

```bash
cd instantly-slack-bridge
pip install -r requirements.txt
cp .env.example .env   # fill in the values
python app.py          # serves on http://localhost:3000
```

Use a tunnel (e.g. `ngrok http 3000`) to expose it to Instantly/Slack while
testing locally.
