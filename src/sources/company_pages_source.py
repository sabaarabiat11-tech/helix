"""Scrape configured company "team"/"about" pages for names + titles, then
resolve each name to a real LinkedIn URL via the SearXNG search source
(reusing its resolver so we never invent a linkedin.com/in/... URL ourselves).

This is inherently the most fragile source — every company's team page has
different HTML. Without a per-company CSS selector in config.yaml it falls
back to a generic heuristic (looks for short text nodes near "team"/"people"
containers) which will have false positives/negatives. Add selectors as you
discover what works for each site.
"""
from __future__ import annotations

import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from src.models import Person, is_valid_linkedin_profile_url
from src.sources.base import DiscoverySource
from src.sources.searxng_search_source import SearXNGSearchSource, SearXNGUnavailableError

logger = logging.getLogger(__name__)

# A generic "looks like a person's name" filter for the fallback heuristic —
# two or three capitalized words, no digits/punctuation beyond hyphen/period.
NAME_LIKE = re.compile(r"^[A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+){1,2}$")


class CompanyPagesSource(DiscoverySource):
    name = "company_pages"

    def is_available(self) -> bool:
        cfg = self.settings.source_config("company_pages")
        return bool(cfg.get("pages"))

    def discover(self) -> list[Person]:
        cfg = self.settings.source_config("company_pages")
        delay = float(cfg.get("request_delay_seconds", 1.5))
        pages = cfg.get("pages", [])

        # Used only to resolve name -> real LinkedIn URL, not to run its own queries.
        resolver = SearXNGSearchSource(self.settings)
        can_resolve = resolver.is_available()
        if not can_resolve:
            logger.warning(
                "company_pages source found candidates but no local SearXNG "
                "base_url is configured, so LinkedIn URLs cannot be resolved — "
                "this source will contribute 0 people this run."
            )

        candidates: list[Person] = []
        for page_cfg in pages:
            company = page_cfg["company"]
            url = page_cfg["url"]
            selector = page_cfg.get("selector")

            try:
                html = self._fetch(url)
            except requests.RequestException as e:
                logger.warning("Could not fetch team page for %s (%s): %s", company, url, e)
                continue

            names = self._extract_names(html, selector)
            logger.info("Parsed %d candidate name(s) from %s team page.", len(names), company)

            if not can_resolve:
                continue

            for name, title_guess in names:
                time.sleep(delay)
                person = self._resolve_to_linkedin(resolver, name, title_guess, company)
                if person:
                    candidates.append(person)

        return candidates

    def _fetch(self, url: str) -> str:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Bio-Discovery-Agent/1.0)"})
        resp.raise_for_status()
        return resp.text

    def _extract_names(self, html: str, selector: str | None) -> list[tuple[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[tuple[str, str]] = []

        if selector:
            for node in soup.select(selector):
                text = node.get_text(strip=True)
                if NAME_LIKE.match(text):
                    results.append((text, ""))
            return results

        # Generic fallback: scan short text nodes that look like a person's name,
        # and use the immediately-following sibling text (if short) as a title guess.
        for tag in soup.find_all(["h2", "h3", "h4", "span", "p", "div"]):
            text = tag.get_text(strip=True)
            if NAME_LIKE.match(text):
                title_guess = ""
                sib = tag.find_next_sibling()
                if sib:
                    sib_text = sib.get_text(strip=True)
                    if sib_text and len(sib_text) < 80:
                        title_guess = sib_text
                results.append((text, title_guess))

        # De-dupe while preserving order.
        seen = set()
        deduped = []
        for name, title in results:
            if name not in seen:
                seen.add(name)
                deduped.append((name, title))
        return deduped

    def _resolve_to_linkedin(self, resolver: SearXNGSearchSource, name: str, title_guess: str, company: str) -> Person | None:
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
                    title=title_guess or "Team Member",
                    company=company,
                    linkedin_url=link,
                    location="",
                    reason=f"Listed on {company}'s public team page; LinkedIn URL confirmed via search.",
                    source=self.name,
                )
        return None
