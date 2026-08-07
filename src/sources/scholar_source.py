"""Google Scholar discovery — OFF by default (see config.yaml).

Google Scholar has no official API. The `scholarly` package scrapes Scholar's
public search pages, which is fragile (Scholar rate-limits/blocks aggressively)
and sits in a legal/ToS gray area. It's included because Scholar is genuinely
useful for finding AI×Bio researchers by affiliation, but:
  - it's best-effort: failures are caught and logged, never crash the run
  - like company_pages, it never invents a LinkedIn URL — it resolves each
    candidate's name through the SearXNG search source and only keeps them if
    a real profile URL is found
  - consider swapping this implementation for a compliant paid API (e.g. a
    Scholar-scraping-as-a-service provider) before relying on it heavily
"""
from __future__ import annotations

import logging
import time

from src.models import Person, is_valid_linkedin_profile_url
from src.sources.base import DiscoverySource
from src.sources.searxng_search_source import SearXNGSearchSource, SearXNGUnavailableError

logger = logging.getLogger(__name__)


class ScholarSource(DiscoverySource):
    name = "google_scholar"

    def is_available(self) -> bool:
        cfg = self.settings.source_config("google_scholar")
        if not cfg.get("enabled", False):
            return False
        try:
            import scholarly  # noqa: F401
        except ImportError:
            logger.warning("google_scholar source enabled in config but 'scholarly' package is not installed.")
            return False
        return True

    def discover(self) -> list[Person]:
        from scholarly import scholarly  # imported lazily; optional dependency

        cfg = self.settings.source_config("google_scholar")
        max_profiles = int(cfg.get("max_profiles_per_run", 10))
        delay = float(cfg.get("request_delay_seconds", 3.0))

        resolver = SearXNGSearchSource(self.settings)
        if not resolver.is_available():
            logger.warning("google_scholar source needs a configured SearXNG instance to resolve LinkedIn URLs — skipping.")
            return []

        candidates: list[Person] = []
        found = 0
        for company in self.settings.target_companies:
            if found >= max_profiles:
                break
            try:
                search_query = scholarly.search_author(f'affiliation:"{company}"')
                author_stub = next(search_query, None)
            except Exception:
                logger.exception("Scholar search failed for affiliation '%s' — skipping.", company)
                continue

            if not author_stub:
                continue

            name = author_stub.get("name", "")
            if not name:
                continue

            person = self._resolve_to_linkedin(resolver, name, company)
            if person:
                candidates.append(person)
                found += 1
            time.sleep(delay)

        return candidates

    def _resolve_to_linkedin(self, resolver: SearXNGSearchSource, name: str, company: str) -> Person | None:
        query = f'site:linkedin.com/in "{name}" "{company}"'
        try:
            items = resolver._search(query, count=3)
        except SearXNGUnavailableError as e:
            logger.warning("LinkedIn resolution search failed for %s: %s", name, e)
            return None

        for item in items:
            link = item.get("url", "")
            if is_valid_linkedin_profile_url(link):
                return Person(
                    name=name,
                    title="Researcher / Academic",
                    company=company,
                    linkedin_url=link,
                    location="",
                    reason=f"Google Scholar author affiliated with {company}; LinkedIn URL confirmed via search.",
                    source=self.name,
                )
        return None
