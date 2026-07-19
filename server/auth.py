"""Auth + workspace helpers for Colddrops (stdlib only)."""
import hashlib
import hmac
import os
import secrets
import time

PLAN_CAPS = {"starter": 1000, "growth": 5000, "scale": 15000}
DEFAULT_PLAN = "starter"


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2$120000${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iters, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def month_start(ts: float | None = None) -> float:
    import datetime as dt
    now = dt.datetime.utcfromtimestamp(ts or time.time())
    return dt.datetime(now.year, now.month, 1).timestamp()
