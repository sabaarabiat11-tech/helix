"""Scheduled digest sender.

Deliberately a standalone CLI rather than a thread inside the API process:

* it scales independently of web traffic, and a slow mail provider can't tie up
  request workers;
* it works with whatever scheduler the deployment already has — cron, systemd
  timers, Windows Task Scheduler, a Kubernetes CronJob, Render/Railway cron;
* it can be run by hand, and `--dry-run` shows exactly who would receive what
  without sending anything.

Usage (from the project root):

    python backend/workers/digest_worker.py --frequency daily
    python backend/workers/digest_worker.py --frequency weekly --dry-run

Suggested schedule: daily at 08:00, weekly on Monday at 08:00.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running this file directly (python backend/workers/digest_worker.py)
# as well as via -m, by putting backend/ on the import path either way.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from db import init_db  # noqa: E402
from services import digest_service  # noqa: E402

log = logging.getLogger("helix.worker")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send Helix digest emails.")
    parser.add_argument(
        "--frequency",
        choices=["daily", "weekly"],
        required=True,
        help="Which subscriber group to send to.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build every digest and report what would be sent, without sending.",
    )
    parser.add_argument("--verbose", action="store_true", help="Debug-level logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    )

    log.info(
        "Digest worker starting · frequency=%s · provider=%s · env=%s",
        args.frequency, settings.email_provider, settings.environment,
    )

    init_db()

    try:
        summary = digest_service.run_digests(args.frequency, dry_run=args.dry_run)
    except Exception:
        log.exception("Digest run failed")
        return 1

    log.info(
        "Done · %s recipients · %s sent · %s failed · %s skipped%s",
        summary["recipients"], summary["sent"], summary["failed"], summary["skipped"],
        " (dry run)" if summary["dry_run"] else "",
    )
    # A partial failure is worth surfacing to whatever scheduler invoked this.
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
