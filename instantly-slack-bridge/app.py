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
import re
import time
import urllib.parse
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify, abort

try:
    import anthropic
except ImportError:  # available in production via requirements.txt
    anthropic = None

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

# Optional: AI-based positive/negative classification (handles any language and
# nuance far better than keywords). If set, it becomes the primary decision.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_CLASSIFIER_MODEL = os.getenv("AI_CLASSIFIER_MODEL", "claude-haiku-4-5")

# Signature automatically appended to every reply sent from Slack. EMAIL_SIGNATURE
# is the default; EMAIL_SIGNATURES_JSON optionally maps a sending mailbox to its
# own signature (e.g. {"ssupport@cloudstrayd.com": "Best,\nST Support"}).
EMAIL_SIGNATURE = os.getenv("EMAIL_SIGNATURE", "")
try:
    EMAIL_SIGNATURES = json.loads(os.getenv("EMAIL_SIGNATURES_JSON", "") or "{}")
except (ValueError, TypeError):
    EMAIL_SIGNATURES = {}

INSTANTLY_API_BASE = "https://api.instantly.ai/api/v2"
SLACK_API_BASE = "https://slack.com/api"

# --- Graph8 (second sequencer) ---------------------------------------------
GRAPH8_API_KEY = os.getenv("GRAPH8_API_KEY", "")
GRAPH8_WEBHOOK_SECRET = os.getenv("GRAPH8_WEBHOOK_SECRET", "")
GRAPH8_API_BASE = "https://be.graph8.com/api/v1"
SLACK_CHANNEL_IMPORTERS = os.getenv("SLACK_CHANNEL_IMPORTERS", "")
SLACK_CHANNEL_EXPORTERS = os.getenv("SLACK_CHANNEL_EXPORTERS", "")
GRAPH8_IMPORTERS_CAMPAIGN_ID = os.getenv("GRAPH8_IMPORTERS_CAMPAIGN_ID", "")
GRAPH8_EXPORTERS_CAMPAIGN_ID = os.getenv("GRAPH8_EXPORTERS_CAMPAIGN_ID", "")
GRAPH8_IMPORTERS_SEQUENCE_ID = os.getenv("GRAPH8_IMPORTERS_SEQUENCE_ID", "")
GRAPH8_EXPORTERS_SEQUENCE_ID = os.getenv("GRAPH8_EXPORTERS_SEQUENCE_ID", "")

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


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _deep_find(payload, regex, prefer_keys=()):
    """Recursively search a payload for the first value matching regex.

    Values under a key whose name contains one of prefer_keys win; otherwise
    the first match found anywhere is returned. Makes us robust to whatever
    shape/nesting Instantly uses.
    """
    preferred, any_match = [None], [None]

    def walk(node, key=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str):
            m = regex.search(node)
            if m:
                val = m.group(0)
                if any(p in key.lower() for p in prefer_keys) and preferred[0] is None:
                    preferred[0] = val
                if any_match[0] is None:
                    any_match[0] = val

    walk(payload)
    return preferred[0] or any_match[0] or ""


def parse_reply(payload):
    """Normalise an Instantly webhook payload into the fields we care about."""
    eaccount = _first(payload, "eaccount", "email_account", "from_email")
    lead_email = _first(
        payload, "lead_email", "lead", "lead_email_address",
        "from_address_email", "email", "from"
    )
    reply_to_uuid = _first(
        payload, "reply_to_uuid", "email_id", "id", "uuid", "message_id"
    )
    # Recursive fallbacks so we always find the lead/id regardless of nesting.
    if not lead_email:
        candidate = _deep_find(payload, _EMAIL_RE, prefer_keys=("lead", "from", "contact", "prospect"))
        if candidate and candidate != eaccount:
            lead_email = candidate
    if not reply_to_uuid:
        reply_to_uuid = _deep_find(payload, _UUID_RE, prefer_keys=("email", "message", "reply"))
    return {
        "event_type": _first(payload, "event_type", "event", "type"),
        "reply_to_uuid": reply_to_uuid,
        "eaccount": eaccount,
        "lead_email": lead_email,
        "lead_name": _first(payload, "lead_name", "name", "first_name"),
        "campaign_name": _first(payload, "campaign_name", "campaign"),
        "subject": _first(payload, "subject", "email_subject", "reply_subject"),
        "reply_text": _first(
            payload, "reply_text", "reply_text_snippet", "reply_html",
            "body", "text", "message", "content",
        ),
        "interest_status": _first(
            payload, "interest_status", "lead_interest_status", "i_status", "label"
        ),
    }


# Instantly interest-status values that we treat as "positive".
# 1 == Interested in Instantly's lead-status convention; we also match text labels.
POSITIVE_VALUES = {"1", "interested", "positive", "meeting_booked", "meeting booked"}


# ---------------------------------------------------------------------------
# Instantly API reads — fetch the authoritative reply so we never depend on
# the webhook payload carrying the exact fields we need.
# ---------------------------------------------------------------------------
def _instantly_get(path):
    try:
        r = requests.get(
            f"{INSTANTLY_API_BASE}{path}",
            headers={"Authorization": f"Bearer {INSTANTLY_API_KEY}"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        log.warning("Instantly GET %s -> %s", path, r.status_code)
    except Exception as exc:  # noqa: BLE001
        log.warning("Instantly GET %s failed: %s", path, exc)
    return None


def fetch_email_by_id(email_id):
    return _instantly_get(f"/emails/{urllib.parse.quote(str(email_id))}")


def fetch_latest_reply_for_lead(lead_email):
    """Find the most recent *received* email from a given lead."""
    data = _instantly_get(f"/emails?search={urllib.parse.quote(lead_email)}&limit=10")
    items = (data or {}).get("items", []) if isinstance(data, dict) else []
    received = [e for e in items if e.get("ue_type") == 2]  # 2 == received
    received.sort(key=lambda e: e.get("timestamp_email", ""), reverse=True)
    if received:
        return received[0]
    return items[0] if items else None


_campaign_names = {}


def fetch_campaign_name(campaign_id):
    if not campaign_id:
        return ""
    if campaign_id in _campaign_names:
        return _campaign_names[campaign_id]
    data = _instantly_get(f"/campaigns/{urllib.parse.quote(str(campaign_id))}")
    name = (data or {}).get("name", "") if isinstance(data, dict) else ""
    _campaign_names[campaign_id] = name
    return name


def _strip_html(html):
    text = re.sub(r"<br\s*/?>", "\n", html or "", flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def email_to_reply(email):
    """Turn a full Instantly email object into our normalised reply dict."""
    body = email.get("body") or {}
    text = ""
    if isinstance(body, dict):
        text = (body.get("text") or "").strip()
        if not text and body.get("html"):
            text = _strip_html(body["html"])
    text = text or (email.get("content_preview") or "")

    name = ""
    faj = email.get("from_address_json")
    if isinstance(faj, list) and faj and isinstance(faj[0], dict):
        name = faj[0].get("name", "")
    elif isinstance(faj, dict):
        name = faj.get("name", "")

    return {
        "event_type": "reply_received",
        "reply_to_uuid": email.get("id", ""),
        "eaccount": email.get("eaccount", ""),
        "lead_email": email.get("lead") or email.get("from_address_email", ""),
        "lead_name": name,
        "campaign_name": fetch_campaign_name(email.get("campaign_id")),
        "subject": email.get("subject", ""),
        "reply_text": text,
        "interest_status": email.get("i_status"),
        "is_auto_reply": email.get("is_auto_reply"),
    }


# Phrases that signal a reply is NOT a positive lead. If any appear, we skip it.
NEGATIVE_PHRASES = [
    # explicit disinterest / opt-out
    "not interested", "no interest", "no thanks", "no thank you",
    "unsubscribe", "remove me", "take me off", "opt out", "opt-out",
    "do not contact", "don't contact", "stop emailing", "stop contacting",
    "leave me alone", "not the right", "wrong person", "wrong contact",
    "please remove", "kindly remove", "no longer interested",
    # wrong/left contact
    "no longer with", "has left the company", "is no longer", "no longer employed",
    "no longer works", "has left", "left the company", "is not the correct",
    # out-of-office / auto-reply
    "out of office", "out of the office", "out-of-office",
    "away from the office", "away from office", "away from my desk",
    "i am away", "i'm away", "currently away", "am currently away",
    "on vacation", "on holiday", "public holiday", "bank holiday",
    "on leave", "annual leave", "maternity leave", "paternity leave",
    "parental leave", "sick leave", "medical leave",
    "currently traveling", "currently travelling", "limited access to email",
    "limited access to my email", "limited email access",
    "will respond to your email", "will reply to your email",
    "will respond when i", "will get back to you when i",
    "back in the office", "return to the office", "returning to the office",
    "upon my return", "on my return", "in my absence", "during my absence",
    "if your email is urgent", "if this is urgent", "if your enquiry is urgent",
    "if your inquiry is urgent", "for urgent matters", "for immediate assistance",
    "for urgent assistance", "thank you for your email. i am",
    "automatic reply", "auto-reply", "autoreply", "auto reply",
    "this is an automated", "automated response", "automated message",
    "do-not-reply", "do not reply", "not monitored", "no longer monitored",
    # auto-acknowledgements
    "thank you for contacting", "thanks for contacting",
    "we have received your", "your message has been received",
    "your email has been received", "this is to confirm we received",
    "your enquiry has been received", "your inquiry has been received",
    "this address will be", "will be deactivated", "is being deactivated",
    "no longer be monitored", "will no longer be", "endereço será", "será desativado",
    # bounces / system
    "delivery has failed", "undeliverable", "mailer-daemon", "mail delivery",
    "address not found", "recipient not found", "message blocked", "spam",
]


_ai_client = None


def _get_ai_client():
    global _ai_client
    if _ai_client is None and anthropic and ANTHROPIC_API_KEY:
        _ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _ai_client


_AI_SYSTEM = (
    "You classify replies to cold sales emails for a sales team. Respond with "
    "exactly one word: POSITIVE or NEGATIVE.\n"
    "POSITIVE = a real human showing interest or genuinely engaging — asking a "
    "question, wanting pricing/info/a deck, proposing or accepting a meeting/call, "
    "expressing curiosity, or routing you to the right person.\n"
    "NEGATIVE = automatic reply, out-of-office, delivery/bounce notice, "
    "unsubscribe or opt-out, 'not interested', wrong person, or a mere "
    "acknowledgement with no interest. Judge replies in ANY language."
)


def classify_positive_ai(reply):
    """Return True/False from the AI classifier, or None if unavailable."""
    client = _get_ai_client()
    if not client:
        return None
    text = ((reply.get("subject") or "") + "\n\n" + (reply.get("reply_text") or "")).strip()
    if not text:
        return None
    try:
        msg = client.messages.create(
            model=AI_CLASSIFIER_MODEL,
            max_tokens=5,
            system=_AI_SYSTEM,
            messages=[{"role": "user", "content": text[:6000]}],
        )
        out = "".join(b.text for b in msg.content if b.type == "text").strip().upper()
        if "POSITIVE" in out:
            return True
        if "NEGATIVE" in out:
            return False
    except Exception as exc:  # noqa: BLE001
        log.warning("AI classify failed (%s); falling back to keywords", exc)
    return None


def is_positive(reply):
    """Decide whether a reply should be forwarded to Slack.

    Instantly is not auto-tagging interest status in this account, so we
    classify from the reply itself: skip clear non-positives (opt-outs,
    auto-replies, wrong-person, bounces) and surface everything else, which
    in cold-email practice is the set of replies worth a human response.
    A real Instantly interest tag, if ever present, always counts as positive.
    """
    if FORWARD_ALL_REPLIES:
        return True
    # Auto-replies (OOO, bounces) flagged by the source are never positive.
    if reply.get("is_auto_reply"):
        return False
    # Honour Instantly's interest status. It is numeric: >0 is a positive
    # status (Interested / Meeting Booked / ...), <0 is negative.
    raw = reply.get("interest_status")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = None
    if n is not None and n != 0:
        return n > 0
    # AI classification is the most accurate signal (any language); use it when
    # configured. Falls through to keyword heuristics if it's unavailable.
    ai = classify_positive_ai(reply)
    if ai is not None:
        return ai
    status = str(raw or "").strip().lower()
    event = str(reply.get("event_type", "")).strip().lower()
    if status in POSITIVE_VALUES or "interest" in event or "positive" in event:
        return True
    if status in {"not_interested", "wrong", "negative"}:
        return False
    # Fall back to reading the subject + reply text for negative signals.
    text = ((reply.get("subject") or "") + "  " + (reply.get("reply_text") or "")).lower()
    if any(phrase in text for phrase in NEGATIVE_PHRASES):
        return False
    return True


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
def apply_signature(text, eaccount=""):
    """Append the configured signature (per-mailbox if set, else default)."""
    sig = ""
    if eaccount and EMAIL_SIGNATURES:
        sig = EMAIL_SIGNATURES.get(eaccount.lower(), "")
    sig = sig or EMAIL_SIGNATURE
    if not sig:
        return text
    return text.rstrip() + "\n\n" + sig


def send_instantly_reply(ctx, reply_body_text):
    reply_body_text = apply_signature(reply_body_text, ctx.get("eaccount", ""))
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
# Graph8 (second sequencer): read replies + send replies via the Inbox API
# ---------------------------------------------------------------------------
def _graph8_get(path):
    try:
        r = requests.get(
            f"{GRAPH8_API_BASE}{path}",
            headers={"Authorization": f"Bearer {GRAPH8_API_KEY}"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        log.warning("Graph8 GET %s -> %s", path, r.status_code)
    except Exception as exc:  # noqa: BLE001
        log.warning("Graph8 GET %s failed: %s", path, exc)
    return None


def fetch_graph8_reply(reply_id):
    data = _graph8_get(f"/inbox/{urllib.parse.quote(str(reply_id), safe='')}")
    if isinstance(data, dict):
        obj = data.get("data", data)
        if isinstance(obj, list):
            obj = obj[0] if obj else None
        return obj
    return None


# Graph8 tag names that mark a reply as not worth surfacing.
GRAPH8_NEGATIVE_TAGS = {"bounced", "out of office", "unsubscribed", "not interested"}


def graph8_to_reply(obj):
    """Normalise a Graph8 inbox thread object into our reply dict."""
    contact = obj.get("contact") or {}
    msgs = obj.get("messages") or []
    contact_msgs = [m for m in msgs if str(m.get("responder", "")).upper() == "CONTACT"]
    user_msgs = [m for m in msgs if str(m.get("responder", "")).upper() == "USER"]
    latest = contact_msgs[-1] if contact_msgs else (msgs[-1] if msgs else {})
    text = _strip_html(latest.get("content", "")) if latest else ""
    eaccount = (user_msgs[-1].get("from_address") if user_msgs else "") or ""
    name = " ".join(
        x for x in [contact.get("first_name", ""), contact.get("last_name", "")] if x
    ).strip()
    tags = [str(t.get("name", "")).lower() for t in (obj.get("tags") or [])]
    return {
        "provider": "graph8",
        "event_type": "email_replied",
        "reply_to_uuid": obj.get("id", ""),  # Graph8 reply_id (used to send)
        "eaccount": eaccount,
        "lead_email": contact.get("email", "") or (latest.get("from_address", "") if latest else ""),
        "lead_name": name,
        "campaign_name": obj.get("campaign_name", ""),
        "subject": obj.get("subject", ""),
        "reply_text": text,
        "interest_status": "",
        "is_auto_reply": any(t in GRAPH8_NEGATIVE_TAGS for t in tags),
        "channel_kind": obj.get("channel", "email"),
    }


_seq_emails_cache = {}  # sequence_id -> (fetched_at, set_of_emails)


def _graph8_sequence_emails(seq_id):
    """Set of contact emails that have replied within a given sequence (cached)."""
    if not seq_id:
        return set()
    cached = _seq_emails_cache.get(seq_id)
    if cached and (time.time() - cached[0]) < 60:
        return cached[1]
    data = _graph8_get(f"/inbox?sequence_id={urllib.parse.quote(seq_id)}&page_size=100")
    emails = {
        (r.get("contact") or {}).get("email", "").lower()
        for r in ((data or {}).get("data", []) if isinstance(data, dict) else [])
        if (r.get("contact") or {}).get("email")
    }
    _seq_emails_cache[seq_id] = (time.time(), emails)
    return emails


def route_graph8_channel(payload, obj):
    """Pick the importers vs exporters Slack channel for a Graph8 reply.

    Primary signal: which live sequence the lead belongs to (the two
    sequences have disjoint reply sets). Falls back to ids/keywords in the
    webhook payload.
    """
    email = ((obj.get("contact") or {}).get("email") or "").lower()
    if email:
        if email in _graph8_sequence_emails(GRAPH8_EXPORTERS_SEQUENCE_ID):
            return SLACK_CHANNEL_EXPORTERS
        if email in _graph8_sequence_emails(GRAPH8_IMPORTERS_SEQUENCE_ID):
            return SLACK_CHANNEL_IMPORTERS

    blob = json.dumps(payload).lower() + " " + json.dumps(obj, default=str).lower()
    for sid, ch in [
        (GRAPH8_EXPORTERS_SEQUENCE_ID, SLACK_CHANNEL_EXPORTERS),
        (GRAPH8_EXPORTERS_CAMPAIGN_ID, SLACK_CHANNEL_EXPORTERS),
        (GRAPH8_IMPORTERS_SEQUENCE_ID, SLACK_CHANNEL_IMPORTERS),
        (GRAPH8_IMPORTERS_CAMPAIGN_ID, SLACK_CHANNEL_IMPORTERS),
    ]:
        if sid and sid.lower() in blob:
            return ch
    if "exporter" in blob:
        return SLACK_CHANNEL_EXPORTERS
    if "importer" in blob:
        return SLACK_CHANNEL_IMPORTERS
    return SLACK_CHANNEL_IMPORTERS  # safe default


def send_graph8_reply(ctx, reply_body_text):
    reply_body_text = apply_signature(reply_body_text, ctx.get("eaccount", ""))
    reply_id = urllib.parse.quote(str(ctx["reply_to_uuid"]), safe="")
    payload = {
        "body": reply_body_text,
        "channel": ctx.get("channel_kind", "email"),
    }
    if ctx.get("subject"):
        payload["subject"] = ctx["subject"]
    resp = requests.post(
        f"{GRAPH8_API_BASE}/inbox/{reply_id}/send",
        headers={
            "Authorization": f"Bearer {GRAPH8_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    ok = resp.status_code in (200, 201)
    if not ok:
        log.error("Graph8 reply failed %s: %s", resp.status_code, resp.text[:500])
    return ok, resp


# ---------------------------------------------------------------------------
# Background worker: send the reply, then update the Slack message.
# Runs off-thread so Slack's 3-second modal-submit deadline is always met.
# ---------------------------------------------------------------------------
def process_reply_submission(ctx, reply_text, user_id):
    provider = ctx.get("provider", "instantly")
    if provider == "graph8":
        ok, resp = send_graph8_reply(ctx, reply_text)
        source = "Graph8"
    else:
        ok, resp = send_instantly_reply(ctx, reply_text)
        source = "Instantly"
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if ok:
        status_line = f"✅ Reply sent by <@{user_id}> · {sent_at}"
    else:
        status_line = (
            f"⚠️ Failed to send ({source} returned {resp.status_code}). "
            f"<@{user_id}>, please retry."
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


@app.route("/debug/last", methods=["GET"])
def debug_last():
    if not INSTANTLY_WEBHOOK_SECRET or request.args.get("secret") != INSTANTLY_WEBHOOK_SECRET:
        abort(401)
    try:
        with open("/tmp/last_instantly.json") as fh:
            return jsonify(json.load(fh))
    except Exception:  # noqa: BLE001
        return jsonify(error="no payload captured yet")


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
    try:
        with open("/tmp/last_instantly.json", "w") as fh:
            json.dump(payload, fh)
    except Exception:  # noqa: BLE001
        pass

    reply = parse_reply(payload)

    # The webhook payload alone is unreliable, so fetch the authoritative email
    # from Instantly's API (by id, else by lead) and use that as the source of
    # truth for the lead, text, subject and the id we reply to.
    email = None
    if reply.get("reply_to_uuid"):
        email = fetch_email_by_id(reply["reply_to_uuid"])
    if not email and reply.get("lead_email"):
        email = fetch_latest_reply_for_lead(reply["lead_email"])
    if email:
        reply = email_to_reply(email)
    else:
        log.warning("Could not resolve email from payload; using raw fields")

    if not is_positive(reply):
        log.info("Reply not positive (status=%r) -- skipping", reply.get("interest_status"))
        return jsonify(status="ignored")

    if not reply["reply_to_uuid"] or not reply["eaccount"]:
        log.warning("Missing reply_to_uuid/eaccount; cannot enable in-Slack reply")

    # Context that travels with the Slack button so we can reply later, with no DB.
    context = {
        "provider": "instantly",
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


@app.route("/webhooks/graph8", methods=["POST"])
def graph8_webhook():
    if GRAPH8_WEBHOOK_SECRET:
        provided = (
            request.headers.get("X-Webhook-Secret") or request.args.get("secret", "")
        )
        if not hmac.compare_digest(provided, GRAPH8_WEBHOOK_SECRET):
            log.warning("Rejected Graph8 webhook: bad/missing secret")
            abort(401)

    payload = request.get_json(silent=True) or {}
    log.info("Graph8 webhook payload: %s", json.dumps(payload)[:2000])
    try:
        with open("/tmp/last_graph8.json", "w") as fh:
            json.dump(payload, fh)
    except Exception:  # noqa: BLE001
        pass

    # Only act on reply events.
    event = json.dumps(payload).lower()
    if "repl" not in event:
        return jsonify(status="ignored", reason="not a reply event")

    # Find the reply/thread id anywhere in the payload, then fetch the thread.
    reply_id = _first(
        payload, "reply_id", "thread_id", "message_id", "id", "inbox_id"
    ) or _deep_find(payload, re.compile(r"[^\s\"]+@[^\s\"]+"), prefer_keys=("reply", "message", "thread", "id"))
    obj = fetch_graph8_reply(reply_id) if reply_id else None
    if not obj:
        log.warning("Graph8: could not resolve inbox thread (reply_id=%r)", reply_id)
        return jsonify(status="error", reason="thread not found")

    reply = graph8_to_reply(obj)
    if not is_positive(reply):
        log.info("Graph8 reply not positive -- skipping (%s)", reply.get("lead_email"))
        return jsonify(status="ignored")

    channel = route_graph8_channel(payload, obj)
    context = {
        "provider": "graph8",
        "reply_to_uuid": reply["reply_to_uuid"],
        "channel_kind": reply.get("channel_kind", "email"),
        "lead_email": reply["lead_email"],
        "eaccount": reply.get("eaccount", ""),
        "subject": reply["subject"],
    }
    blocks = build_message_blocks(reply, json.dumps(context))
    result = slack_call(
        "chat.postMessage",
        {
            "channel": channel,
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
        # Send synchronously so this works on serverless hosts (e.g. Vercel),
        # where background threads are frozen once the response is returned.
        # The Instantly call is fast, so we stay within Slack's 3s window.
        process_reply_submission(ctx, reply_text, user_id)
        # Empty 200 closes the modal.
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
