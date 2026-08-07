"""In-process scheduler for the daily and weekly recommendation emails.

Why in-process, when `workers/digest_worker.py` already exists
--------------------------------------------------------------
The CLI worker is the better architecture at scale — it scales separately from
web traffic and a slow mail provider can't tie up request workers. But it
requires configuring a cron job in the hosting platform, which is a manual
step, and a digest that silently never sends because nobody set that up is
worse than a slightly less pure design.

So this runs the same `digest_service` code on a timer inside the API process
and is on by default. Set `ENABLE_SCHEDULER=false` once real cron jobs exist.

Correctness details that matter more than the mechanism:

* **At most once per day.** The last successful send date is recorded in the
  `meta` table, not in memory, so a redeploy or a crash-restart at 08:05 does
  not send everyone a second copy.
* **Safe with several instances.** The same `meta` row is claimed with a
  conditional UPDATE, so if the service is ever scaled to more than one
  replica exactly one of them wins the day's send.
* **Catch-up, not backlog.** If the process was down at the scheduled hour it
  sends once when it next wakes, rather than replaying every missed day.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from config import settings
from database import get_meta, set_meta
from db import db_conn, execute, row, utcnow
from services import digest_service

log = logging.getLogger("helix.scheduler")

# How often to wake and check whether anything is due. The scheduled hour has
# minute granularity at best, so a tighter loop would only burn cycles.
CHECK_INTERVAL_SECONDS = 300

DAILY_KEY = "scheduler_last_daily"
WEEKLY_KEY = "scheduler_last_weekly"


def _claim(key: str, today: str) -> bool:
    """Atomically claim today's run for `key`. True if this caller won it.

    The conditional UPDATE is what makes this safe across replicas: whichever
    instance's statement lands first changes a row, the rest change none.
    """
    with db_conn() as conn:
        existing = row(conn, "SELECT value FROM meta WHERE key = :key", {"key": key})
        if existing is None:
            # First ever run for this cadence. INSERT ... ON CONFLICT DO
            # NOTHING means a racing instance inserting the same key loses.
            result = execute(
                conn,
                "INSERT INTO meta (key, value) VALUES (:key, :today) "
                "ON CONFLICT(key) DO NOTHING",
                {"key": key, "today": today},
            )
            return result.rowcount > 0

        if existing["value"] == today:
            return False

        result = execute(
            conn,
            "UPDATE meta SET value = :today WHERE key = :key AND value != :today",
            {"key": key, "today": today},
        )
        return result.rowcount > 0


def _due(frequency: str, now) -> bool:
    """Whether `frequency` should send at this moment."""
    if now.hour < settings.scheduler_hour:
        return False
    if frequency == "weekly" and now.weekday() != settings.scheduler_weekday:
        return False

    key = DAILY_KEY if frequency == "daily" else WEEKLY_KEY
    last = get_meta(key)
    return last != now.date().isoformat()


def run_due_digests(force: str | None = None) -> list[dict]:
    """Send whichever digests are due. Returns a summary per cadence sent.

    `force` bypasses the schedule for one cadence — used by the admin trigger
    so an operator can verify delivery without waiting for tomorrow.
    """
    now = utcnow()
    today = now.date().isoformat()
    summaries = []

    for frequency in ("daily", "weekly"):
        if force and force != frequency:
            continue
        if not force and not _due(frequency, now):
            continue

        key = DAILY_KEY if frequency == "daily" else WEEKLY_KEY
        if not force and not _claim(key, today):
            log.info("Another instance already sent the %s digest today", frequency)
            continue

        log.info("Sending %s digests", frequency)
        try:
            summaries.append(digest_service.run_digests(frequency))
        except Exception:
            log.exception("The %s digest run failed", frequency)
            # Release the claim so the next check retries rather than skipping
            # the whole day over a transient mail-provider outage.
            if not force:
                set_meta(key, (date.fromisoformat(today) - timedelta(days=1)).isoformat())

    return summaries


async def scheduler_loop() -> None:
    """Background task started with the app when ENABLE_SCHEDULER is on."""
    log.info(
        "Digest scheduler active — daily at %02d:00 UTC, weekly on %s",
        settings.scheduler_hour,
        ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][settings.scheduler_weekday],
    )
    while True:
        try:
            # run_due_digests is blocking (database + HTTP to the mail
            # provider), so it goes to a worker thread rather than stalling the
            # event loop and with it every in-flight request.
            await asyncio.to_thread(run_due_digests)
        except asyncio.CancelledError:
            log.info("Digest scheduler stopping")
            raise
        except Exception:
            log.exception("Scheduler tick failed; continuing")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
