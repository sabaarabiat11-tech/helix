"""Watchlist business logic — follow/unfollow people, manage notes, tags,
priority, status, and reminders.

Every function is scoped to a `user_id`. Two users following the same
researcher keep entirely separate notes and status; neither can read or modify
the other's entry. Routers stay thin — all SQL lives here.
"""
from __future__ import annotations

from db import db_conn, execute, row, rows, utcnow_iso

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_STATUSES = {"new", "contacted", "responded", "archived"}


def list_watchlist(user_id: int) -> list[dict]:
    with db_conn() as conn:
        return rows(
            conn,
            """
            SELECT w.id AS watchlist_id, w.notes, w.tags, w.priority, w.status,
                   w.reminder_date, w.followed_at,
                   p.id AS person_id, p.name, p.title, p.company, p.linkedin_url,
                   p.location, p.discovery_date, p.source
            FROM watchlist w
            JOIN people p ON p.id = w.person_id
            WHERE w.user_id = :user_id
            ORDER BY w.followed_at DESC
            """,
            {"user_id": user_id},
        )


def followed_person_ids(user_id: int) -> set[int]:
    with db_conn() as conn:
        found = rows(
            conn, "SELECT person_id FROM watchlist WHERE user_id = :user_id", {"user_id": user_id}
        )
    return {r["person_id"] for r in found}


def is_following(user_id: int, person_id: int) -> bool:
    with db_conn() as conn:
        found = row(
            conn,
            "SELECT 1 AS hit FROM watchlist WHERE user_id = :user_id AND person_id = :person_id",
            {"user_id": user_id, "person_id": person_id},
        )
    return found is not None


def follow(user_id: int, person_id: int) -> dict:
    with db_conn() as conn:
        person = row(conn, "SELECT id FROM people WHERE id = :id", {"id": person_id})
        if not person:
            raise ValueError(f"No person with id {person_id}")
        execute(
            conn,
            "INSERT INTO watchlist (user_id, person_id, followed_at) "
            "VALUES (:user_id, :person_id, :followed_at) "
            "ON CONFLICT(user_id, person_id) DO NOTHING",
            {"user_id": user_id, "person_id": person_id, "followed_at": utcnow_iso()},
        )
    return {"person_id": person_id, "following": True}


def unfollow(user_id: int, person_id: int) -> dict:
    with db_conn() as conn:
        execute(
            conn,
            "DELETE FROM watchlist WHERE user_id = :user_id AND person_id = :person_id",
            {"user_id": user_id, "person_id": person_id},
        )
    return {"person_id": person_id, "following": False}


def update_entry(user_id: int, person_id: int, **fields) -> dict:
    allowed = {"notes", "tags", "priority", "status", "reminder_date"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}

    if "priority" in updates and updates["priority"] not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority: {updates['priority']}")
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {updates['status']}")

    if not updates:
        return {"person_id": person_id, "updated": False}

    set_clause = ", ".join(f"{key} = :{key}" for key in updates)
    with db_conn() as conn:
        result = execute(
            conn,
            f"UPDATE watchlist SET {set_clause} WHERE user_id = :user_id AND person_id = :person_id",
            {**updates, "user_id": user_id, "person_id": person_id},
        )
        if result.rowcount == 0:
            raise ValueError(f"Person {person_id} is not on your watchlist")

    return {"person_id": person_id, "updated": True}


def due_reminders(user_id: int, on_date: str) -> list[dict]:
    """Watchlist entries whose reminder falls on or before `on_date`
    (YYYY-MM-DD) and that haven't been archived — used by the digest email."""
    with db_conn() as conn:
        return rows(
            conn,
            """
            SELECT w.reminder_date, w.priority, w.status, w.notes,
                   p.id AS person_id, p.name, p.title, p.company, p.linkedin_url
            FROM watchlist w
            JOIN people p ON p.id = w.person_id
            WHERE w.user_id = :user_id
              AND w.reminder_date != ''
              AND w.reminder_date <= :on_date
              AND w.status != 'archived'
            ORDER BY w.reminder_date ASC
            """,
            {"user_id": user_id, "on_date": on_date},
        )
