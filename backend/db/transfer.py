"""One-way data transfer from a SQLite database into the live database.

Switching `DATABASE_URL` to PostgreSQL creates an empty schema — correct, but
it silently abandons whatever was in SQLite. This copies it across so the
switch preserves accounts, watchlists and the discovery corpus instead of
starting from nothing.

Runs automatically at startup when it is safe to do so (see
`maybe_auto_migrate`), and can be run by hand:

    python -m db.transfer --from data/app.db
    python -m db.transfer --from data/app.db --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import Boolean, create_engine, inspect, text

from db.engine import db_conn, engine
from db.migrations import init_db
from db.schema import metadata

log = logging.getLogger("helix.transfer")

# Parents before children: every row's foreign keys must already exist.
TRANSFER_ORDER = [
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


def _source_engine(sqlite_path: Path):
    return create_engine(f"sqlite:///{sqlite_path.as_posix()}", future=True)


def _coerce_row(table_name: str, row: dict) -> dict:
    """Convert SQLite's value representation to what the destination expects.

    SQLite has no boolean type and stores 0/1 integers. PostgreSQL's BOOLEAN
    columns reject those outright ("column is of type boolean but expression
    is of type integer"), which aborts the whole transfer partway through —
    so every Boolean column is converted explicitly, driven by the schema
    rather than a hand-maintained list of column names.
    """
    table = metadata.tables[table_name]
    coerced = dict(row)
    for column in table.columns:
        if isinstance(column.type, Boolean) and column.name in coerced:
            value = coerced[column.name]
            if value is not None:
                coerced[column.name] = bool(value)
    return coerced


def target_is_empty() -> bool:
    """True when the live database has no users and no discovery data.

    Both are checked because either one alone is ambiguous: a fresh deploy has
    people (seeded) but no users, and a brand-new install has neither.
    Migrating into a database that already holds real rows would duplicate or
    collide, so this is the guard that makes auto-migration safe.
    """
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    if "users" not in existing or "people" not in existing:
        return True
    with db_conn() as conn:
        users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
        people = conn.execute(text("SELECT COUNT(*) FROM people")).scalar() or 0
    return users == 0 and people == 0


def _reset_sequences() -> None:
    """Advance PostgreSQL identity sequences past the copied ids.

    Copying explicit primary keys does not move the sequence, so without this
    the very next INSERT reuses id 1 and fails on the primary key. SQLite has
    no equivalent and needs nothing.
    """
    if engine.dialect.name != "postgresql":
        return

    with db_conn() as conn:
        for table in TRANSFER_ORDER:
            # Only tables with a generated integer `id` have a sequence.
            # `meta` keys on text and `user_preferences` on user_id, so asking
            # Postgres for MAX(id) on either is an error, not a no-op.
            columns = metadata.tables[table].columns
            if "id" not in columns or not columns["id"].primary_key:
                continue
            conn.execute(
                text(
                    "SELECT setval("
                    "  pg_get_serial_sequence(:table, 'id'),"
                    "  COALESCE((SELECT MAX(id) FROM " + table + "), 0) + 1,"
                    "  false"
                    ") WHERE pg_get_serial_sequence(:table, 'id') IS NOT NULL"
                ),
                {"table": table},
            )
    log.info("PostgreSQL id sequences advanced past the imported rows")


def transfer(sqlite_path: Path, dry_run: bool = False) -> dict:
    """Copy every table from `sqlite_path` into the live database."""
    if not sqlite_path.exists():
        raise FileNotFoundError(f"No SQLite database at {sqlite_path}")

    init_db()

    source = _source_engine(sqlite_path)
    source_tables = set(inspect(source).get_table_names())
    copied: dict[str, int] = {}

    try:
        with source.connect() as src:
            for table_name in TRANSFER_ORDER:
                if table_name not in source_tables:
                    continue

                table = metadata.tables[table_name]
                # Only columns the destination schema still has — an older
                # SQLite file may predate a column, or carry one since removed.
                src_columns = {c["name"] for c in inspect(source).get_columns(table_name)}
                columns = [c.name for c in table.columns if c.name in src_columns]
                if not columns:
                    continue

                rows = src.execute(
                    text(f"SELECT {', '.join(columns)} FROM {table_name}")
                ).mappings().all()
                if not rows:
                    copied[table_name] = 0
                    continue

                if dry_run:
                    copied[table_name] = len(rows)
                    continue

                placeholders = ", ".join(f":{c}" for c in columns)
                insert_sql = (
                    f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
                )
                with db_conn() as dest:
                    for row in rows:
                        dest.execute(text(insert_sql), _coerce_row(table_name, row))
                copied[table_name] = len(rows)
    finally:
        # Runs even when a table above raised. A partial transfer that left the
        # sequences at 1 would make the next INSERT collide with a copied id —
        # a far more confusing failure than whatever actually went wrong here.
        if not dry_run:
            _reset_sequences()

    total = sum(copied.values())
    log.info("Transferred %s rows from %s: %s", total, sqlite_path.name, copied)
    return {"source": str(sqlite_path), "total": total, "tables": copied, "dry_run": dry_run}


def maybe_auto_migrate(sqlite_path: Path) -> dict | None:
    """Import a leftover SQLite database at startup, when it is clearly right.

    Deliberately conservative — all four conditions must hold:

      * the live database is PostgreSQL (nothing to do when already SQLite),
      * the live database is empty (never merge into real data),
      * a SQLite file exists locally,
      * it actually contains rows.

    That makes the common upgrade path — set DATABASE_URL, redeploy — carry the
    old data across with no command to run, while being a no-op on every
    subsequent boot.
    """
    if engine.dialect.name != "postgresql":
        return None
    if not sqlite_path.exists():
        return None
    if not target_is_empty():
        log.debug("Target database already has data; skipping SQLite import")
        return None

    try:
        source = _source_engine(sqlite_path)
        tables = set(inspect(source).get_table_names())
        if not tables:
            return None
        with source.connect() as src:
            has_rows = any(
                (src.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() or 0) > 0
                for t in tables
                if t in metadata.tables
            )
        if not has_rows:
            return None

        log.info("Empty PostgreSQL database and a populated %s — importing", sqlite_path)
        return transfer(sqlite_path)
    except Exception:
        # A failed import must not stop the service from starting; the app
        # works fine on an empty database, and the traceback is in the log.
        log.exception("Automatic SQLite import failed; continuing with an empty database")
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy a SQLite database into the live database.")
    parser.add_argument("--from", dest="source", default="data/app.db", help="Path to the SQLite file")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be copied")
    parser.add_argument("--force", action="store_true", help="Copy even if the target is not empty")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")

    path = Path(args.source)
    if not args.force and not args.dry_run and not target_is_empty():
        print(
            "Target database is not empty. Re-run with --force if you are sure "
            "you want to add these rows on top.",
            file=sys.stderr,
        )
        return 1

    result = transfer(path, dry_run=args.dry_run)
    print(f"{'Would copy' if args.dry_run else 'Copied'} {result['total']} rows")
    for table, count in result["tables"].items():
        if count:
            print(f"  {count:6}  {table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
