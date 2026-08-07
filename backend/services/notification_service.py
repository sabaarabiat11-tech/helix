"""In-app notification center.

Notifications belong to a user. Pipeline-level events (a run finished, a new
company appeared) are system-wide facts, so they fan out to every user who has
opted in to that category — which is why the notify_* helpers take no user
argument and consult preferences themselves.
"""
from __future__ import annotations

import logging

from db import db_conn, execute, insert_returning_id, rows, scalar, utcnow_iso
from services import user_service

log = logging.getLogger("helix.notifications")

# Notification type -> the preference flag that gates it. A type absent from
# this map is always delivered (it's a direct consequence of something the user
# did, not a broadcast).
PREFERENCE_BY_TYPE = {
    "discovery": "notify_new_recommendations",
    "company": "notify_new_companies",
    "pipeline": "notify_pipeline_complete",
    "report": "notify_weekly_report",
    "insight": "notify_ai_insights",
}


def list_notifications(user_id: int, unread_only: bool = False, limit: int = 50) -> list[dict]:
    where = "WHERE user_id = :user_id" + (" AND read = :unread" if unread_only else "")
    params = {"user_id": user_id, "limit": limit}
    if unread_only:
        params["unread"] = False
    with db_conn() as conn:
        return rows(
            conn,
            f"SELECT id, type, title, message, link, created_at, read FROM notifications "
            f"{where} ORDER BY created_at DESC LIMIT :limit",
            params,
        )


def unread_count(user_id: int) -> int:
    with db_conn() as conn:
        return scalar(
            conn,
            "SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND read = :unread",
            {"user_id": user_id, "unread": False},
        )


def create(user_id: int, type_: str, title: str, message: str, link: str = "") -> dict:
    with db_conn() as conn:
        notif_id = insert_returning_id(
            conn,
            "INSERT INTO notifications (user_id, type, title, message, link, created_at, read) "
            "VALUES (:user_id, :type, :title, :message, :link, :created_at, :read)",
            {
                "user_id": user_id,
                "type": type_,
                "title": title,
                "message": message,
                "link": link,
                "created_at": utcnow_iso(),
                "read": False,
            },
        )
    return {"id": notif_id, "type": type_, "title": title, "message": message, "link": link}


def mark_read(user_id: int, notification_id: int) -> None:
    with db_conn() as conn:
        execute(
            conn,
            "UPDATE notifications SET read = :read WHERE id = :id AND user_id = :user_id",
            {"read": True, "id": notification_id, "user_id": user_id},
        )


def mark_all_read(user_id: int) -> None:
    with db_conn() as conn:
        execute(
            conn,
            "UPDATE notifications SET read = :read WHERE user_id = :user_id AND read = :unread",
            {"read": True, "user_id": user_id, "unread": False},
        )


def broadcast(type_: str, title: str, message: str, link: str = "") -> int:
    """Deliver a system event to every active user who wants that category.

    Returns how many users received it.
    """
    pref_key = PREFERENCE_BY_TYPE.get(type_)
    delivered = 0
    for user in user_service.list_active_users():
        if pref_key:
            prefs = user_service.get_preferences(user["id"])
            if not prefs.get(pref_key, True):
                continue
        create(user["id"], type_, title, message, link)
        delivered += 1
    return delivered


def notify_run_completed(sync_result: dict, new_people_count: int) -> None:
    """Called once by the run router right after a pipeline run finishes and
    the CSV has been synced. Fans the resulting events out to every opted-in
    user."""
    if new_people_count > 0:
        noun = "researcher" if new_people_count == 1 else "researchers"
        broadcast(
            "discovery",
            f"{new_people_count} new {noun} found",
            f"The latest run added {new_people_count} new {noun} to the database.",
            link="/discoveries",
        )

    for company in sync_result.get("new_companies") or []:
        broadcast(
            "company",
            "New company detected",
            f"First discovery at {company}.",
            link=f"/companies/{company}",
        )

    person_noun = "person" if new_people_count == 1 else "people"
    broadcast(
        "pipeline",
        "Pipeline completed",
        f"Discovery run finished — {new_people_count} new {person_noun} added.",
        link="/discoveries",
    )


def notify_report_ready(filename: str) -> None:
    broadcast("report", "Weekly report ready", f"{filename} is ready to view.", link="/reports")
