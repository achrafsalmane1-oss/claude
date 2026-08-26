"""Calendar Hub - one day view across every Google account you connect.

Run locally:  python3 app.py   ->  http://localhost:5000
"""

import os
import secrets
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from google_auth_oauthlib.flow import Flow

import calendar_api
import store

load_dotenv()

# This is a local-only tool served over plain http on localhost; oauthlib
# refuses non-https redirect URIs unless we say so.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
PORT = int(os.environ.get("PORT", "5000"))
HOST = os.environ.get("HOST", "127.0.0.1")
REDIRECT_URI = os.environ.get("REDIRECT_URI", f"http://localhost:{PORT}/oauth2/callback")
DEFAULT_TZ = os.environ.get("TIMEZONE") or "UTC"

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)


def _client_config():
    return {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }


def _resolve_tz(name):
    if not name:
        return DEFAULT_TZ
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return DEFAULT_TZ
    return name


def _configured():
    return bool(CLIENT_ID and CLIENT_SECRET)


@app.route("/")
def index():
    return render_template(
        "index.html",
        configured=_configured(),
        default_tz=DEFAULT_TZ,
    )


@app.get("/api/accounts")
def api_accounts():
    accounts = [
        {
            "email": a["email"],
            "label": a.get("label"),
            "color": a.get("color"),
            "hidden": bool(a.get("hidden")),
            "picture": a.get("picture"),
            "needs_reconnect": bool(a.get("needs_reconnect")),
            "added_at": a.get("added_at"),
        }
        for a in store.list_accounts()
    ]
    return jsonify({"configured": _configured(), "accounts": accounts})


@app.patch("/api/accounts/<email>")
def api_update_account(email):
    body = request.get_json(silent=True) or {}
    prefs = {}
    if "hidden" in body:
        prefs["hidden"] = bool(body["hidden"])
    if body.get("label"):
        prefs["label"] = str(body["label"])[:60]
    if body.get("color"):
        prefs["color"] = str(body["color"])[:16]
    if isinstance(body.get("muted_calendars"), list):
        prefs["muted_calendars"] = [str(c) for c in body["muted_calendars"]]
    updated = store.set_prefs(email, **prefs)
    if updated is None:
        return jsonify({"error": "unknown account"}), 404
    return jsonify({"ok": True})


@app.delete("/api/accounts/<email>")
def api_remove_account(email):
    if not store.remove_account(email):
        return jsonify({"error": "unknown account"}), 404
    return jsonify({"ok": True})


@app.get("/api/day")
def api_day():
    if not _configured():
        return jsonify({"error": "Google OAuth client is not configured. See README."}), 400

    raw_date = request.args.get("date")
    tz_name = _resolve_tz(request.args.get("tz"))
    try:
        day = date.fromisoformat(raw_date) if raw_date else datetime.now(ZoneInfo(tz_name)).date()
    except ValueError:
        return jsonify({"error": "bad date, expected YYYY-MM-DD"}), 400

    payload = calendar_api.fetch_day(day, tz_name, CLIENT_ID, CLIENT_SECRET)
    return jsonify(payload)


@app.get("/connect")
def connect():
    """Kick off Google consent for one more account."""
    if not _configured():
        return "Google OAuth client is not configured. See README.", 400

    flow = Flow.from_client_config(
        _client_config(), scopes=calendar_api.SCOPES, redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        # Always prompt: it is the only way to add a *second* account and the
        # only way Google returns a refresh token again.
        prompt="consent select_account",
    )
    session["oauth_state"] = state
    return redirect(auth_url)


@app.get("/oauth2/callback")
def oauth_callback():
    error = request.args.get("error")
    if error:
        return redirect(url_for("index", connected="error", reason=error))

    state = session.get("oauth_state")
    if not state or state != request.args.get("state"):
        return redirect(url_for("index", connected="error", reason="state_mismatch"))

    flow = Flow.from_client_config(
        _client_config(),
        scopes=calendar_api.SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state,
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    profile = _userinfo(creds)
    email = profile.get("email")
    if not email:
        return redirect(url_for("index", connected="error", reason="no_email"))

    store.save_account(
        email,
        refresh_token=creds.refresh_token,
        token=creds.token,
        expiry=creds.expiry.isoformat() if creds.expiry else None,
        scopes=list(creds.scopes or calendar_api.SCOPES),
        picture=profile.get("picture"),
        label=profile.get("name") or email.split("@")[0],
        added_at=datetime.utcnow().isoformat(),
    )
    session.pop("oauth_state", None)
    return redirect(url_for("index", connected=email))


def _userinfo(creds):
    from googleapiclient.discovery import build

    service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
    return service.userinfo().get().execute()


if __name__ == "__main__":
    if not _configured():
        print("\n  !  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not set.")
        print("     Copy .env.example to .env and fill them in (README has the steps).\n")
    print(f"  Calendar Hub -> http://localhost:{PORT}\n")
    app.run(host=HOST, port=PORT, debug=os.environ.get("DEBUG") == "1")
