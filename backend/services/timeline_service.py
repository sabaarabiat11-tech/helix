"""Activity timeline — buckets discoveries into Today / Yesterday / This
Week / Last Month / Earlier."""
from __future__ import annotations

from datetime import date, timedelta

from db import db_conn, rows

BUCKET_ORDER = ["Today", "Yesterday", "This Week", "Last Month", "Earlier"]


def _bucket_for(d: date, today: date) -> str:
    if d == today:
        return "Today"
    if d == today - timedelta(days=1):
        return "Yesterday"
    if d >= today - timedelta(days=7):
        return "This Week"
    if d >= today - timedelta(days=30):
        return "Last Month"
    return "Earlier"


def get_timeline() -> list[dict]:
    with db_conn() as conn:
        events = rows(
            conn,
            "SELECT id, name, title, company, linkedin_url, source, discovery_date "
            "FROM people ORDER BY discovery_date DESC, id DESC",
        )

    today = date.today()
    buckets: dict[str, list[dict]] = {b: [] for b in BUCKET_ORDER}

    for event in events:
        try:
            d = date.fromisoformat(event["discovery_date"])
        except (ValueError, TypeError):
            continue
        buckets[_bucket_for(d, today)].append(event)

    return [
        {"bucket": b, "count": len(buckets[b]), "events": buckets[b]}
        for b in BUCKET_ORDER
        if buckets[b]
    ]
