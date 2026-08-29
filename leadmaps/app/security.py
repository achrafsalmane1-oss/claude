"""Password hashing, signed sessions and API key minting."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

_hasher = PasswordHasher()

API_KEY_PREFIX = "lm_live_"
MIN_PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_problem(password: str) -> str | None:
    """Return a human-readable reason the password is unacceptable, if any."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password.lower() in {"password12", "1234567890", "qwertyuiop"}:
        return "Please choose a less predictable password."
    return None


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="session")


def sign_session(user_id: str) -> str:
    return _serializer().dumps({"uid": user_id})


def read_session(token: str) -> str | None:
    """Return the user id carried by ``token``, or None if it is not usable."""
    try:
        data = _serializer().loads(token, max_age=get_settings().session_max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    uid = data.get("uid")
    return uid if isinstance(uid, str) else None


def generate_api_key() -> tuple[str, str, str]:
    """Mint a key. Returns ``(plaintext, prefix, hash)``.

    Only the hash is stored; the plaintext is surfaced once at creation.
    """
    raw = secrets.token_urlsafe(32)
    plaintext = f"{API_KEY_PREFIX}{raw}"
    return plaintext, plaintext[: len(API_KEY_PREFIX) + 6], hash_api_key(plaintext)


def hash_api_key(plaintext: str) -> str:
    """Hash an API key.

    Keys are 256 bits of entropy, so a plain SHA-256 is appropriate here and
    keeps per-request auth cheap. Passwords use Argon2 instead.
    """
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)
