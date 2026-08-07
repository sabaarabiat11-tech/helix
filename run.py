#!/usr/bin/env python3
"""Entry point for a single discovery run.

Usage:
    python run.py

Prefer `python start.py` instead, which also starts the local SearXNG Docker
container and waits for it to be healthy first. This script still performs
its own (shorter) readiness check as a safety net in case it's invoked
directly without going through start.py — if SearXNG isn't reachable, the
run continues anyway (fail-soft: GitHub/company_pages/scholar can still
contribute) but logs a clear warning so the shortfall isn't a mystery.

Intended to be invoked weekly (see README.md for Windows Task Scheduler setup).
Every run is idempotent-ish: it only ever appends genuinely new people (deduped
against the existing master CSV) and never modifies or deletes prior rows.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.wait_for_searxng import wait_for_searxng
from src.config import load_settings
from src.logging_setup import setup_logging
from src.pipeline import run_pipeline
from src.report import write_weekly_report


def main() -> int:
    settings = load_settings()
    log_file = setup_logging(settings.path("logs_dir"))
    logger = logging.getLogger("run")

    logger.info("=== AI x Biology LinkedIn discovery run starting ===")
    logger.info("Log file: %s", log_file)

    searxng_cfg = settings.source_config("searxng_search")
    base_url = searxng_cfg.get("base_url", "http://localhost:8080")
    logger.info("Checking local SearXNG readiness at %s ...", base_url)
    if not wait_for_searxng(base_url, timeout=15, poll_interval=3):
        logger.warning(
            "SearXNG at %s is not reachable/healthy. Continuing anyway (fail-soft) — "
            "the searxng_search source will be skipped for this run. "
            "Run 'docker compose up -d' (or 'python start.py') to fix this.",
            base_url,
        )

    try:
        result = run_pipeline(settings)
    except Exception:
        logger.exception("Run failed with an unhandled error.")
        return 1

    report_path = write_weekly_report(settings.path("reports_dir"), result)
    logger.info("Report written to %s", report_path)
    logger.info(
        "=== Run complete: %d new people added (target 20-30/week) ===",
        len(result.new_people),
    )

    if result.target_shortfall:
        logger.warning("Run finished below the weekly target — see report for likely causes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
