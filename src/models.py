"""Core data model + normalization helpers used for deduplication."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Person:
    name: str
    title: str
    company: str
    linkedin_url: str
    location: str = ""
    reason: str = ""
    discovery_date: str = field(default_factory=lambda: date.today().isoformat())
    source: str = ""  # not written to the master CSV, kept for logging/report only

    def normalized_url(self) -> str:
        return normalize_linkedin_url(self.linkedin_url)

    def name_company_key(self) -> tuple[str, str]:
        return (self.name.strip().lower(), self.company.strip().lower())

    def as_csv_row(self) -> list[str]:
        return [
            self.name.strip(),
            self.title.strip(),
            self.company.strip(),
            self.linkedin_url.strip(),
            self.location.strip(),
            self.reason.strip(),
            self.discovery_date,
        ]


MASTER_CSV_HEADER = [
    "Name",
    "Title",
    "Company",
    "LinkedIn URL",
    "Location",
    "Reason",
    "Discovery Date",
]


def normalize_linkedin_url(url: str) -> str:
    """Collapse protocol/www/locale-subdomain/trailing-slash/query differences
    so the same profile isn't counted twice (e.g. uk.linkedin.com vs www.linkedin.com)."""
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^[a-z]{2,3}\.linkedin\.com", "linkedin.com", u)
    u = re.sub(r"^www\.linkedin\.com", "linkedin.com", u)
    u = u.split("?")[0].rstrip("/")
    return u


def is_valid_linkedin_profile_url(url: str) -> bool:
    """Only accept real linkedin.com/in/... profile URLs — never a guessed/constructed one
    (callers are responsible for only passing URLs they actually observed, e.g. in a
    search result); this is just a sanity-check on shape."""
    if not url:
        return False
    return bool(re.match(r"^https?://([a-z]{2,3}\.)?(www\.)?linkedin\.com/in/[^/?#]+/?([a-z]{2}/?)?$", url.strip(), re.I))
