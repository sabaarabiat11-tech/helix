"""Authentication: sessions, refresh-token rotation, and one-time email tokens.

Session design — short-lived JWT access token + long-lived opaque refresh token:

* The **access token** is a signed JWT the SPA holds in memory. It expires in
  minutes, so a leaked one has a small blast radius, and verifying it needs no
  database round trip.
* The **refresh token** is a random secret delivered in an httpOnly cookie, so
  page JavaScript (and therefore XSS) cannot read it. Only its SHA-256 is
  stored, so a database leak yields no usable sessions.
* Refresh tokens **rotate**: each use revokes the presented token and issues a
  new one. If a token that has already been rotated is presented again, that
  means two parties hold the same token — the session was stolen — so the
  entire token family for that user is revoked and everyone is logged out.
"""
from __future__ import annotations

import logging

from config import settings
from core.security import (
    create_access_token,
    generate_secret_token,
    hash_token,
    verify_password,
)
from db import (
    db_conn,
    execute,
    insert_returning_id,
    is_expired,
    iso_in,
    row,
    utcnow_iso,
)
from services import user_service

log = logging.getLogger("helix.auth")

PURPOSE_VERIFY_EMAIL = "verify_email"
PURPOSE_RESET_PASSWORD = "reset_password"

MIN_PASSWORD_LENGTH = 8


class AuthError(Exception):
    """Raised for any authentication failure. The message is safe to show."""


def validate_password(password: str) -> None:
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")


# --- Sessions ---------------------------------------------------------------

def issue_session(user_id: int, user_agent: str = "", ip_address: str = "") -> dict:
    """Mint a fresh access/refresh pair for a user who has just proved identity."""
    refresh_token = generate_secret_token()
    with db_conn() as conn:
        insert_returning_id(
            conn,
            """
            INSERT INTO refresh_tokens
                (user_id, token_hash, expires_at, created_at, user_agent, ip_address)
            VALUES
                (:user_id, :token_hash, :expires_at, :created_at, :user_agent, :ip_address)
            """,
            {
                "user_id": user_id,
                "token_hash": hash_token(refresh_token),
                "expires_at": iso_in(days=settings.refresh_token_ttl_days),
                "created_at": utcnow_iso(),
                "user_agent": (user_agent or "")[:400],
                "ip_address": (ip_address or "")[:64],
            },
        )
    user_service.record_login(user_id)
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": refresh_token,
        "expires_in": settings.access_token_ttl_minutes * 60,
    }


def _revoke_family(conn, user_id: int) -> None:
    execute(
        conn,
        "UPDATE refresh_tokens SET revoked_at = :now WHERE user_id = :user_id AND revoked_at IS NULL",
        {"now": utcnow_iso(), "user_id": user_id},
    )


def rotate_session(refresh_token: str, user_agent: str = "", ip_address: str = "") -> dict:
    """Exchange a refresh token for a new pair, revoking the presented one."""
    if not refresh_token:
        raise AuthError("Not signed in")

    presented_hash = hash_token(refresh_token)

    with db_conn() as conn:
        record = row(
            conn,
            "SELECT id, user_id, expires_at, revoked_at FROM refresh_tokens WHERE token_hash = :hash",
            {"hash": presented_hash},
        )

        if not record:
            raise AuthError("Session expired, please sign in again")

        if record["revoked_at"]:
            # Replay of an already-rotated token: assume the session was stolen
            # and invalidate every session this user has.
            log.warning("Refresh token reuse detected for user %s — revoking all sessions", record["user_id"])
            _revoke_family(conn, record["user_id"])
            raise AuthError("Session expired, please sign in again")

        if is_expired(record["expires_at"]):
            raise AuthError("Session expired, please sign in again")

        user_id = record["user_id"]
        new_token = generate_secret_token()
        execute(
            conn,
            "UPDATE refresh_tokens SET revoked_at = :now, replaced_by = :replaced_by WHERE id = :id",
            {"now": utcnow_iso(), "replaced_by": hash_token(new_token), "id": record["id"]},
        )
        insert_returning_id(
            conn,
            """
            INSERT INTO refresh_tokens
                (user_id, token_hash, expires_at, created_at, user_agent, ip_address)
            VALUES
                (:user_id, :token_hash, :expires_at, :created_at, :user_agent, :ip_address)
            """,
            {
                "user_id": user_id,
                "token_hash": hash_token(new_token),
                "expires_at": iso_in(days=settings.refresh_token_ttl_days),
                "created_at": utcnow_iso(),
                "user_agent": (user_agent or "")[:400],
                "ip_address": (ip_address or "")[:64],
            },
        )

    user = user_service.get_by_id(user_id)
    if not user or not user["is_active"]:
        raise AuthError("Account is disabled")

    return {
        "access_token": create_access_token(user_id),
        "refresh_token": new_token,
        "expires_in": settings.access_token_ttl_minutes * 60,
        "user": user,
    }


def revoke_session(refresh_token: str) -> None:
    if not refresh_token:
        return
    with db_conn() as conn:
        execute(
            conn,
            "UPDATE refresh_tokens SET revoked_at = :now "
            "WHERE token_hash = :hash AND revoked_at IS NULL",
            {"now": utcnow_iso(), "hash": hash_token(refresh_token)},
        )


def revoke_all_sessions(user_id: int) -> None:
    with db_conn() as conn:
        _revoke_family(conn, user_id)


# --- Credentials ------------------------------------------------------------

def authenticate(email: str, password: str) -> dict:
    credentials = user_service.get_credentials(email)

    # Always run a hash comparison, even when the account doesn't exist, so the
    # response time doesn't reveal which emails are registered.
    password_ok = verify_password(password, credentials["password_hash"] if credentials else None)

    if not credentials or not password_ok:
        raise AuthError("Incorrect email or password")
    if not credentials["is_active"]:
        raise AuthError("This account has been disabled")
    if settings.require_email_verification and not credentials["email_verified"]:
        raise AuthError("Please verify your email address before signing in")

    return user_service.get_by_id(credentials["id"])


# --- One-time email tokens --------------------------------------------------

def create_email_token(user_id: int, purpose: str) -> str:
    """Issue a single-use token for an emailed link. Any outstanding token for
    the same purpose is invalidated, so only the newest email in the user's
    inbox works."""
    token = generate_secret_token()
    with db_conn() as conn:
        execute(
            conn,
            "UPDATE email_tokens SET used_at = :now "
            "WHERE user_id = :user_id AND purpose = :purpose AND used_at IS NULL",
            {"now": utcnow_iso(), "user_id": user_id, "purpose": purpose},
        )
        insert_returning_id(
            conn,
            """
            INSERT INTO email_tokens (user_id, token_hash, purpose, expires_at, created_at)
            VALUES (:user_id, :token_hash, :purpose, :expires_at, :created_at)
            """,
            {
                "user_id": user_id,
                "token_hash": hash_token(token),
                "purpose": purpose,
                "expires_at": iso_in(hours=settings.email_token_ttl_hours),
                "created_at": utcnow_iso(),
            },
        )
    return token


def consume_email_token(token: str, purpose: str) -> int:
    """Validate and burn a token, returning the user id it belonged to."""
    if not token:
        raise AuthError("This link is invalid")

    with db_conn() as conn:
        record = row(
            conn,
            "SELECT id, user_id, expires_at, used_at FROM email_tokens "
            "WHERE token_hash = :hash AND purpose = :purpose",
            {"hash": hash_token(token), "purpose": purpose},
        )
        if not record or record["used_at"]:
            raise AuthError("This link is invalid or has already been used")
        if is_expired(record["expires_at"]):
            raise AuthError("This link has expired — please request a new one")

        execute(
            conn,
            "UPDATE email_tokens SET used_at = :now WHERE id = :id",
            {"now": utcnow_iso(), "id": record["id"]},
        )
    return record["user_id"]


def verify_email(token: str) -> dict:
    user_id = consume_email_token(token, PURPOSE_VERIFY_EMAIL)
    user_service.mark_email_verified(user_id)
    return user_service.get_by_id(user_id)


def reset_password(token: str, new_password: str) -> dict:
    validate_password(new_password)
    user_id = consume_email_token(token, PURPOSE_RESET_PASSWORD)
    user_service.set_password(user_id, new_password)
    # A password reset is the standard response to a suspected compromise, so
    # every existing session is invalidated.
    revoke_all_sessions(user_id)
    return user_service.get_by_id(user_id)


def change_password(user_id: int, current_password: str, new_password: str) -> None:
    credentials = user_service.get_credentials(user_service.get_by_id(user_id)["email"])
    if credentials and credentials["password_hash"]:
        if not verify_password(current_password, credentials["password_hash"]):
            raise AuthError("Your current password is incorrect")
    # A user who signed up via OAuth has no password yet; setting the first one
    # doesn't require proving a previous one they never had.
    validate_password(new_password)
    user_service.set_password(user_id, new_password)
