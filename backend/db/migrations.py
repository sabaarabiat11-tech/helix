"""Schema creation and forward migration.

The app has to boot cleanly against three different starting states:

* a brand-new empty database,
* an existing single-user `data/app.db` written by the pre-V3 dashboard,
* a database already on the current schema (the common case — a no-op).

`create_all` covers the first and third. The second needs real work, because
the old `watchlist` and `notifications` tables predate user accounts: they have
no `user_id`, and `watchlist` carries a `UNIQUE(person_id)` constraint that is
wrong once more than one person can follow the same researcher.

Rather than guess an owner for that data (there are no users yet at migration
time) it is parked in `legacy_*_import` holding tables and handed to the first
account that signs up — which, on a local single-user install, is the person
whose data it was. If nobody ever signs up, nothing is destroyed.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect

from db.engine import db_conn, engine, execute, rows
from db.schema import metadata

log = logging.getLogger("helix.db")

LEGACY_WATCHLIST = "legacy_watchlist_import"
LEGACY_NOTIFICATIONS = "legacy_notifications_import"


def _table_columns(table_name: str) -> set[str]:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _park_legacy_tables() -> None:
    """Rename pre-user-accounts tables aside so create_all can build the new
    shape. Must run BEFORE create_all."""
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    for live, parked in (("watchlist", LEGACY_WATCHLIST), ("notifications", LEGACY_NOTIFICATIONS)):
        if live not in existing:
            continue
        if "user_id" in _table_columns(live):
            continue  # already migrated
        if parked in existing:
            # A previous run parked data that has not been claimed yet. Leave
            # it alone and drop the stale live table instead of stacking up
            # holding tables.
            log.warning("Dropping stale %s — unclaimed %s already exists", live, parked)
            with db_conn() as conn:
                execute(conn, f"DROP TABLE {live}")
            continue

        log.info("Migrating legacy %s -> %s (awaiting first account)", live, parked)
        with db_conn() as conn:
            execute(conn, f"ALTER TABLE {live} RENAME TO {parked}")


def _add_missing_columns() -> None:
    """Additive forward migration: any column present in the schema definition
    but missing from the live table is added. Runs AFTER create_all, so it only
    ever sees tables that already existed with an older column set."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        live_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in live_columns:
                continue
            if column.primary_key:
                # Can't retrofit a primary key with ALTER TABLE; that needs a
                # rebuild, which we only do for the known legacy cases above.
                log.warning("Cannot add primary key column %s.%s", table.name, column.name)
                continue

            ddl_type = column.type.compile(engine.dialect)
            clause = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl_type}"
            if column.server_default is not None:
                clause += f" DEFAULT {column.server_default.arg}"
            elif not column.nullable:
                # SQLite refuses a NOT NULL column with no default on a table
                # that already has rows. Add it nullable; the app writes the
                # value on every insert anyway.
                pass
            log.info("Adding missing column %s.%s", table.name, column.name)
            with db_conn() as conn:
                execute(conn, clause)


def init_db() -> None:
    """Create or upgrade the schema. Safe to call on every boot."""
    _park_legacy_tables()
    metadata.create_all(engine)
    _add_missing_columns()


def has_unclaimed_legacy_data() -> bool:
    inspector = inspect(engine)
    return bool({LEGACY_WATCHLIST, LEGACY_NOTIFICATIONS} & set(inspector.get_table_names()))


def claim_legacy_data(user_id: int) -> dict:
    """Hand parked pre-V3 data to `user_id` and drop the holding tables.

    Called once, for the first account created on an upgraded install.
    """
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    claimed = {"watchlist": 0, "notifications": 0}

    if LEGACY_WATCHLIST in existing:
        with db_conn() as conn:
            legacy = rows(conn, f"SELECT * FROM {LEGACY_WATCHLIST}")
            for entry in legacy:
                execute(
                    conn,
                    """
                    INSERT INTO watchlist
                        (user_id, person_id, notes, tags, priority, status, reminder_date, followed_at)
                    VALUES
                        (:user_id, :person_id, :notes, :tags, :priority, :status, :reminder_date, :followed_at)
                    """,
                    {
                        "user_id": user_id,
                        "person_id": entry["person_id"],
                        "notes": entry.get("notes") or "",
                        "tags": entry.get("tags") or "",
                        "priority": entry.get("priority") or "medium",
                        "status": entry.get("status") or "new",
                        "reminder_date": entry.get("reminder_date") or "",
                        "followed_at": entry.get("followed_at") or "",
                    },
                )
            claimed["watchlist"] = len(legacy)
            execute(conn, f"DROP TABLE {LEGACY_WATCHLIST}")

    if LEGACY_NOTIFICATIONS in existing:
        with db_conn() as conn:
            legacy = rows(conn, f"SELECT * FROM {LEGACY_NOTIFICATIONS}")
            for entry in legacy:
                execute(
                    conn,
                    """
                    INSERT INTO notifications (user_id, type, title, message, link, created_at, read)
                    VALUES (:user_id, :type, :title, :message, '', :created_at, :read)
                    """,
                    {
                        "user_id": user_id,
                        "type": entry.get("type") or "system",
                        "title": entry.get("title") or "",
                        "message": entry.get("message") or "",
                        "created_at": entry.get("created_at") or "",
                        "read": bool(entry.get("read")),
                    },
                )
            claimed["notifications"] = len(legacy)
            execute(conn, f"DROP TABLE {LEGACY_NOTIFICATIONS}")

    if claimed["watchlist"] or claimed["notifications"]:
        log.info(
            "Claimed legacy data for user %s: %s watchlist entries, %s notifications",
            user_id, claimed["watchlist"], claimed["notifications"],
        )
    return claimed
