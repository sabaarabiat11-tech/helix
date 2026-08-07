from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from database import sync_from_csv
from db import db_conn, rows

router = APIRouter(prefix="/api/companies", tags=["companies"])

SORTABLE = {"name": "company", "count": "n", "latest": "latest_date"}


@router.get("")
def list_companies(
    search: str = Query(""),
    sort_by: str = Query("count"),
    sort_dir: str = Query("desc"),
):
    sync_from_csv()

    sort_col = SORTABLE.get(sort_by, "n")
    sort_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"

    where = ""
    params: dict = {}
    if search:
        where = "WHERE company LIKE :search"
        params["search"] = f"%{search}%"

    with db_conn() as conn:
        return rows(
            conn,
            f"""
            SELECT company, COUNT(*) AS n, MAX(discovery_date) AS latest_date
            FROM people
            {where}
            GROUP BY company
            ORDER BY {sort_col} {sort_dir}
            """,
            params,
        )


@router.get("/{company_name}")
def get_company_detail(company_name: str):
    sync_from_csv()

    params = {"company": company_name}
    with db_conn() as conn:
        people = rows(
            conn,
            """
            SELECT id, name, title, company, linkedin_url, location, reason, discovery_date, source
            FROM people
            WHERE company = :company
            ORDER BY discovery_date DESC
            """,
            params,
        )
        title_breakdown = rows(
            conn,
            "SELECT title, COUNT(*) AS n FROM people WHERE company = :company GROUP BY title ORDER BY n DESC",
            params,
        )
        source_breakdown = rows(
            conn,
            "SELECT source, COUNT(*) AS n FROM people WHERE company = :company GROUP BY source ORDER BY n DESC",
            params,
        )

    if not people:
        raise HTTPException(status_code=404, detail=f"No people found for company '{company_name}'")

    return {
        "company": company_name,
        "total": len(people),
        "people": people,
        "title_breakdown": title_breakdown,
        "source_breakdown": source_breakdown,
    }
