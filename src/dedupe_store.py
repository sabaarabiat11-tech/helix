"""Read/append the master CSV, and answer "have we already seen this person?"."""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.models import MASTER_CSV_HEADER, Person, normalize_linkedin_url

logger = logging.getLogger(__name__)


class MasterStore:
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self._seen_urls: set[str] = set()
        self._seen_name_company: set[tuple[str, str]] = set()
        self._existing_row_count = 0
        self._load()

    def _load(self) -> None:
        if not self.csv_path.exists():
            logger.info("No existing master CSV at %s — starting fresh.", self.csv_path)
            return
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._existing_row_count += 1
                url = row.get("LinkedIn URL", "")
                name = row.get("Name", "")
                company = row.get("Company", "")
                if url:
                    self._seen_urls.add(normalize_linkedin_url(url))
                if name and company:
                    self._seen_name_company.add((name.strip().lower(), company.strip().lower()))
        logger.info("Loaded %d existing people from %s", self._existing_row_count, self.csv_path)

    @property
    def existing_count(self) -> int:
        return self._existing_row_count

    def is_duplicate(self, person: Person) -> bool:
        if person.normalized_url() in self._seen_urls:
            return True
        if person.name_company_key() in self._seen_name_company:
            return True
        return False

    def register(self, person: Person) -> None:
        """Mark a person as seen without writing yet (used to dedupe within one run's
        candidate batch before anything is committed to disk)."""
        self._seen_urls.add(person.normalized_url())
        self._seen_name_company.add(person.name_company_key())

    def append(self, people: list[Person]) -> None:
        if not people:
            return
        is_new_file = not self.csv_path.exists()
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if is_new_file:
                writer.writerow(MASTER_CSV_HEADER)
            for p in people:
                writer.writerow(p.as_csv_row())
        logger.info("Appended %d new people to %s", len(people), self.csv_path)
