"""Database engine and connection helpers.

Everything in the application talks to the database through this module. It is
backed by SQLAlchemy Core (not the ORM) so the existing hand-written SQL keeps
working unchanged in shape, while the dialect — SQLite today, PostgreSQL in
production — becomes a single environment variable.

Two rules make the SQL portable and are enforced by convention across the
codebase:

1. Bind parameters are always **named** (``:user_id``), never positional
   ``?`` — the qmark style is SQLite-specific.
2. Date/time arithmetic happens in **Python**, never in SQL — no ``strftime``,
   ``julianday`` or ``NOW()``, whose names and semantics differ per dialect.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, create_engine, event, text
from sqlalchemy.engine import Connection, Engine

from config import settings
from db.schema import metadata

# Raw text() queries bypass SQLAlchemy's result type coercion, so each driver's
# native representation leaks through: SQLite has no boolean type and hands
# back 0/1, while psycopg returns real bools. Without normalizing, the same
# endpoint would serialize `"email_verified": 1` on SQLite and
# `"email_verified": true` on PostgreSQL.
#
# The set is derived from the schema itself rather than hand-listed, so a new
# Boolean column is covered the moment it is declared.
BOOLEAN_COLUMNS: frozenset[str] = frozenset(
    column.name
    for table in metadata.tables.values()
    for column in table.columns
    if isinstance(column.type, Boolean)
)


def _normalize(record: Mapping[str, Any]) -> dict:
    return {
        key: (bool(value) if key in BOOLEAN_COLUMNS and value is not None else value)
        for key, value in record.items()
    }


def _build_engine() -> Engine:
    url = settings.database_url

    if url.startswith("sqlite"):
        # Ensure the containing directory exists before SQLite tries to open
        # the file, otherwise a fresh checkout fails on first boot.
        path_part = url.split("///", 1)[-1]
        if path_part and path_part != ":memory:":
            Path(path_part).parent.mkdir(parents=True, exist_ok=True)

        engine = create_engine(
            url,
            # FastAPI serves requests from a thread pool; SQLite's default
            # same-thread check would reject those connections.
            connect_args={"check_same_thread": False},
            future=True,
        )

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - driver hook
            cursor = dbapi_conn.cursor()
            # ON DELETE CASCADE is off by default in SQLite and our schema
            # relies on it for per-user cleanup.
            cursor.execute("PRAGMA foreign_keys = ON")
            # WAL lets the digest worker read while the API writes.
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.close()

        return engine

    # PostgreSQL (or anything else SQLAlchemy speaks). pool_pre_ping survives
    # connections dropped by a proxy or a database restart, which is the
    # single most common source of 500s in a hosted deployment.
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        future=True,
    )


engine: Engine = _build_engine()


@contextmanager
def db_conn() -> Iterator[Connection]:
    """A transactional connection. Commits on clean exit, rolls back on error."""
    with engine.begin() as conn:
        yield conn


def rows(conn: Connection, sql: str, params: Mapping[str, Any] | None = None) -> list[dict]:
    """Run a query and return every row as a plain dict, with boolean columns
    normalized to real bools regardless of dialect."""
    result = conn.execute(text(sql), dict(params or {}))
    return [_normalize(m) for m in result.mappings().all()]


def row(conn: Connection, sql: str, params: Mapping[str, Any] | None = None) -> dict | None:
    """Run a query and return the first row as a dict, or None."""
    result = conn.execute(text(sql), dict(params or {}))
    first = result.mappings().first()
    return _normalize(first) if first else None


def scalar(conn: Connection, sql: str, params: Mapping[str, Any] | None = None) -> Any:
    """Run a query and return the first column of the first row."""
    return conn.execute(text(sql), dict(params or {})).scalar()


def execute(conn: Connection, sql: str, params: Mapping[str, Any] | None = None):
    """Run a statement that isn't a SELECT. Returns the SQLAlchemy result so
    callers can read ``.rowcount``."""
    return conn.execute(text(sql), dict(params or {}))


def insert_returning_id(conn: Connection, sql: str, params: Mapping[str, Any] | None = None) -> int:
    """INSERT and get the new primary key back on either dialect.

    ``lastrowid`` is a SQLite/MySQL concept; PostgreSQL needs an explicit
    ``RETURNING id``. Callers write plain INSERTs and this adds whichever the
    current dialect needs.
    """
    if engine.dialect.name == "postgresql":
        result = conn.execute(text(f"{sql.rstrip().rstrip(';')} RETURNING id"), dict(params or {}))
        return int(result.scalar_one())
    result = conn.execute(text(sql), dict(params or {}))
    return int(result.lastrowid)
