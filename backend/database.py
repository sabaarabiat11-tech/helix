"""Pipeline ⇄ application bridge.

The discovery pipeline (src/, run.py, start.py) writes an append-only
`data/linkedin_master.csv` and knows nothing about this application. This
module mirrors that CSV *into* the database after every run, and can export the
database back out to CSV on demand. Those are the only two places CSV and the
application meet.

The database is the source of truth for everything the product reads and
writes. Nothing here ever writes back to `linkedin_master.csv`.

Schema definition and connection handling live in `db/`; this module only owns
the CSV bridge and the `meta` key/value helpers that go with it.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from db import db_conn, execute, init_db, row, rows, scalar

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTER_CSV = PROJECT_ROOT / "data" / "linkedin_master.csv"

# The pipeline's master CSV has no "Source" column (by design — see
# src/models.py, which deliberately keeps `source` as a Person attribute that's
# only used for logging/reporting, not persisted). Rather than touch pipeline
# code, we infer a human-readable source category from the `Reason` text each
# source class already writes — those strings are stable enough (unchanged
# across the SearXNG/GitHub/company_pages source modules) to pattern-match
# reliably.
SOURCE_PATTERNS: list[tuple[str, str]] = [
    (r"local SearXNG", "SearXNG (local)"),
    (r"\bSearXNG\b", "SearXNG"),
    (r"GitHub contributor", "GitHub"),
    (r"public team page", "Company Page"),
    (r"Google Scholar author", "Google Scholar"),
    (r"Brave Search", "Brave Search (legacy)"),
    (r"Google Search", "Google Search (legacy)"),
]


def infer_source(reason: str) -> str:
    for pattern, label in SOURCE_PATTERNS:
        if re.search(pattern, reason, re.IGNORECASE):
            return label
    return "Manual Research"


def get_meta(key: str) -> str | None:
    with db_conn() as conn:
        result = row(conn, "SELECT value FROM meta WHERE key = :key", {"key": key})
    return result["value"] if result else None


def set_meta(key: str, value: str) -> None:
    with db_conn() as conn:
        _set_meta(conn, key, value)


def _set_meta(conn, key: str, value: str) -> None:
    """Portable upsert. ON CONFLICT ... DO UPDATE is supported by both SQLite
    (3.24+) and PostgreSQL (9.5+), so one statement covers both dialects."""
    execute(
        conn,
        "INSERT INTO meta (key, value) VALUES (:key, :value) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        {"key": key, "value": value},
    )


def sync_from_csv(force: bool = False) -> dict:
    """Upsert every row from linkedin_master.csv into the database.

    Cheap no-op if the CSV hasn't changed since the last sync (tracked by
    mtime), unless force=True. Existing rows are updated in place (matched by
    linkedin_url) so ids stay stable; nothing is ever deleted here even if a
    row somehow disappeared from the CSV, since the CSV is append-only by
    design.
    """
    init_db()

    if not MASTER_CSV.exists():
        return {
            "synced": False,
            "reason": "linkedin_master.csv does not exist yet",
            "rows": 0,
            "new_people": [],
            "new_companies": [],
        }

    csv_mtime = str(MASTER_CSV.stat().st_mtime)

    with db_conn() as conn:
        last = row(conn, "SELECT value FROM meta WHERE key = 'csv_mtime'")
        if not force and last and last["value"] == csv_mtime:
            count = scalar(conn, "SELECT COUNT(*) FROM people")
            return {
                "synced": False,
                "reason": "unchanged",
                "rows": count,
                "new_people": [],
                "new_companies": [],
            }

        existing_urls = {
            r["linkedin_url"] for r in rows(conn, "SELECT linkedin_url FROM people")
        }
        existing_companies = {
            r["company"] for r in rows(conn, "SELECT DISTINCT company FROM people")
        }

        upserted = 0
        new_people: list[dict] = []

        with open(MASTER_CSV, newline="", encoding="utf-8") as f:
            for record in csv.DictReader(f):
                name = (record.get("Name") or "").strip()
                linkedin_url = (record.get("LinkedIn URL") or "").strip()
                if not name or not linkedin_url:
                    continue

                payload = {
                    "name": name,
                    "title": (record.get("Title") or "").strip(),
                    "company": (record.get("Company") or "").strip(),
                    "linkedin_url": linkedin_url,
                    "location": (record.get("Location") or "").strip(),
                    "reason": (record.get("Reason") or "").strip(),
                    "discovery_date": (record.get("Discovery Date") or "").strip(),
                }
                payload["source"] = infer_source(payload["reason"])

                if linkedin_url not in existing_urls:
                    new_people.append(
                        {"name": name, "company": payload["company"], "title": payload["title"]}
                    )

                execute(
                    conn,
                    """
                    INSERT INTO people
                        (name, title, company, linkedin_url, location, reason, discovery_date, source)
                    VALUES
                        (:name, :title, :company, :linkedin_url, :location, :reason, :discovery_date, :source)
                    ON CONFLICT(linkedin_url) DO UPDATE SET
                        name           = excluded.name,
                        title          = excluded.title,
                        company        = excluded.company,
                        location       = excluded.location,
                        reason         = excluded.reason,
                        discovery_date = excluded.discovery_date,
                        source         = excluded.source
                    """,
                    payload,
                )
                upserted += 1

        new_companies = sorted({p["company"] for p in new_people} - existing_companies)

        _set_meta(conn, "csv_mtime", csv_mtime)
        count = scalar(conn, "SELECT COUNT(*) FROM people")

    return {
        "synced": True,
        "rows": count,
        "upserted": upserted,
        "new_people": new_people,
        "new_companies": new_companies,
    }


def export_to_csv(dest_path: Path) -> int:
    """On-demand export of the current `people` table to a CSV file. This is the
    only CSV-writing path in the application — a read of the database, never a
    write back to linkedin_master.csv."""
    with db_conn() as conn:
        records = rows(
            conn,
            "SELECT name, title, company, linkedin_url, location, reason, discovery_date, source "
            "FROM people ORDER BY id",
        )

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["Name", "Title", "Company", "LinkedIn URL", "Location", "Reason", "Discovery Date", "Source"]
        )
        for record in records:
            writer.writerow(
                [
                    record["name"], record["title"], record["company"], record["linkedin_url"],
                    record["location"], record["reason"], record["discovery_date"], record["source"],
                ]
            )
    return len(records)
