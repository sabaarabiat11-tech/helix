"""Portable schema definition — one MetaData that creates identically on
SQLite and PostgreSQL.

Two deliberate modelling decisions worth stating up front:

**Discovery data is global, personalization is per-user.** The `people` table
is a single shared corpus produced by the discovery pipeline; it has no
`user_id` and never will. Every user sees the same underlying researchers.
What differs per user is the layer on top — their watchlist, their
notifications, their preferences, and the ranking applied to that shared
corpus. This is why one nightly pipeline run can serve thousands of users
instead of running once per account.

**Timestamps are ISO-8601 UTC strings, not native datetimes.** They sort
lexicographically in the same order they sort chronologically, so range
queries and ORDER BY behave correctly on both dialects with no driver-specific
datetime adaptation, and the existing pipeline CSV format maps straight in.
See `db/timeutil.py` for the single pair of functions that produce and parse
them. A later Postgres migration can widen these to `timestamptz` without
touching query logic.
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()


# --- Shared discovery corpus (written by the pipeline, read by everyone) -----

people = Table(
    "people",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("title", Text, nullable=False, server_default=""),
    Column("company", Text, nullable=False, server_default=""),
    Column("linkedin_url", Text, nullable=False, unique=True),
    Column("location", Text, nullable=False, server_default=""),
    Column("reason", Text, nullable=False, server_default=""),
    Column("discovery_date", Text, nullable=False, server_default=""),
    Column("source", Text, nullable=False, server_default="Unknown"),
    Index("idx_people_company", "company"),
    Index("idx_people_date", "discovery_date"),
    Index("idx_people_source", "source"),
)

meta = Table(
    "meta",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text),
)


# --- Accounts ---------------------------------------------------------------

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    # `email` keeps the address as the user typed it (for display and for
    # sending); `email_normalized` is the lowercased form every lookup and the
    # uniqueness guarantee runs against, so Alice@x.com and alice@x.com cannot
    # both register.
    Column("email", Text, nullable=False),
    Column("email_normalized", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False, server_default=""),
    # Null for accounts created purely through OAuth — those users have no
    # password until they explicitly set one.
    Column("password_hash", Text, nullable=True),
    Column("avatar_url", Text, nullable=False, server_default=""),
    Column("email_verified", Boolean, nullable=False, server_default="0"),
    Column("is_active", Boolean, nullable=False, server_default="1"),
    Column("is_admin", Boolean, nullable=False, server_default="0"),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("last_login_at", Text, nullable=True),
)

user_preferences = Table(
    "user_preferences",
    metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("theme", Text, nullable=False, server_default="dark"),
    # JSON-encoded lists. Stored as Text rather than a JSON column because the
    # JSON type differs between SQLite and Postgres and we only ever read these
    # whole, never query inside them.
    Column("focus_areas", Text, nullable=False, server_default="[]"),
    Column("preferred_companies", Text, nullable=False, server_default="[]"),
    Column("preferred_locations", Text, nullable=False, server_default="[]"),
    Column("seniority_preference", Text, nullable=False, server_default="any"),
    Column("min_score", Integer, nullable=False, server_default="0"),
    Column("digest_frequency", Text, nullable=False, server_default="weekly"),
    Column("digest_hour", Integer, nullable=False, server_default="8"),
    Column("timezone", Text, nullable=False, server_default="UTC"),
    Column("notify_new_recommendations", Boolean, nullable=False, server_default="1"),
    Column("notify_pipeline_complete", Boolean, nullable=False, server_default="1"),
    Column("notify_new_companies", Boolean, nullable=False, server_default="1"),
    Column("notify_weekly_report", Boolean, nullable=False, server_default="1"),
    Column("notify_ai_insights", Boolean, nullable=False, server_default="1"),
    Column("updated_at", Text, nullable=False),
)

oauth_accounts = Table(
    "oauth_accounts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("provider", Text, nullable=False),
    Column("provider_account_id", Text, nullable=False),
    Column("email", Text, nullable=False, server_default=""),
    Column("created_at", Text, nullable=False),
    UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
    Index("idx_oauth_user", "user_id"),
)


# --- Sessions and one-time tokens -------------------------------------------

refresh_tokens = Table(
    "refresh_tokens",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    # Only the SHA-256 of the token is stored. A database leak therefore does
    # not hand an attacker usable sessions.
    Column("token_hash", Text, nullable=False, unique=True),
    Column("expires_at", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("revoked_at", Text, nullable=True),
    # Set when this token is rotated, so presenting an already-rotated token
    # can be detected as theft and the whole family revoked.
    Column("replaced_by", Text, nullable=True),
    Column("user_agent", Text, nullable=False, server_default=""),
    Column("ip_address", Text, nullable=False, server_default=""),
    Index("idx_refresh_user", "user_id"),
)

email_tokens = Table(
    "email_tokens",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("token_hash", Text, nullable=False, unique=True),
    # 'verify_email' | 'reset_password'
    Column("purpose", Text, nullable=False),
    Column("expires_at", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("used_at", Text, nullable=True),
    Index("idx_email_tokens_user", "user_id"),
)


# --- Per-user product data --------------------------------------------------

watchlist = Table(
    "watchlist",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("person_id", Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
    Column("notes", Text, nullable=False, server_default=""),
    Column("tags", Text, nullable=False, server_default=""),
    Column("priority", Text, nullable=False, server_default="medium"),
    Column("status", Text, nullable=False, server_default="new"),
    Column("reminder_date", Text, nullable=False, server_default=""),
    Column("followed_at", Text, nullable=False),
    # Two different users following the same researcher is normal; the same
    # user following them twice is not.
    UniqueConstraint("user_id", "person_id", name="uq_watchlist_user_person"),
    Index("idx_watchlist_user", "user_id"),
)

notifications = Table(
    "notifications",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("type", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("message", Text, nullable=False),
    Column("link", Text, nullable=False, server_default=""),
    Column("created_at", Text, nullable=False),
    Column("read", Boolean, nullable=False, server_default="0"),
    Index("idx_notifications_user_read", "user_id", "read"),
)

recommendation_history = Table(
    "recommendation_history",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("person_id", Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
    Column("score", Integer, nullable=False, server_default="0"),
    # 'app' | 'email' — lets a digest avoid repeating what it already sent
    # without hiding things the user has merely seen in the UI.
    Column("channel", Text, nullable=False, server_default="app"),
    Column("shown_on", Text, nullable=False),  # YYYY-MM-DD
    Column("created_at", Text, nullable=False),
    UniqueConstraint("user_id", "person_id", "channel", "shown_on", name="uq_rec_history_daily"),
    Index("idx_rec_history_user", "user_id"),
)

email_log = Table(
    "email_log",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("to_email", Text, nullable=False),
    Column("subject", Text, nullable=False),
    Column("template", Text, nullable=False, server_default=""),
    Column("provider", Text, nullable=False, server_default=""),
    # 'sent' | 'failed'
    Column("status", Text, nullable=False, server_default="sent"),
    Column("error", Text, nullable=False, server_default=""),
    Column("created_at", Text, nullable=False),
    Index("idx_email_log_user", "user_id"),
)


__all__ = [
    "metadata",
    "people",
    "meta",
    "users",
    "user_preferences",
    "oauth_accounts",
    "refresh_tokens",
    "email_tokens",
    "watchlist",
    "notifications",
    "recommendation_history",
    "email_log",
]
