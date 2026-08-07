"""Data access layer.

Import everything database-related from here rather than from the submodules,
so the rest of the app never depends on which engine or dialect is underneath.
"""
from db.engine import (
    db_conn,
    engine,
    execute,
    insert_returning_id,
    row,
    rows,
    scalar,
)
from db.migrations import claim_legacy_data, has_unclaimed_legacy_data, init_db
from db.timeutil import (
    is_expired,
    iso_in,
    parse_date,
    parse_iso,
    today_iso,
    utcnow,
    utcnow_iso,
)

__all__ = [
    "db_conn",
    "engine",
    "execute",
    "insert_returning_id",
    "row",
    "rows",
    "scalar",
    "init_db",
    "claim_legacy_data",
    "has_unclaimed_legacy_data",
    "utcnow",
    "utcnow_iso",
    "iso_in",
    "parse_iso",
    "is_expired",
    "today_iso",
    "parse_date",
]
