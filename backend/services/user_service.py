"""User accounts and preferences.

This is the only module that creates users, so it is also where the one-time
handover of pre-V3 single-user data happens (see `db/migrations.py`): the first
account created on an upgraded install inherits the watchlist and notifications
that existed before accounts did.
"""
from __future__ import annotations

import json
import logging

from core.security import hash_password
from db import (
    claim_legacy_data,
    db_conn,
    execute,
    has_unclaimed_legacy_data,
    insert_returning_id,
    row,
    rows,
    scalar,
    utcnow_iso,
)

log = logging.getLogger("helix.users")

PUBLIC_USER_FIELDS = (
    "id, email, name, avatar_url, email_verified, is_active, is_admin, created_at, last_login_at"
)

JSON_PREFERENCE_FIELDS = ("focus_areas", "preferred_companies", "preferred_locations")
BOOL_PREFERENCE_FIELDS = (
    "notify_new_recommendations",
    "notify_pipeline_complete",
    "notify_new_companies",
    "notify_weekly_report",
    "notify_ai_insights",
)

VALID_DIGEST_FREQUENCIES = {"off", "instant", "daily", "weekly"}
VALID_SENIORITY = {"any", "junior", "mid", "senior", "leadership"}
VALID_THEMES = {"dark", "light"}

DEFAULT_PREFERENCES = {
    "theme": "dark",
    "focus_areas": [],
    "preferred_companies": [],
    "preferred_locations": [],
    "seniority_preference": "any",
    "min_score": 0,
    "digest_frequency": "weekly",
    "digest_hour": 8,
    "timezone": "UTC",
    "notify_new_recommendations": True,
    "notify_pipeline_complete": True,
    "notify_new_companies": True,
    "notify_weekly_report": True,
    "notify_ai_insights": True,
}


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


# --- Reads ------------------------------------------------------------------

def get_by_id(user_id: int) -> dict | None:
    with db_conn() as conn:
        return row(conn, f"SELECT {PUBLIC_USER_FIELDS} FROM users WHERE id = :id", {"id": user_id})


def get_by_email(email: str) -> dict | None:
    with db_conn() as conn:
        return row(
            conn,
            f"SELECT {PUBLIC_USER_FIELDS} FROM users WHERE email_normalized = :email",
            {"email": normalize_email(email)},
        )


def get_credentials(email: str) -> dict | None:
    """Includes the password hash — only auth_service should call this."""
    with db_conn() as conn:
        return row(
            conn,
            "SELECT id, email, name, password_hash, email_verified, is_active "
            "FROM users WHERE email_normalized = :email",
            {"email": normalize_email(email)},
        )


def list_active_users() -> list[dict]:
    with db_conn() as conn:
        return rows(
            conn,
            f"SELECT {PUBLIC_USER_FIELDS} FROM users WHERE is_active = :active ORDER BY id",
            {"active": True},
        )


def count_users() -> int:
    with db_conn() as conn:
        return scalar(conn, "SELECT COUNT(*) FROM users") or 0


# --- Writes -----------------------------------------------------------------

def create_user(
    email: str,
    password: str | None = None,
    name: str = "",
    avatar_url: str = "",
    email_verified: bool = False,
) -> dict:
    normalized = normalize_email(email)
    if not normalized:
        raise ValueError("Email is required")

    if get_by_email(normalized):
        raise ValueError("An account with that email already exists")

    # The very first account on a fresh install becomes the admin — a
    # single-tenant deployment shouldn't require a manual database edit to get
    # an operator, and every subsequent signup is an ordinary user.
    is_first_user = count_users() == 0
    now = utcnow_iso()

    with db_conn() as conn:
        user_id = insert_returning_id(
            conn,
            """
            INSERT INTO users
                (email, email_normalized, name, password_hash, avatar_url,
                 email_verified, is_active, is_admin, created_at, updated_at)
            VALUES
                (:email, :email_normalized, :name, :password_hash, :avatar_url,
                 :email_verified, :is_active, :is_admin, :created_at, :updated_at)
            """,
            {
                "email": email.strip(),
                "email_normalized": normalized,
                "name": (name or "").strip() or normalized.split("@")[0],
                "password_hash": hash_password(password) if password else None,
                "avatar_url": avatar_url or "",
                "email_verified": email_verified,
                "is_active": True,
                "is_admin": is_first_user,
                "created_at": now,
                "updated_at": now,
            },
        )
        _insert_default_preferences(conn, user_id, now)

    if is_first_user and has_unclaimed_legacy_data():
        claim_legacy_data(user_id)

    log.info("Created user %s (%s)%s", user_id, normalized, " [admin]" if is_first_user else "")
    return get_by_id(user_id)


def _insert_default_preferences(conn, user_id: int, now: str) -> None:
    execute(
        conn,
        """
        INSERT INTO user_preferences (user_id, updated_at) VALUES (:user_id, :updated_at)
        ON CONFLICT(user_id) DO NOTHING
        """,
        {"user_id": user_id, "updated_at": now},
    )


def update_profile(user_id: int, name: str | None = None, avatar_url: str | None = None) -> dict:
    updates: dict = {}
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        updates["name"] = cleaned
    if avatar_url is not None:
        updates["avatar_url"] = avatar_url.strip()

    if updates:
        updates["updated_at"] = utcnow_iso()
        set_clause = ", ".join(f"{key} = :{key}" for key in updates)
        with db_conn() as conn:
            execute(
                conn,
                f"UPDATE users SET {set_clause} WHERE id = :user_id",
                {**updates, "user_id": user_id},
            )
    return get_by_id(user_id)


def set_password(user_id: int, password: str) -> None:
    with db_conn() as conn:
        execute(
            conn,
            "UPDATE users SET password_hash = :hash, updated_at = :now WHERE id = :user_id",
            {"hash": hash_password(password), "now": utcnow_iso(), "user_id": user_id},
        )


def mark_email_verified(user_id: int) -> None:
    with db_conn() as conn:
        execute(
            conn,
            "UPDATE users SET email_verified = :verified, updated_at = :now WHERE id = :user_id",
            {"verified": True, "now": utcnow_iso(), "user_id": user_id},
        )


def record_login(user_id: int) -> None:
    with db_conn() as conn:
        execute(
            conn,
            "UPDATE users SET last_login_at = :now WHERE id = :user_id",
            {"now": utcnow_iso(), "user_id": user_id},
        )


def has_password(user_id: int) -> bool:
    with db_conn() as conn:
        found = row(conn, "SELECT password_hash FROM users WHERE id = :id", {"id": user_id})
    return bool(found and found["password_hash"])


def delete_user(user_id: int) -> None:
    """Hard delete. Every per-user table cascades from users.id."""
    with db_conn() as conn:
        execute(conn, "DELETE FROM users WHERE id = :id", {"id": user_id})


# --- Preferences ------------------------------------------------------------

def _decode_preferences(record: dict) -> dict:
    prefs = dict(record)
    prefs.pop("user_id", None)
    for field in JSON_PREFERENCE_FIELDS:
        raw = prefs.get(field)
        try:
            value = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            value = []
        prefs[field] = value if isinstance(value, list) else []
    for field in BOOL_PREFERENCE_FIELDS:
        prefs[field] = bool(prefs.get(field))
    prefs["min_score"] = int(prefs.get("min_score") or 0)
    prefs["digest_hour"] = int(prefs.get("digest_hour") or 8)
    return prefs


def get_preferences(user_id: int) -> dict:
    with db_conn() as conn:
        record = row(
            conn, "SELECT * FROM user_preferences WHERE user_id = :user_id", {"user_id": user_id}
        )
        if not record:
            # A user created before preferences existed, or a partially failed
            # signup. Materialize the defaults rather than returning them
            # transiently, so a later update has a row to write to.
            _insert_default_preferences(conn, user_id, utcnow_iso())
            record = row(
                conn, "SELECT * FROM user_preferences WHERE user_id = :user_id", {"user_id": user_id}
            )
    return _decode_preferences(record) if record else dict(DEFAULT_PREFERENCES)


def update_preferences(user_id: int, **fields) -> dict:
    updates: dict = {}

    for field in JSON_PREFERENCE_FIELDS:
        if fields.get(field) is not None:
            value = fields[field]
            if not isinstance(value, list):
                raise ValueError(f"{field} must be a list")
            updates[field] = json.dumps([str(v).strip() for v in value if str(v).strip()])

    for field in BOOL_PREFERENCE_FIELDS:
        if fields.get(field) is not None:
            updates[field] = bool(fields[field])

    if fields.get("theme") is not None:
        if fields["theme"] not in VALID_THEMES:
            raise ValueError(f"Invalid theme: {fields['theme']}")
        updates["theme"] = fields["theme"]

    if fields.get("seniority_preference") is not None:
        if fields["seniority_preference"] not in VALID_SENIORITY:
            raise ValueError(f"Invalid seniority preference: {fields['seniority_preference']}")
        updates["seniority_preference"] = fields["seniority_preference"]

    if fields.get("digest_frequency") is not None:
        if fields["digest_frequency"] not in VALID_DIGEST_FREQUENCIES:
            raise ValueError(f"Invalid digest frequency: {fields['digest_frequency']}")
        updates["digest_frequency"] = fields["digest_frequency"]

    if fields.get("min_score") is not None:
        score = int(fields["min_score"])
        if not 0 <= score <= 100:
            raise ValueError("min_score must be between 0 and 100")
        updates["min_score"] = score

    if fields.get("digest_hour") is not None:
        hour = int(fields["digest_hour"])
        if not 0 <= hour <= 23:
            raise ValueError("digest_hour must be between 0 and 23")
        updates["digest_hour"] = hour

    if fields.get("timezone") is not None:
        updates["timezone"] = str(fields["timezone"]).strip() or "UTC"

    if not updates:
        return get_preferences(user_id)

    get_preferences(user_id)  # guarantees the row exists before UPDATE
    updates["updated_at"] = utcnow_iso()
    set_clause = ", ".join(f"{key} = :{key}" for key in updates)
    with db_conn() as conn:
        execute(
            conn,
            f"UPDATE user_preferences SET {set_clause} WHERE user_id = :user_id",
            {**updates, "user_id": user_id},
        )
    return get_preferences(user_id)


def users_wanting_digest(frequency: str) -> list[dict]:
    """Active users subscribed to a given digest cadence, with preferences
    attached — the digest worker's entry point."""
    result = []
    for user in list_active_users():
        prefs = get_preferences(user["id"])
        if prefs.get("digest_frequency") == frequency:
            result.append({**user, "preferences": prefs})
    return result
