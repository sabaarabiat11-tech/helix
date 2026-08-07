"""Discover candidates via the official GitHub REST API.

GitHub profiles rarely list a LinkedIn URL directly, so this source only keeps
a candidate when it can actually find one in the user's public bio or "blog"
field — never guesses one. This means GitHub will usually contribute few (or
zero) candidates per run; that's expected, it's a supplementary source.
"""
from __future__ import annotations

import logging
import re
import time

import requests

from src.models import Person, is_valid_linkedin_profile_url
from src.sources.base import DiscoverySource

logger = logging.getLogger(__name__)

SEARCH_ENDPOINT = "https://api.github.com/search/users"
USER_ENDPOINT = "https://api.github.com/users/{login}"

LINKEDIN_URL_PATTERN = re.compile(r"https?://([a-z]{2,3}\.)?(www\.)?linkedin\.com/in/[^\s)\"']+", re.I)

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002190-\U000027BF"
    "\U00002300-\U000023FF"
    "\U0001F1E6-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)


def _clean_title(bio: str | None) -> str:
    if not bio:
        return ""
    text = EMOJI_PATTERN.sub("", bio)
    text = re.sub(r"\s+", " ", text).strip(" -|@")
    # Bios are often multiple clauses; keep it to the first sentence-like chunk.
    first_chunk = re.split(r"[.\n]|(?<=\w)  ", text)[0].strip()
    return first_chunk[:100]


class GitHubSource(DiscoverySource):
    name = "github"

    def is_available(self) -> bool:
        # Works unauthenticated too (lower rate limit), so it's "available" regardless.
        return True

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers

    def discover(self) -> list[Person]:
        cfg = self.settings.source_config("github")
        max_results = int(cfg.get("max_results_per_query", 15))
        delay = float(cfg.get("request_delay_seconds", 2.0))

        candidates: list[Person] = []
        for company in self.settings.target_companies:
            query = f'"{company}" in:bio'
            try:
                logins = self._search_users(query, max_results)
            except requests.HTTPError as e:
                logger.warning("GitHub search failed for '%s': %s", company, e)
                time.sleep(delay)
                continue

            for login in logins:
                person = self._resolve_user(login, company)
                if person:
                    candidates.append(person)
                time.sleep(delay)

        return candidates

    def _search_users(self, query: str, per_page: int) -> list[str]:
        params = {"q": query, "per_page": per_page}
        resp = requests.get(SEARCH_ENDPOINT, params=params, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return [item["login"] for item in resp.json().get("items", [])]

    def _resolve_user(self, login: str, company_hint: str) -> Person | None:
        resp = requests.get(USER_ENDPOINT.format(login=login), headers=self._headers(), timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()

        blob = " ".join(filter(None, [data.get("bio"), data.get("blog"), data.get("company")]))
        match = LINKEDIN_URL_PATTERN.search(blob)
        if not match:
            return None  # no verifiable LinkedIn URL -> skip, do not guess one

        linkedin_url = match.group(0).rstrip(").,\"'")
        if not is_valid_linkedin_profile_url(linkedin_url):
            return None

        name = data.get("name") or login
        title = _clean_title(data.get("bio")) or "Software/ML Engineer"
        return Person(
            name=name,
            title=title,
            company=company_hint,
            linkedin_url=linkedin_url,
            location=data.get("location") or "",
            reason=f"Active GitHub contributor whose profile bio references {company_hint}.",
            source=self.name,
        )
