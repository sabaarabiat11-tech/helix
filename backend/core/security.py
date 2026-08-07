"""Password hashing, JWT access tokens, and opaque secret tokens.

All cryptographic decisions live here so they can be audited — and changed —
in one place.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Any

import bcrypt
import jwt

from config import settings
from db.timeutil import utcnow

ALGORITHM = "HS256"

# bcrypt only reads the first 72 bytes of its input and raises on longer ones.
# Pre-hashing with SHA-256 means a long passphrase is fully mixed in rather
# than silently truncated, and the base64 digest is always 44 bytes.
_BCRYPT_ROUNDS = 12


def _prehash(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, extra: dict[str, Any] | None = None) -> str:
    now = utcnow()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_ttl_minutes)).timestamp()),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Return the payload, or None if the token is invalid, expired, or not an
    access token. Never raises — callers treat None as 'not authenticated'."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


def generate_secret_token(num_bytes: int = 32) -> str:
    """A high-entropy, URL-safe token. This is the value the user receives
    (in a cookie or an email link); only its hash is ever stored."""
    return secrets.token_urlsafe(num_bytes)


def hash_token(token: str) -> str:
    """SHA-256 of an opaque token. Fast by design — unlike a password, the
    token already has full entropy, so key-stretching buys nothing."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def sign_state(payload: str) -> str:
    """HMAC an OAuth state value so the callback can prove the redirect it
    received is one this server actually started."""
    mac = hmac.new(settings.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).decode("utf-8").rstrip("=")


def verify_state(payload: str, signature: str) -> bool:
    return hmac.compare_digest(sign_state(payload), signature)
