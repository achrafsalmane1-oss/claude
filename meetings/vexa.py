# -*- coding: utf-8 -*-
"""Client Vexa -- parler a une instance Vexa auto-hebergee, sans dependance.

Tout passe par urllib : rien a installer, comme le reste du repo.

Variables d'environnement (ou meetings/.env, charge automatiquement) :
  VEXA_API_KEY    (obligatoire) cle imprimee par setup.sh
  VEXA_API_BASE   defaut http://localhost:8056  (Vexa Lite ; la stack
                  compose complete ecoute sur 18056)
  VEXA_BOT_NAME   nom affiche du bot dans la reunion (defaut "Notes")
  VEXA_LANG       langue forcee (ex. fr, en) ; VIDE = detection par Whisper,
                  segment par segment. A laisser vide quand une reunion
                  melange francais et anglais.
  VEXA_TIMEOUT    secondes par appel HTTP (defaut 30)
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(HERE, ".env")

PLATFORMS = ("google_meet", "zoom", "teams", "jitsi")


def load_env(path=ENV_FILE):
    """Charge un .env sans python-dotenv. L'environnement reel gagne toujours."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


class VexaError(Exception):
    """Erreur renvoyee par l'API (code HTTP + detail lisible)."""

    def __init__(self, status, detail, body=""):
        self.status = status
        self.detail = detail
        self.body = body
        super().__init__("HTTP %s -- %s" % (status, detail))


# --- parsing des liens de reunion -------------------------------------------
# Meme discipline que le parseur de Vexa : on compare le hostname EXACT (ou un
# sous-domaine explicite), jamais un `in` sur la chaine -- "zoom.us" in host
# accepte aussi zoom.us.evil.example.

def _host_is(host, domain):
    return host == domain or host.endswith("." + domain)


def parse_meeting_url(url):
    """URL de reunion -> (platform, native_meeting_id, passcode).

    Couvre les formes courantes de Meet / Zoom / Teams / Jitsi. Pour un lien
    Teams exotique, laisser l'API trancher : `join` envoie meeting_url brut et
    relit la plateforme et l'id dans la reponse.
    """
    url = (url or "").strip()
    if not url:
        raise ValueError("lien de reunion vide")
    if "://" not in url:
        url = "https://" + url

    p = urlparse(url)
    host = (p.hostname or "").lower()
    path = p.path or ""
    query = parse_qs(p.query or "")

    # Google Meet : https://meet.google.com/abc-defg-hij
    if host == "meet.google.com":
        if path.startswith("/lookup/"):
            raise ValueError(
                "lien Meet /lookup/ non joignable : prends le lien standard de l'invitation"
            )
        code = path.strip("/").split("/")[0] if path else ""
        if re.fullmatch(r"[a-z]{3}-[a-z]{4}-[a-z]{3}", code):
            return "google_meet", code, None
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{3,38}[a-z0-9]", code):
            return "google_meet", code, None
        raise ValueError("lien Google Meet invalide : attendu meet.google.com/abc-defg-hij")

    # Teams personnel : https://teams.live.com/meet/1234567890123?p=passcode
    if _host_is(host, "teams.live.com"):
        m = re.match(r"^/meet/(\d{10,15})/?$", path)
        if m:
            return "teams", m.group(1), (query.get("p") or [None])[0]
        raise ValueError("lien teams.live.com non reconnu : attendu /meet/<id 10-15 chiffres>")

    # Teams entreprise : lien court /meet/<id>, ou deep link #/meet/<id>
    if _host_is(host, "teams.microsoft.com") or _host_is(host, "teams.microsoft.us"):
        frag = p.fragment or ""
        if frag.startswith("/meet/"):
            fp = urlparse("https://x" + frag)
            fm = re.match(r"^/meet/(\d{10,15})/?$", fp.path)
            if fm:
                fq = parse_qs(fp.query or "")
                return "teams", fm.group(1), (fq.get("p") or [None])[0]
        m = re.match(r"^/meet/(\d{10,15})/?$", path)
        if m:
            return "teams", m.group(1), (query.get("p") or [None])[0]
        # /l/meetup-join/19:meeting_...@thread.v2 -- le thread id EST l'id natif
        m = re.search(r"(19%3ameeting_[^%/@]+%40thread\.v2|19:meeting_[^/@]+@thread\.v2)", path, re.I)
        if m:
            from urllib.parse import unquote
            return "teams", unquote(m.group(1)), None
        raise ValueError(
            "lien Teams non reconnu : envoie-le tel quel a `join`, l'API sait le lire"
        )

    # Zoom : https://us05web.zoom.us/j/81234567890?pwd=xxxx
    if _host_is(host, "zoom.us") or _host_is(host, "zoomgov.com"):
        # l'id est numerique sur un lien /j/, mais /my/<nom-perso> est valide aussi
        m = re.search(r"/(?:j|s|my)/([A-Za-z0-9._-]+)", path)
        if m:
            return "zoom", m.group(1), (query.get("pwd") or [None])[0]
        raise ValueError("lien Zoom non reconnu : attendu .../j/<id de reunion>")

    # Jitsi : n'importe quel hote, la room est le dernier segment
    if _host_is(host, "jit.si") or _host_is(host, "meet.jit.si") or "jitsi" in host:
        room = path.strip("/").split("/")[-1]
        if room:
            return "jitsi", room, None
        raise ValueError("lien Jitsi sans nom de salle")

    raise ValueError(
        "plateforme non reconnue pour %s (Meet, Zoom, Teams, Jitsi supportes)" % host
    )


def looks_like_url(s):
    s = (s or "").strip().lower()
    return s.startswith(("http://", "https://")) or "." in s.split("/")[0]


class Vexa(object):
    """Les quelques appels dont on a besoin : envoyer un bot, lire, arreter."""

    def __init__(self, base=None, key=None, timeout=None):
        load_env()
        self.base = (base or os.environ.get("VEXA_API_BASE") or "http://localhost:8056").rstrip("/")
        self.key = key or os.environ.get("VEXA_API_KEY", "")
        self.timeout = int(timeout or os.environ.get("VEXA_TIMEOUT", "30"))

    # --- transport ---------------------------------------------------------
    def _call(self, method, path, body=None):
        if not self.key:
            raise VexaError(
                0,
                "VEXA_API_KEY absente -- lance ./meetings/setup.sh, ou copie la cle "
                "dans meetings/.env",
            )
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"X-API-Key": self.key, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode("utf-8") or "{}"
                return json.loads(raw) if raw.strip().startswith(("{", "[")) else {"raw": raw}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            detail = raw
            try:
                parsed = json.loads(raw)
                detail = parsed.get("detail") or parsed.get("message") or raw
                if isinstance(detail, list):  # erreurs de validation FastAPI
                    detail = "; ".join(
                        "%s: %s" % (".".join(str(x) for x in d.get("loc", [])), d.get("msg", ""))
                        for d in detail
                    )
            except Exception:
                pass
            raise VexaError(e.code, str(detail)[:600], raw)
        except urllib.error.URLError as e:
            raise VexaError(
                0,
                "Vexa injoignable sur %s (%s). La stack tourne ? "
                "`docker ps | grep vexa-lite`" % (self.base, e.reason),
            )

    # --- API ---------------------------------------------------------------
    def send_bot(self, target, bot_name=None, language=None, task=None,
                 passcode=None, transcribe=True, record=None):
        """Envoie un bot. `target` = URL complete (l'API la parse) ou id natif."""
        body = {
            "bot_name": bot_name or os.environ.get("VEXA_BOT_NAME") or "Notes",
            "transcribe_enabled": bool(transcribe),
        }
        lang = language if language is not None else os.environ.get("VEXA_LANG", "")
        if lang:
            body["language"] = lang
        if task:
            body["task"] = task
        if record is not None:
            body["recording_enabled"] = bool(record)

        if looks_like_url(target):
            body["meeting_url"] = target if "://" in target else "https://" + target
            # le passcode present dans l'URL gagne cote serveur ; on n'ajoute le
            # notre que s'il est explicite
            if passcode:
                body["passcode"] = passcode
        else:
            raise ValueError(
                "donne l'URL complete de la reunion (l'API en deduit la plateforme)"
            )
        return self._call("POST", "/bots", body)

    def transcript(self, platform, native_id):
        return self._call("GET", "/transcripts/%s/%s" % (platform, native_id))

    def transcript_by_id(self, meeting_id):
        return self._call("GET", "/transcripts/by-id/%s" % meeting_id)

    def bots_status(self):
        return self._call("GET", "/bots/status")

    def stop_bot(self, platform, native_id):
        return self._call("DELETE", "/bots/%s/%s" % (platform, native_id))

    def meetings(self):
        return self._call("GET", "/meetings")

    def health(self):
        """/health n'exige pas de cle : utile pour le diagnostic."""
        try:
            req = urllib.request.Request(self.base + "/health")
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")[:200]
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception as e:
            return 0, str(e)


def running_bots(status_payload):
    """`GET /bots/status` porte running_bots (0.10) ET running/count (0.12)."""
    if not isinstance(status_payload, dict):
        return []
    for key in ("running_bots", "running", "bots"):
        val = status_payload.get(key)
        if isinstance(val, list):
            return val
    return []


def meeting_rows(payload):
    """`GET /meetings` -> liste, quelle que soit l'enveloppe."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("meetings", "items", "results", "data"):
            val = payload.get(key)
            if isinstance(val, list):
                return val
    return []
