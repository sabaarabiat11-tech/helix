"""Scheduler, admin endpoints, and the SQLite→PostgreSQL transfer."""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import UTC
from pathlib import Path

# --- Scheduler --------------------------------------------------------------

def test_daily_claim_is_idempotent(client, registered):
    """The claim is what stops a redeploy at 08:05 from sending everyone a
    second copy of the morning digest."""
    from db import today_iso
    from services import scheduler_service

    registered()
    today = today_iso()
    key = "test_claim_idempotent"

    assert scheduler_service._claim(key, today) is True
    assert scheduler_service._claim(key, today) is False
    # A new day is claimable again.
    assert scheduler_service._claim(key, "2099-01-01") is True


def test_forced_digest_run_sends(client, registered):
    from services import scheduler_service, user_service

    _, user, _ = registered()
    user_service.update_preferences(user["id"], digest_frequency="daily")

    summaries = scheduler_service.run_due_digests(force="daily")
    assert summaries, "a forced run must produce a summary"
    assert summaries[0]["frequency"] == "daily"
    assert summaries[0]["sent"] >= 1
    assert summaries[0]["failed"] == 0


def test_scheduler_respects_the_configured_hour(client, registered):
    """Before the scheduled hour nothing is due, so an early restart doesn't
    fire the day's send prematurely."""
    from datetime import datetime

    from config import settings
    from services import scheduler_service

    registered()
    too_early = datetime(2099, 6, 1, max(0, settings.scheduler_hour - 1), 0, tzinfo=UTC)
    assert scheduler_service._due("daily", too_early) is False

    at_hour = datetime(2099, 6, 1, settings.scheduler_hour, 5, tzinfo=UTC)
    assert scheduler_service._due("daily", at_hour) is True


# --- Admin ------------------------------------------------------------------

def test_admin_status_requires_an_administrator(client, registered):
    # The first account created in the session is the admin; a later one isn't.
    registered("firstadmin")
    non_admin_auth, user, _ = registered("regular")
    assert user["is_admin"] is False
    assert client.get("/api/admin/status", headers=non_admin_auth).status_code == 403


def test_admin_status_reports_configuration(client, registered):
    from services import user_service

    auth, user, _ = registered()
    # Promote so the check works regardless of creation order in the session.
    from db import db_conn, execute
    with db_conn() as conn:
        execute(conn, "UPDATE users SET is_admin = :a WHERE id = :i", {"a": True, "i": user["id"]})

    body = client.get("/api/admin/status", headers=auth).json()
    for key in ("environment", "database", "email", "cookies", "urls", "scheduler", "warnings"):
        assert key in body
    assert body["database"]["dialect"] in {"sqlite", "postgresql"}
    assert isinstance(body["warnings"], list)
    assert user_service.count_users() >= 1


# --- SQLite -> PostgreSQL transfer ------------------------------------------

def test_transfer_coerces_sqlite_integer_booleans():
    """SQLite stores booleans as 0/1 integers, which PostgreSQL's BOOLEAN
    columns reject outright — that aborted the whole transfer before this was
    handled."""
    from db.transfer import _coerce_row

    row = {"id": 1, "email": "a@b.com", "is_admin": 1, "email_verified": 0, "is_active": 1}
    coerced = _coerce_row("users", row)

    assert coerced["is_admin"] is True
    assert coerced["email_verified"] is False
    assert coerced["is_active"] is True
    # Non-boolean columns are untouched.
    assert coerced["id"] == 1
    assert coerced["email"] == "a@b.com"


def test_transfer_reads_a_real_sqlite_file():
    """End-to-end read side of the transfer, against a genuine SQLite file."""
    from db.transfer import transfer

    tmp = Path(tempfile.mkdtemp()) / "source.db"
    conn = sqlite3.connect(tmp)
    conn.executescript(
        """
        CREATE TABLE people (
            id INTEGER PRIMARY KEY, name TEXT, title TEXT, company TEXT,
            linkedin_url TEXT, location TEXT, reason TEXT,
            discovery_date TEXT, source TEXT
        );
        INSERT INTO people VALUES
            (1,'A','t','c','https://linkedin.com/in/a','','','2026-01-01','SearXNG'),
            (2,'B','t','c','https://linkedin.com/in/b','','','2026-01-02','GitHub');
        """
    )
    conn.commit()
    conn.close()

    result = transfer(tmp, dry_run=True)
    assert result["dry_run"] is True
    assert result["tables"]["people"] == 2


def test_auto_migrate_skips_when_target_has_data(client, registered):
    """Auto-migration must never merge into a database that already holds real
    rows — the guard that makes running it on every boot safe."""
    from db.transfer import maybe_auto_migrate, target_is_empty

    registered()  # the target now has a user
    assert target_is_empty() is False
    assert maybe_auto_migrate(Path("definitely-does-not-exist.db")) is None
