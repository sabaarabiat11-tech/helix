"""Discover LinkedIn profiles via a locally self-hosted SearXNG instance
(Docker, see docker-compose.yml) — queries SearXNG's JSON API, never touches
linkedin.com directly. This is the primary "LinkedIn" and general web-search
domain handler from the requirements.

This project no longer uses any public SearXNG instance. Public instances
were tried first but proved unreliable in practice (heavy rate-limiting /
blocking from shared IPs) — running our own instance in Docker means full
control, no rate limits from other users, and no dependency on volunteer
infrastructure. It is still not a paid service: SearXNG itself is free,
open-source software; Docker Desktop is free for local development use.

Every LinkedIn URL returned here comes straight from a real SearXNG search
result — nothing is guessed or constructed.
"""
from __future__ import annotations

import itertools
import logging
import re
import time

import requests

from src.models import Person, is_valid_linkedin_profile_url
from src.sources.base import DiscoverySource

logger = logging.getLogger(__name__)

# LinkedIn result titles are typically "Name - Title - Company | LinkedIn"
# or "Name | LinkedIn" — parse what we can, leave the rest blank rather than guess.
TITLE_PATTERN = re.compile(r"^(?P<name>[^-|]+?)\s*-\s*(?P<title>[^-|]+?)\s*-\s*(?P<company>[^-|]+?)\s*\|\s*LinkedIn", re.I)
TITLE_PATTERN_SIMPLE = re.compile(r"^(?P<name>[^-|]+?)\s*-\s*(?P<title>[^|]+?)\s*\|\s*LinkedIn", re.I)

HTML_TAG = re.compile(r"<[^>]+>")

REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class SearXNGUnavailableError(RuntimeError):
    """Raised when the local SearXNG instance could not be reached/queried
    after all configured retries — most likely the Docker container isn't
    running. Run `docker compose up -d` (or `python start.py`, which does
    this automatically)."""


class SearXNGSearchSource(DiscoverySource):
    name = "searxng_search"

    def is_available(self) -> bool:
        # No API key required — available as long as a base URL is configured.
        return bool(self._base_url())

    def _base_url(self) -> str:
        cfg = self.settings.source_config("searxng_search")
        return cfg.get("base_url", "").rstrip("/")

    def discover(self) -> list[Person]:
        cfg = self.settings.source_config("searxng_search")
        results_per_query = int(cfg.get("results_per_query", 8))
        max_queries = int(cfg.get("max_queries_per_run", 40))
        delay = float(cfg.get("request_delay_seconds", 0.5))

        queries = self._build_queries()[:max_queries]
        candidates: list[Person] = []

        for query in queries:
            try:
                items = self._search(query, count=results_per_query)
            except SearXNGUnavailableError as e:
                logger.warning("SearXNG query failed: %s — skipping this query.", e)
                time.sleep(delay)
                continue

            for item in items:
                person = self._parse_item(item)
                if person:
                    candidates.append(person)

            time.sleep(delay)

        return candidates

    def _build_queries(self) -> list[str]:
        companies = self.settings.target_companies
        roles = self.settings.target_roles
        queries = []
        for company, role in itertools.product(companies, roles):
            queries.append(f'site:linkedin.com/in "{company}" "{role}"')
        return queries

    def _search(self, query: str, count: int) -> list[dict]:
        """Query the local SearXNG instance, with retries + backoff for
        transient errors (e.g. the container is still warming up). Returns a
        normalized list of {"title", "url", "description"} dicts, or raises
        SearXNGUnavailableError if every retry failed.
        """
        cfg = self.settings.source_config("searxng_search")
        timeout = float(cfg.get("timeout_seconds", 10))
        max_retries = int(cfg.get("max_retries", 3))
        backoff_base = float(cfg.get("retry_backoff_seconds", 1.0))

        base_url = self._base_url()
        if not base_url:
            raise SearXNGUnavailableError("No SearXNG base_url configured (config.yaml -> sources.searxng_search.base_url).")

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                return self._search_once(base_url, query, count, timeout)
            except (requests.RequestException, ValueError) as e:
                last_error = e
                logger.warning(
                    "SearXNG request attempt %d/%d failed for query '%s': %s",
                    attempt, max_retries, query, e,
                )
                if attempt < max_retries:
                    time.sleep(backoff_base * attempt)

        raise SearXNGUnavailableError(
            f"Local SearXNG instance at {base_url} did not respond successfully after "
            f"{max_retries} attempts (last error: {last_error}). Is the Docker container "
            f"running? Try: docker compose up -d"
        )

    def _search_once(self, base_url: str, query: str, count: int, timeout: float) -> list[dict]:
        params = {
            "q": query,
            "format": "json",
            "language": "en",
        }
        resp = requests.get(
            f"{base_url}/search",
            params=params,
            headers=REQUEST_HEADERS,
            timeout=timeout,
        )
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "json" not in content_type.lower():
            raise ValueError(f"non-JSON response (Content-Type: {content_type or 'unknown'})")

        data = resp.json()
        raw_results = data.get("results", [])[:count]
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("content", ""),
            }
            for r in raw_results
        ]

    def _parse_item(self, item: dict) -> Person | None:
        link = item.get("url", "")
        if not is_valid_linkedin_profile_url(link):
            return None

        title_text = HTML_TAG.sub("", item.get("title", ""))
        description = HTML_TAG.sub("", item.get("description", ""))

        m = TITLE_PATTERN.match(title_text) or TITLE_PATTERN_SIMPLE.match(title_text)
        if not m:
            return None

        groups = m.groupdict()
        name = groups.get("name", "").strip()
        role_title = groups.get("title", "").strip()
        company = groups.get("company", "").strip()

        if not name or not role_title:
            return None

        # If the company wasn't in the title, fall back to whichever target
        # company name appears in the title/description text.
        if not company:
            company = self._infer_company(title_text + " " + description) or ""
        if not company:
            return None

        return Person(
            name=name,
            title=role_title,
            company=company,
            linkedin_url=link,
            location="",
            reason=f"Found via local SearXNG instance matching '{company}' + relevant AI×Bio role.",
            source=self.name,
        )

    def _infer_company(self, text: str) -> str | None:
        text_l = text.lower()
        for company in self.settings.target_companies:
            if company.lower() in text_l:
                return company
        return None
