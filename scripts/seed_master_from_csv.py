#!/usr/bin/env python3
"""One-time bootstrap: import an existing curated CSV (e.g. the 500-person
research file) into data/linkedin_master.csv, so the weekly agent starts
already knowing about these people and only surfaces genuinely new ones.

Usage:
    python scripts/seed_master_from_csv.py <path-to-source-csv>

The source CSV is expected to have (at least) these columns, case-insensitive,
matching what earlier research produced:
    Name, Title, Company, LinkedIn URL, Location, Reason

Safe to re-run: it uses the same dedupe logic as the live pipeline, so
re-seeding from the same file (or an overlapping one) never creates duplicates.
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_settings
from src.dedupe_store import MasterStore
from src.models import Person, is_valid_linkedin_profile_url


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/seed_master_from_csv.py <path-to-source-csv>")
        return 1

    source_path = Path(sys.argv[1])
    if not source_path.exists():
        print(f"Source file not found: {source_path}")
        return 1

    settings = load_settings()
    store = MasterStore(settings.path("master_csv"))

    seed_date = date.today().isoformat()
    to_add: list[Person] = []
    skipped_dupe = 0
    skipped_invalid = 0

    with open(source_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # normalize header lookups (case-insensitive)
        fieldmap = {k.lower().strip(): k for k in reader.fieldnames or []}

        def get(row: dict, key: str) -> str:
            actual = fieldmap.get(key.lower())
            return (row.get(actual, "") if actual else "").strip()

        for row in reader:
            name = get(row, "Name")
            title = get(row, "Title")
            company = get(row, "Company")
            linkedin_url = get(row, "LinkedIn URL")
            location = get(row, "Location")
            reason = get(row, "Reason")

            if not (name and company and linkedin_url):
                skipped_invalid += 1
                continue
            if not is_valid_linkedin_profile_url(linkedin_url):
                skipped_invalid += 1
                continue

            person = Person(
                name=name,
                title=title,
                company=company,
                linkedin_url=linkedin_url,
                location=location,
                reason=reason or f"Previously identified as relevant to AI x Biology at {company}.",
                discovery_date=seed_date,
                source="seed_import",
            )

            if store.is_duplicate(person):
                skipped_dupe += 1
                continue

            store.register(person)
            to_add.append(person)

    store.append(to_add)

    print(f"Source rows read: {skipped_invalid + skipped_dupe + len(to_add)}")
    print(f"Skipped (missing/invalid data): {skipped_invalid}")
    print(f"Skipped (already in master CSV): {skipped_dupe}")
    print(f"Seeded into master CSV: {len(to_add)}")
    print(f"Master CSV total now: {store.existing_count + len(to_add)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
