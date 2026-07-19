"""Pluggable voice + delivery backends for Colddrops.

VOICE  (best available wins, all behind one interface):
  elevenlabs  -> premium neural voice (needs a paid ElevenLabs plan)
  gtts        -> free, real speech (no cost, decent quality) — default now
  chime       -> offline placeholder tone (last resort, always works)

DELIVERY (self-operated — we own the carrier relationship, no reseller):
  telnyx      -> BYOC programmable voice: dial + answering-machine detection,
                 play the audio into voicemail. Needs a Telnyx key + Call
                 Control connection. True zero-ring still needs a carrier
                 voicemail-deposit deal; AMD is the buildable path we own.
  dry_run     -> simulate acceptance/delivery (tested default, $0)
"""
import math
import os
import struct
import uuid
import wave
from pathlib import Path

import requests

AUDIO_DIR = Path(__file__).resolve().parent / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

# --- config ---
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
VOICE_BACKEND = os.environ.get("VOICE_BACKEND", "auto")  # auto|elevenlabs|gtts|chime

TELNYX_KEY = os.environ.get("TELNYX_API_KEY", "")
TELNYX_CONNECTION = os.environ.get("TELNYX_CONNECTION_ID", "")
TELNYX_FROM = os.environ.get("TELNYX_FROM_NUMBER", "")
DELIVERY_BACKEND = os.environ.get("DELIVERY_BACKEND", "auto")  # auto|telnyx|dry_run

PUBLIC_BASE = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

_elevenlabs_blocked = False  # flips true after a paid-plan rejection


class ProviderError(Exception):
    pass


# ==================== VOICE ====================

def active_voice_backend() -> str:
    if VOICE_BACKEND != "auto":
        return VOICE_BACKEND
    if ELEVENLABS_KEY and not _elevenlabs_blocked:
        return "elevenlabs"
    if _gtts_available():
        return "gtts"
    return "chime"


def _gtts_available() -> bool:
    try:
        import gtts  # noqa: F401
        return True
    except Exception:
        return False


def _render_elevenlabs(text: str, tag: str) -> Path:
    global _elevenlabs_blocked
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}",
        headers={"xi-api-key": ELEVENLABS_KEY},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=120,
    )
    if r.status_code == 402:
        _elevenlabs_blocked = True
        raise ProviderError("elevenlabs_paid_plan_required")
    if r.status_code != 200:
        raise ProviderError(f"elevenlabs_error_{r.status_code}")
    path = AUDIO_DIR / f"{tag}.mp3"
    path.write_bytes(r.content)
    return path


def _render_gtts(text: str, tag: str) -> Path:
    from gtts import gTTS
    path = AUDIO_DIR / f"{tag}.mp3"
    gTTS(text=text, lang="en", tld="com").save(str(path))
    return path


def _render_chime(text: str, tag: str) -> Path:
    """Offline two-tone placeholder — always works, no network."""
    path = AUDIO_DIR / f"{tag}.wav"
    rate, seconds = 8000, min(3.0, max(1.0, len(text) / 60))
    frames = bytearray()
    for i in range(int(rate * seconds)):
        t = i / rate
        amp = 0.3 * math.sin(2 * math.pi * 392 * t) * (0.5 + 0.5 * math.sin(2 * math.pi * 1.5 * t))
        frames += struct.pack("<h", int(amp * 32767))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(frames))
    return path


def render_voice(text: str, tag: str) -> dict:
    """Render `text` to audio using the best available backend.

    Returns {path, url, backend}. Falls back gracefully (elevenlabs -> gtts ->
    chime) so a paywall or outage never breaks a send.
    """
    order = {
        "elevenlabs": [_render_elevenlabs, _render_gtts, _render_chime],
        "gtts": [_render_gtts, _render_chime],
        "chime": [_render_chime],
    }[active_voice_backend()]
    names = {_render_elevenlabs: "elevenlabs", _render_gtts: "gtts", _render_chime: "chime"}
    last_err = None
    for fn in order:
        try:
            path = fn(text, tag)
            return {"path": path, "url": f"{PUBLIC_BASE}/audio/{path.name}", "backend": names[fn]}
        except Exception as exc:  # try the next backend
            last_err = exc
    raise ProviderError(f"all voice backends failed: {last_err}")


# ==================== DELIVERY ====================

def active_delivery_backend() -> str:
    if DELIVERY_BACKEND != "auto":
        return DELIVERY_BACKEND
    if TELNYX_KEY and TELNYX_CONNECTION and TELNYX_FROM:
        return "telnyx"
    return "dry_run"


def delivery_live() -> bool:
    return active_delivery_backend() != "dry_run"


def voice_live() -> bool:
    """True when a real (non-placeholder) voice will be produced."""
    return active_voice_backend() in ("elevenlabs", "gtts")


def _send_telnyx(phone: str, audio_url: str, foreign_id: str) -> dict:
    """Self-operated delivery: originate a Call Control call with answering-
    machine detection. When AMD reports a machine/voicemail, our webhook plays
    `audio_url` and hangs up. We own routing, caller-ID and cost here.
    """
    r = requests.post(
        "https://api.telnyx.com/v2/calls",
        headers={"Authorization": f"Bearer {TELNYX_KEY}", "Content-Type": "application/json"},
        json={
            "connection_id": TELNYX_CONNECTION,
            "to": ("+" + phone) if not phone.startswith("+") else phone,
            "from": TELNYX_FROM,
            "answering_machine_detection": "detect",
            "webhook_url": f"{PUBLIC_BASE}/api/webhooks/telnyx",
            "client_state": _b64(foreign_id),
            # our webhook reads client_state to know which audio to play
            "custom_headers": [{"name": "X-Colddrops-Audio", "value": audio_url}],
        },
        timeout=60,
    )
    if r.status_code not in (200, 201):
        raise ProviderError(f"telnyx_error_{r.status_code}: {r.text[:200]}")
    data = r.json().get("data", {})
    return {"provider_id": data.get("call_control_id") or foreign_id,
            "status": "sending", "mode": "live", "backend": "telnyx"}


def _send_dry(phone: str, audio_url: str, foreign_id: str) -> dict:
    return {"provider_id": f"dry_{uuid.uuid4().hex[:10]}",
            "status": "delivered", "mode": "dry_run", "backend": "dry_run"}


def send_rvm(phone: str, audio_url: str, foreign_id: str) -> dict:
    if active_delivery_backend() == "telnyx":
        return _send_telnyx(phone, audio_url, foreign_id)
    return _send_dry(phone, audio_url, foreign_id)


def _b64(s: str) -> str:
    import base64
    return base64.b64encode(s.encode()).decode()


def decode_client_state(s: str | None) -> str:
    import base64
    if not s:
        return ""
    try:
        return base64.b64decode(s).decode()
    except Exception:
        return ""
