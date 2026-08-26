"""Local token + preference storage for connected Google accounts.

Everything lives in a single JSON file outside the repo (default
~/.calendar_hub/accounts.json) with 0600 permissions, because it holds
OAuth refresh tokens.
"""

import json
import os
import threading
from pathlib import Path

DATA_DIR = Path(os.environ.get("CALENDAR_HUB_DATA", Path.home() / ".calendar_hub"))
ACCOUNTS_FILE = DATA_DIR / "accounts.json"

# Distinct, colour-blind-friendly-ish hues assigned per account in order.
PALETTE = [
    "#4f8cff",  # blue
    "#f5a524",  # amber
    "#2dd4a7",  # teal
    "#f2557f",  # pink
    "#a78bfa",  # violet
    "#7dd3fc",  # sky
    "#facc15",  # yellow
    "#fb923c",  # orange
]

_lock = threading.Lock()


def _read():
    if not ACCOUNTS_FILE.exists():
        return {"accounts": {}}
    try:
        with ACCOUNTS_FILE.open() as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {"accounts": {}}
    data.setdefault("accounts", {})
    return data


def _write(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(DATA_DIR, 0o700)
    tmp = ACCOUNTS_FILE.with_suffix(".tmp")
    with tmp.open("w") as fh:
        json.dump(data, fh, indent=2)
    os.chmod(tmp, 0o600)
    tmp.replace(ACCOUNTS_FILE)


def _next_color(accounts):
    used = {a.get("color") for a in accounts.values()}
    for color in PALETTE:
        if color not in used:
            return color
    return PALETTE[len(accounts) % len(PALETTE)]


def list_accounts():
    """All connected accounts, oldest connection first."""
    data = _read()
    accounts = []
    for email, acct in data["accounts"].items():
        acct = dict(acct)
        acct["email"] = email
        accounts.append(acct)
    accounts.sort(key=lambda a: a.get("added_at", ""))
    return accounts


def get_account(email):
    acct = _read()["accounts"].get(email)
    if acct is None:
        return None
    acct = dict(acct)
    acct["email"] = email
    return acct


def save_account(email, *, refresh_token, token=None, expiry=None, scopes=None,
                 label=None, picture=None, added_at=None):
    """Insert or update an account, keeping existing prefs and refresh token."""
    with _lock:
        data = _read()
        existing = data["accounts"].get(email, {})
        # Google only hands back a refresh token on first consent; keep the old
        # one if this round-trip didn't include a new one.
        acct = {
            **existing,
            "refresh_token": refresh_token or existing.get("refresh_token"),
            "token": token,
            "expiry": expiry,
            "scopes": scopes or existing.get("scopes"),
            "label": label or existing.get("label") or email.split("@")[0],
            "picture": picture or existing.get("picture"),
            "color": existing.get("color") or _next_color(data["accounts"]),
            "hidden": existing.get("hidden", False),
            "added_at": existing.get("added_at") or added_at,
            "needs_reconnect": False,
        }
        data["accounts"][email] = acct
        _write(data)
    return get_account(email)


def update_tokens(email, token, expiry):
    with _lock:
        data = _read()
        if email not in data["accounts"]:
            return
        data["accounts"][email]["token"] = token
        data["accounts"][email]["expiry"] = expiry
        data["accounts"][email]["needs_reconnect"] = False
        _write(data)


def mark_needs_reconnect(email):
    with _lock:
        data = _read()
        if email in data["accounts"]:
            data["accounts"][email]["needs_reconnect"] = True
            _write(data)


def set_prefs(email, **prefs):
    allowed = {"label", "color", "hidden", "muted_calendars"}
    with _lock:
        data = _read()
        if email not in data["accounts"]:
            return None
        for key, value in prefs.items():
            if key in allowed and value is not None:
                data["accounts"][email][key] = value
        _write(data)
    return get_account(email)


def remove_account(email):
    with _lock:
        data = _read()
        removed = data["accounts"].pop(email, None)
        if removed is not None:
            _write(data)
    return removed is not None
