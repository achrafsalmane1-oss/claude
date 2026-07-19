"""Voice + delivery provider clients for Colddrops.

Both clients work in two modes:
  - live     : real API calls (ElevenLabs TTS, Drop Cowboy RVM)
  - dry-run  : no keys configured — renders a placeholder WAV and simulates
               delivery, so the whole pipeline is testable end-to-end today.
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

ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # "Rachel"
DC_TEAM = os.environ.get("DROPCOWBOY_TEAM_ID", "")
DC_SECRET = os.environ.get("DROPCOWBOY_SECRET", "")
PUBLIC_BASE = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


class ProviderError(Exception):
    pass


def voice_live() -> bool:
    return bool(ELEVENLABS_KEY)


def delivery_live() -> bool:
    return bool(DC_TEAM and DC_SECRET)


# ---------- voice ----------

def _placeholder_wav(path: Path, seconds: float) -> None:
    """A soft two-tone chime — a real, playable stand-in for the TTS render."""
    rate = 8000
    n = int(rate * seconds)
    frames = bytearray()
    for i in range(n):
        t = i / rate
        amp = 0.3 * math.sin(2 * math.pi * 392 * t) * (0.5 + 0.5 * math.sin(2 * math.pi * 1.5 * t))
        frames += struct.pack("<h", int(amp * 32767))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def render_voice(text: str, tag: str) -> tuple[Path, str]:
    """Render `text` to an audio file; returns (path, public URL)."""
    if voice_live():
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}",
            headers={"xi-api-key": ELEVENLABS_KEY},
            json={"text": text, "model_id": "eleven_multilingual_v2"},
            timeout=120,
        )
        if r.status_code != 200:
            raise ProviderError(f"ElevenLabs error {r.status_code}: {r.text[:200]}")
        path = AUDIO_DIR / f"{tag}.mp3"
        path.write_bytes(r.content)
    else:
        path = AUDIO_DIR / f"{tag}.wav"
        # rough speech duration: ~15 chars/second, clamped for the placeholder
        _placeholder_wav(path, min(3.0, max(1.0, len(text) / 15 / 4)))
    return path, f"{PUBLIC_BASE}/audio/{path.name}"


# ---------- delivery ----------

def send_rvm(phone: str, audio_url: str, foreign_id: str) -> dict:
    """Queue a ringless voicemail drop. Returns provider result.

    Drop Cowboy queues the drop and delivers it inside TCPA-compliant local
    windows on their side; final status arrives on our webhook.
    """
    if delivery_live():
        r = requests.post(
            "https://api.dropcowboy.com/v1/rvm",
            json={
                "team_id": DC_TEAM,
                "secret": DC_SECRET,
                "phone_number": phone,
                "audio_url": audio_url,
                "audio_type": audio_url.rsplit(".", 1)[-1],
                "foreign_id": foreign_id,
                "callback_url": f"{PUBLIC_BASE}/api/webhooks/dropcowboy",
            },
            timeout=60,
        )
        if r.status_code not in (200, 201, 202):
            raise ProviderError(f"Drop Cowboy error {r.status_code}: {r.text[:200]}")
        data = r.json() if r.content else {}
        return {"provider_id": data.get("id") or foreign_id, "status": "sent", "mode": "live"}
    # dry-run: pretend the carrier accepted and delivered instantly
    return {"provider_id": f"dry_{uuid.uuid4().hex[:10]}", "status": "delivered", "mode": "dry_run"}
