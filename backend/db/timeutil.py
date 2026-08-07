"""The single place timestamps are produced and parsed.

Every stored timestamp is an ISO-8601 string in UTC with an explicit offset,
produced only by `utcnow_iso()`. Because the format is fixed-width and
timezone-consistent, string comparison equals chronological comparison — which
is what lets `expires_at > :now` work as a plain SQL string comparison on both
SQLite and PostgreSQL.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta


def utcnow() -> datetime:
    return datetime.now(UTC)


def utcnow_iso() -> str:
    return utcnow().isoformat()


def iso_in(**delta: float) -> str:
    """ISO timestamp offset from now, e.g. ``iso_in(days=30)``."""
    return (utcnow() + timedelta(**delta)).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    """Parse a stored timestamp back to an aware UTC datetime.

    Tolerates the naive local-time strings written by earlier versions of the
    app (and the pipeline's plain ``YYYY-MM-DD`` dates) by assuming UTC when no
    offset is present, so old rows never crash a comparison.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def is_expired(value: str | None) -> bool:
    """True if the stored timestamp is absent or already in the past."""
    parsed = parse_iso(value)
    if parsed is None:
        return True
    return parsed <= utcnow()


def today_iso() -> str:
    """Current UTC date as YYYY-MM-DD — matches the pipeline's date format."""
    return utcnow().date().isoformat()


def parse_date(value: str | None) -> date | None:
    """Parse a plain YYYY-MM-DD discovery date."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
