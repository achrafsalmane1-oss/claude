"""Pluggable SMS backend for Colddrops onboarding.

Sends the phone-verification code to a new user's mobile.

  telnyx  -> live SMS via Telnyx Messaging (needs TELNYX_API_KEY + a from-number
             or a messaging profile). Used automatically when configured.
  dev     -> no external send; the code is returned to the caller and logged so
             the whole login -> phone -> SMS -> dashboard flow works end-to-end
             at $0 before any paid number is provisioned. Default.

The endpoint decides whether to surface the dev code to the client; this module
only reports which backend actually handled the message.
"""
import os

import requests

TELNYX_KEY = os.environ.get("TELNYX_API_KEY", "")
# either a purchased from-number in E.164, or a Telnyx messaging profile id
TELNYX_SMS_FROM = os.environ.get("TELNYX_SMS_FROM", "")
TELNYX_MESSAGING_PROFILE_ID = os.environ.get("TELNYX_MESSAGING_PROFILE_ID", "")
SMS_BACKEND = os.environ.get("SMS_BACKEND", "auto")  # auto|telnyx|dev


def active_sms_backend() -> str:
    if SMS_BACKEND == "telnyx":
        return "telnyx"
    if SMS_BACKEND == "dev":
        return "dev"
    # auto: live only when we have a key and something to send from
    if TELNYX_KEY and (TELNYX_SMS_FROM or TELNYX_MESSAGING_PROFILE_ID):
        return "telnyx"
    return "dev"


def send_sms(to: str, text: str) -> dict:
    """Send a text message. Returns {backend, sent, id?, error?}."""
    backend = active_sms_backend()
    if backend == "telnyx":
        payload = {"to": to, "text": text}
        if TELNYX_SMS_FROM:
            payload["from"] = TELNYX_SMS_FROM
        if TELNYX_MESSAGING_PROFILE_ID:
            payload["messaging_profile_id"] = TELNYX_MESSAGING_PROFILE_ID
        try:
            r = requests.post(
                "https://api.telnyx.com/v2/messages",
                headers={"Authorization": f"Bearer {TELNYX_KEY}",
                         "Content-Type": "application/json"},
                json=payload, timeout=20,
            )
            if r.status_code < 300:
                mid = (r.json().get("data") or {}).get("id")
                return {"backend": "telnyx", "sent": True, "id": mid}
            return {"backend": "telnyx", "sent": False, "error": r.text[:300]}
        except Exception as e:  # network / config problems shouldn't break signup
            return {"backend": "telnyx", "sent": False, "error": str(e)[:300]}
    # dev backend: nothing leaves the box; the code is delivered in-band
    print(f"[sms:dev] to {to}: {text}")
    return {"backend": "dev", "sent": True}
