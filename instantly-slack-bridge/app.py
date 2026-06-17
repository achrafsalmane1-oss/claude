#!/usr/bin/env python3
"""
Instantly -> Slack positive-reply bridge
========================================
A small always-on web service that connects Instantly.ai to Slack so that:

  1. When a positive reply lands in Instantly, Instantly fires a webhook to
     this service, which posts a rich message into a Slack channel showing
     the lead, the original context, and the prospect's reply.
  2. Each Slack message has a "Write & send reply" button. Clicking it opens
     a text box (a Slack modal). Whatever you type is sent back through the
     Instantly API as a native in-thread email reply -- without ever opening
     Instantly.

Two endpoints:
  POST /webhooks/instantly   <- Instantly calls this on each reply event
  POST /slack/interactions   <- Slack calls this on button click / modal submit

Configuration is via environment variables (see .env.example).

Run locally:   python app.py
Run on Railway: gunicorn app:app   (see Procfile)
"""

import hashlib
import hmac
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify, abort

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
INSTANTLY_API_KEY = os.getenv("INSTANTLY_API_KEY", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")

# Optional shared secret. Set the same value as a custom header / query param
# on the Instantly webhook so random internet traffic can't post fake replies.
INSTANTLY_WEBHOOK_SECRET = os.getenv("INSTANTLY_WEBHOOK_SECRET", "")

# While testing, set FORWARD_ALL_REPLIES=true to forward every reply to Slack
# (not just positive ones), so you can confirm the pipeline end to end.
FORWARD_ALL_REPLIES = os.getenv("FORWARD_ALL_REPLIES", "false").lower() == "true"

INSTANTLY_API_BASE = "https://api.instantly.ai/api/v2"
SLACK_API_BASE = "https://slack.com/api"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("bridge")

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers: pulling fields out of the Instantly webhook payload
# ---------------------------------------------------------------------------
# Instantly does not publish an exhaustive payload schema, so we look for the
# data under several plausible key names. The full payload is logged on every
# request -- once you see a real one, tighten these up.
def _first(payload, *keys, default=""):
    """Return the first present, non-empty value among the given keys."""
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    # also look one level deep inside common containers
    for container in ("data", "lead", "email", "payload"):
        nested = payload.get(container)
        if isinstance(nested, dict):
            for key in keys:
                if nested.get(key) not in (None, ""):
                    return nested[key]
    return default


def parse_reply(payload):
    """Normalise an Instantly webhook payload into the fields we care about."""
    return {
        "event_type": _first(payload, "event_type", "event", "type"),
        # The uuid of the email we reply to. This is the critical field for
        # sending a threaded reply back through Instantly.
        "reply_to_uuid": _first(
            payload, "reply_to_uuid", "email_id", "id", "uuid", "message_id"
        ),
        # Which of your sending mailboxes received the reply.
        "eaccount": _first(payload, "eaccount", "email_account", "from_email"),
        "lead_email": _first(payload, "lead_email", "lead", "email", "from"),
        "lead_name": _first(payload, "lead_name", "name", "first_name"),
        "campaign_name": _first(payload, "campaign_name", "campaign"),
        "subject": _first(payload, "subject", "email_subject", "reply_subject"),
        "reply_text": _first(
            payload,
            "reply_text",
            "reply_text_snippet",
            "reply_html",
            "body",
            "text",
            "message",
            "content",
        ),
        # Interest / sentiment signal, if Instantly provides one.
        "interest_status": _first(
            payload, "interest_status", "lead_interest_status", "i_status", "label"
        ),
    }


# Instantly interest-status values that we treat as "positive".
# 1 == Interested in Instantly's lead-status convention; we also match text labels.
POSITIVE_VALUES = {"1", "interested", "positive", "meeting_booked", "meeting booked"}


def is_positive(reply):
    """Decide whether a reply should be forwarded to Slack."""
    if FORWARD_ALL_REPLIES:
        return True
    status = str(reply.get("interest_status", "")).strip().lower()
    event = str(reply.get("event_type", "")).strip().lower()
    if status in POSITIVE_VALUES:
        return True
    # Some Instantly setups emit a dedicated event for interested leads.
    if "interest" in event or "positive" in event:
        return True
    return False


# ---------------------------------------------------------------------------
# Slack Block Kit message
# ---------------------------------------------------------------------------
def _truncate(text, limit=2800):
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_message_blocks(reply, context_value):
    who = reply["lead_name"] or reply["lead_email"] or "a lead"
    header = f"📬 Positive reply from {who}"[:150]
    meta_bits = []
    if reply["lead_email"]:
        meta_bits.append(f"*Lead:* {reply['lead_email']}")
    if reply["campaign_name"]:
        meta_bits.append(f"*Campaign:* {reply['campaign_name']}")
    if reply["eaccount"]:
        meta_bits.append(f"*Mailbox:* {reply['eaccount']}")
    meta = "   |   ".join(meta_bits) or "_no metadata_"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header}},
        {"type": "section", "text": {"type": "mrkdwn", "text": meta}},
        {"type": "divider"},
    ]
    if reply["subject"]:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Subject:* {reply['subject']}"},
            }
        )
    quoted = "\n".join("> " + line for line in _truncate(reply["reply_text"]).splitlines())
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Their reply:*\n{quoted or '> _(no text)_'}"},
        }
    )
    blocks.append(
        {
            "type": "actions",
            "block_id": "reply_actions",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "✍️  Write & send reply"},
                    "action_id": "open_reply_modal",
                    "value": context_value,
                }
            ],
        }
    )
    return blocks


# ---------------------------------------------------------------------------
# Slack Web API calls
# ---------------------------------------------------------------------------
def slack_call(method, payload):
    resp = requests.post(
        f"{SLACK_API_BASE}/{method}",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json=payload,
        timeout=15,
    )
    data = resp.json()
    if not data.get("ok"):
        log.error("Slack %s failed: %s", method, data.get("error"))
    return data


def verify_slack_signature(req):
    """Verify the request really came from Slack (HMAC over the raw body)."""
    timestamp = req.headers.get("X-Slack-Request-Timestamp", "")
    signature = req.headers.get("X-Slack-Signature", "")
    if not timestamp or not signature:
        return False
    # Reject anything older than 5 minutes (replay protection).
    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
    except ValueError:
        return False
    basestring = f"v0:{timestamp}:{req.get_data(as_text=True)}".encode()
    digest = hmac.new(
        SLACK_SIGNING_SECRET.encode(), basestring, hashlib.sha256
    ).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Instantly: send the reply
# ---------------------------------------------------------------------------
def send_instantly_reply(ctx, reply_body_text):
    subject = ctx.get("subject") or ""
    if subject and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    payload = {
        "eaccount": ctx["eaccount"],
        "reply_to_uuid": ctx["reply_to_uuid"],
        "subject": subject or "Re:",
        "body": {
            "text": reply_body_text,
            "html": "<p>" + reply_body_text.replace("\n", "<br>") + "</p>",
        },
    }
    resp = requests.post(
        f"{INSTANTLY_API_BASE}/emails/reply",
        headers={
            "Authorization": f"Bearer {INSTANTLY_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    ok = resp.status_code in (200, 201)
    if not ok:
        log.error("Instantly reply failed %s: %s", resp.status_code, resp.text[:500])
    return ok, resp


# ---------------------------------------------------------------------------
# Background worker: send via Instantly, then update the Slack message.
# Runs off-thread so Slack's 3-second modal-submit deadline is always met.
# ---------------------------------------------------------------------------
def process_reply_submission(ctx, reply_text, user_id):
    ok, resp = send_instantly_reply(ctx, reply_text)
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if ok:
        status_line = f"✅ Reply sent by <@{user_id}> · {sent_at}"
    else:
        status_line = (
            f"⚠️ Failed to send (Instantly returned {resp.status_code}). "
            f"<@{user_id}>, please retry or check Instantly."
        )
    quoted = "\n".join("> " + line for line in reply_text.splitlines())
    new_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Lead:* {ctx.get('lead_email','')}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Your reply:*\n{quoted}"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": status_line}]},
    ]
    slack_call(
        "chat.update",
        {
            "channel": ctx["channel"],
            "ts": ctx["message_ts"],
            "text": status_line,
            "blocks": new_blocks,
        },
    )


# ===========================================================================
# Routes
# ===========================================================================
@app.route("/", methods=["GET"])
@app.route("/healthz", methods=["GET"])
def health():
    return jsonify(status="ok", service="instantly-slack-bridge")


@app.route("/webhooks/instantly", methods=["POST"])
def instantly_webhook():
    # Optional shared-secret check.
    if INSTANTLY_WEBHOOK_SECRET:
        provided = (
            request.headers.get("X-Webhook-Secret")
            or request.args.get("secret", "")
        )
        if not hmac.compare_digest(provided, INSTANTLY_WEBHOOK_SECRET):
            log.warning("Rejected Instantly webhook: bad/missing secret")
            abort(401)

    payload = request.get_json(silent=True) or {}
    log.info("Instantly webhook payload: %s", json.dumps(payload)[:2000])

    reply = parse_reply(payload)
    if not is_positive(reply):
        log.info("Reply not positive (status=%r) -- skipping", reply["interest_status"])
        return jsonify(status="ignored")

    if not reply["reply_to_uuid"] or not reply["eaccount"]:
        log.warning("Missing reply_to_uuid/eaccount; cannot enable in-Slack reply")

    # Context that travels with the Slack button so we can reply later, with no DB.
    context = {
        "reply_to_uuid": reply["reply_to_uuid"],
        "eaccount": reply["eaccount"],
        "lead_email": reply["lead_email"],
        "subject": reply["subject"],
    }
    blocks = build_message_blocks(reply, json.dumps(context))
    result = slack_call(
        "chat.postMessage",
        {
            "channel": SLACK_CHANNEL_ID,
            "text": f"Positive reply from {reply['lead_email'] or 'a lead'}",
            "blocks": blocks,
        },
    )
    return jsonify(status="posted" if result.get("ok") else "slack_error")


@app.route("/slack/interactions", methods=["POST"])
def slack_interactions():
    if not verify_slack_signature(request):
        log.warning("Rejected Slack interaction: bad signature")
        abort(401)

    payload = json.loads(request.form.get("payload", "{}"))
    ptype = payload.get("type")

    # 1) Button click -> open the reply modal.
    if ptype == "block_actions":
        action = payload["actions"][0]
        if action.get("action_id") == "open_reply_modal":
            ctx = json.loads(action.get("value", "{}"))
            ctx["channel"] = payload["channel"]["id"]
            ctx["message_ts"] = payload["message"]["ts"]
            open_reply_modal(payload["trigger_id"], ctx)
        return ("", 200)

    # 2) Modal submitted -> send the reply (in background) and close the modal.
    if ptype == "view_submission":
        view = payload["view"]
        ctx = json.loads(view.get("private_metadata", "{}"))
        reply_text = (
            view["state"]["values"]["reply_block"]["reply_input"].get("value") or ""
        ).strip()
        if not reply_text:
            return jsonify(
                response_action="errors",
                errors={"reply_block": "Please write a reply before sending."},
            )
        user_id = payload["user"]["id"]
        threading.Thread(
            target=process_reply_submission,
            args=(ctx, reply_text, user_id),
            daemon=True,
        ).start()
        # Empty 200 closes the modal immediately.
        return ("", 200)

    return ("", 200)


def open_reply_modal(trigger_id, ctx):
    to = ctx.get("lead_email", "the lead")
    modal = {
        "type": "modal",
        "callback_id": "submit_reply",
        "private_metadata": json.dumps(ctx),
        "title": {"type": "plain_text", "text": "Reply to lead"},
        "submit": {"type": "plain_text", "text": "Send"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Sending to *{to}* via Instantly"}],
            },
            {
                "type": "input",
                "block_id": "reply_block",
                "label": {"type": "plain_text", "text": "Your reply"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "reply_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "Type your reply…"},
                },
            },
        ],
    }
    slack_call("views.open", {"trigger_id": trigger_id, "view": modal})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    app.run(host="0.0.0.0", port=port)
