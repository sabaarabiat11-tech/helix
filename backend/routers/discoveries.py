from __future__ import annotations

from fastapi import APIRouter, Query

from database import sync_from_csv
from db import db_conn, rows, scalar

router = APIRouter(prefix="/api/discoveries", tags=["discoveries"])

SORTABLE_COLUMNS = {"discovery_date", "name", "company", "title", "source"}


@router.get("")
def list_discoveries(
    search: str = Query("", description="Matches name, company, or title"),
    company: str = Query("", description="Exact company filter"),
    source: str = Query("", description="Exact source filter"),
    date_from: str = Query("", description="ISO date, inclusive"),
    date_to: str = Query("", description="ISO date, inclusive"),
    sort_by: str = Query("discovery_date"),
    sort_dir: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=5000),  # high ceiling so the frontend's client-side
    # DataTable (sort/filter/column-visibility/export) can fetch the whole dataset at once —
    # this app's realistic scale (thousands of people, not millions) makes that fine.
):
    sync_from_csv()

    if sort_by not in SORTABLE_COLUMNS:
        sort_by = "discovery_date"
    sort_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"

    where: list[str] = []
    params: dict = {}

    if search:
        where.append("(name LIKE :search OR company LIKE :search OR title LIKE :search)")
        params["search"] = f"%{search}%"
    if company:
        where.append("company = :company")
        params["company"] = company
    if source:
        where.append("source = :source")
        params["source"] = source
    if date_from:
        where.append("discovery_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("discovery_date <= :date_to")
        params["date_to"] = date_to

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    with db_conn() as conn:
        total = scalar(conn, f"SELECT COUNT(*) FROM people {where_clause}", params)

        results = rows(
            conn,
            f"""
            SELECT id, name, title, company, linkedin_url, location, reason, discovery_date, source
            FROM people
            {where_clause}
            ORDER BY {sort_by} {sort_dir}, id DESC
            LIMIT :limit OFFSET :offset
            """,
            {**params, "limit": page_size, "offset": (page - 1) * page_size},
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": results,
    }


@router.get("/sources")
def list_sources():
    sync_from_csv()
    with db_conn() as conn:
        return rows(conn, "SELECT source, COUNT(*) AS n FROM people GROUP BY source ORDER BY n DESC")
