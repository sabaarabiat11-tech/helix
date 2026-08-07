"""Orchestrates all sources into one weekly run: discover -> dedupe -> filter ->
rank -> cap to target range -> append to master CSV -> write report."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.config import Settings
from src.dedupe_store import MasterStore
from src.models import Person
from src.sources.base import DiscoverySource
from src.sources.company_pages_source import CompanyPagesSource
from src.sources.github_source import GitHubSource
from src.sources.scholar_source import ScholarSource
from src.sources.searxng_search_source import SearXNGSearchSource

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    new_people: list[Person] = field(default_factory=list)
    per_source_counts: dict[str, int] = field(default_factory=dict)
    per_source_errors: list[str] = field(default_factory=list)
    existing_count_before: int = 0
    total_candidates_before_dedupe: int = 0
    target_shortfall: bool = False


def build_sources(settings: Settings) -> list[DiscoverySource]:
    all_sources = [
        SearXNGSearchSource(settings),
        GitHubSource(settings),
        CompanyPagesSource(settings),
        ScholarSource(settings),
    ]
    enabled = []
    for source in all_sources:
        cfg = settings.source_config(source.name)
        if cfg.get("enabled", True):
            enabled.append(source)
        else:
            logger.info("Source '%s' disabled in config.yaml.", source.name)
    return enabled


def is_excluded_title(settings: Settings, title: str) -> bool:
    title_l = title.lower()
    return any(kw in title_l for kw in settings.exclude_title_keywords)


def score_candidate(settings: Settings, person: Person) -> int:
    score = 0
    if person.company in settings.target_companies:
        score += 10
    title_l = person.title.lower()
    if any(role.lower() in title_l for role in settings.target_roles):
        score += 5
    if person.location:
        score += 1
    if person.reason:
        score += 1
    return score


def run_pipeline(settings: Settings) -> RunResult:
    master_path = settings.path("master_csv")
    store = MasterStore(master_path)

    result = RunResult(existing_count_before=store.existing_count)

    sources = build_sources(settings)
    all_candidates: list[Person] = []

    for source in sources:
        found = source.run_safely()
        result.per_source_counts[source.name] = len(found)
        all_candidates.extend(found)

    result.total_candidates_before_dedupe = len(all_candidates)

    # Filter -> dedupe (against master AND within this run's batch) -> score -> rank.
    accepted: list[Person] = []
    for person in all_candidates:
        if not person.name or not person.company or not person.linkedin_url:
            continue
        if is_excluded_title(settings, person.title):
            continue
        if store.is_duplicate(person):
            continue
        store.register(person)  # prevents the same person appearing twice from two sources in one run
        accepted.append(person)

    accepted.sort(key=lambda p: score_candidate(settings, p), reverse=True)

    run_cfg = settings.run_config
    max_new = int(run_cfg.get("max_new_per_run", 30))
    min_new = int(run_cfg.get("min_new_per_run", 20))

    final_batch = accepted[:max_new]
    if len(final_batch) < min_new:
        result.target_shortfall = True
        logger.warning(
            "Only found %d new people this run (target was %d-%d). "
            "Consider enabling more sources or widening target_companies/target_roles.",
            len(final_batch), min_new, max_new,
        )

    store.append(final_batch)
    result.new_people = final_batch
    return result
