"""Common interface every discovery source implements.

A source's job is to *propose* candidate Person objects. It must never invent a
LinkedIn URL — every URL it returns has to come from something it actually
observed (a search result, an API response, a scraped page). The pipeline is
responsible for deduplication and final filtering; a source can be sloppy about
duplicates but must not be sloppy about authenticity.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from src.config import Settings
from src.models import Person

logger = logging.getLogger(__name__)


class DiscoverySource(ABC):
    name: str = "base"

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def is_available(self) -> bool:
        """False if required credentials/config are missing — the pipeline logs
        this as a skipped source rather than failing the run."""

    @abstractmethod
    def discover(self) -> list[Person]:
        """Return candidate people. Raise on hard failure; the pipeline catches
        and logs it per-source (fail_soft) so one broken source doesn't kill the run."""

    def run_safely(self) -> list[Person]:
        if not self.is_available():
            logger.warning("Source '%s' skipped: not configured (missing credentials/config).", self.name)
            return []
        try:
            results = self.discover()
            logger.info("Source '%s' produced %d candidates.", self.name, len(results))
            return results
        except Exception:
            logger.exception("Source '%s' failed — continuing with other sources.", self.name)
            return []
