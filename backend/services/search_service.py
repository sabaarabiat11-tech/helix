"""Global search across people, companies, and the signed-in user's watchlist.

People and companies come from the shared discovery corpus and are identical
for everyone; watchlist hits are scoped to the caller so one user's private
notes can never surface in another user's search.
"""
from __future__ import annotations

from db import db_conn, rows


def global_search(query: str, user_id: int | None = None, limit: int = 8) -> dict:
    params = {"q": f"%{query}%", "limit": limit}

    with db_conn() as conn:
        people = rows(
            conn,
            """
            SELECT id, name, title, company, linkedin_url
            FROM people
            WHERE name LIKE :q OR title LIKE :q
            ORDER BY discovery_date DESC
            LIMIT :limit
            """,
            params,
        )

        companies = rows(
            conn,
            "SELECT company, COUNT(*) AS n FROM people WHERE company LIKE :q "
            "GROUP BY company ORDER BY n DESC LIMIT :limit",
            params,
        )

        watchlist_hits = (
            rows(
                conn,
                """
                SELECT p.id, p.name, p.company, w.notes, w.tags
                FROM watchlist w
                JOIN people p ON p.id = w.person_id
                WHERE w.user_id = :user_id
                  AND (w.notes LIKE :q OR w.tags LIKE :q OR p.name LIKE :q)
                LIMIT :limit
                """,
                {**params, "user_id": user_id},
            )
            if user_id is not None
            else []
        )

    return {"people": people, "companies": companies, "watchlist": watchlist_hits}
