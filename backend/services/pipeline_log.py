"""Turns a pipeline run's log text into a structured, honest outcome.

`run.py` is deliberately fail-soft about SearXNG: if it's unreachable, the run
continues so GitHub/company-pages/Scholar can still contribute, and exits 0.
That's the right behavior for the pipeline itself — but it means "exit code 0"
alone cannot tell a caller whether the run actually found anyone, or why it
didn't. This module extracts that from the same log lines the pipeline already
writes (see `run.py`'s `wait_for_searxng` call and its final summary line), so
no pipeline code has to change to get an honest answer.

Used by two callers that must agree with each other: `routers/stats.py`
(reads the last log file on disk, for the dashboard's "Last Run" card) and
`routers/run.py` (reads the just-finished run's own log, for the live
WebSocket "closed" event and `GET /api/run/state`). One parser, one set of
rules, so the two never drift apart.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# These match the exact strings run.py and wait_for_searxng.py already log —
# see backend/routers/run.py's docstring note and run.py's own comments for
# why fail-soft is intentional. Change the wording there and this breaks, but
# that coupling is explicit and grep-able rather than a silent assumption.
SEARXNG_UNREACHABLE_RE = re.compile(r"SearXNG at .+ is not reachable/healthy")
SEARXNG_HEALTHY_RE = re.compile(r"SearXNG is healthy and the JSON API works")
RUN_COMPLETE_RE = re.compile(r"Run complete: (\d+) new people added")
UNHANDLED_ERROR_RE = re.compile(r"Traceback|Run failed with an unhandled error")

# Every value this module can return for `status`. Superset of the five the
# dashboard's PIPELINE_TONE/PIPELINE_LABEL maps already know about
# (never_run/running/completed/failed/incomplete) — the extra ones are
# additive, so a frontend that doesn't recognize them yet still has a
# reasonable fallback string to display rather than breaking.
STATUS_NEVER_RUN = "never_run"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_COMPLETED_ZERO_RESULTS = "completed_zero_results"
STATUS_COMPLETED_ZERO_RESULTS_SEARXNG_UNAVAILABLE = "completed_zero_results_searxng_unavailable"
STATUS_FAILED = "failed"
STATUS_INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class RunOutcome:
    status: str
    new_people: int | None
    searxng_reachable: bool | None

    @property
    def succeeded(self) -> bool:
        return self.status in (
            STATUS_COMPLETED,
            STATUS_COMPLETED_ZERO_RESULTS,
            STATUS_COMPLETED_ZERO_RESULTS_SEARXNG_UNAVAILABLE,
        )

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "new_people": self.new_people,
            "searxng_reachable": self.searxng_reachable,
        }


def parse_run_log(text: str) -> RunOutcome:
    """Classify a completed (or in-progress) run from its log text.

    Order matters: an unhandled error is checked first because a traceback can
    appear *after* a partial "Run complete" line was never reached, and
    reachability is read independently of the people count so a run that found
    SearXNG healthy but genuinely discovered nobody new is reported as exactly
    that, not confused with an infrastructure failure.
    """
    if UNHANDLED_ERROR_RE.search(text):
        return RunOutcome(STATUS_FAILED, None, _reachability(text))

    match = RUN_COMPLETE_RE.search(text)
    if match is None:
        # The process ended (or hasn't yet) without ever reaching its own
        # summary line — still writing, or it exited some other way run.py
        # doesn't log about.
        return RunOutcome(STATUS_INCOMPLETE, None, _reachability(text))

    new_people = int(match.group(1))
    reachable = _reachability(text)

    if new_people > 0:
        return RunOutcome(STATUS_COMPLETED, new_people, reachable)
    if reachable is False:
        return RunOutcome(STATUS_COMPLETED_ZERO_RESULTS_SEARXNG_UNAVAILABLE, 0, reachable)
    return RunOutcome(STATUS_COMPLETED_ZERO_RESULTS, 0, reachable)


def _reachability(text: str) -> bool | None:
    """None means the log never mentioned a check either way (e.g. the run
    crashed before `run.py` reached its own readiness probe)."""
    if SEARXNG_HEALTHY_RE.search(text):
        return True
    if SEARXNG_UNREACHABLE_RE.search(text):
        return False
    return None


# Human-readable text for each status, meant for a UI label. Kept alongside
# the parser rather than duplicated in the frontend, so the wording only has
# to be right once.
STATUS_MESSAGES = {
    STATUS_NEVER_RUN: "Never run",
    STATUS_RUNNING: "Discovery run in progress",
    STATUS_COMPLETED: "Run finished",
    STATUS_COMPLETED_ZERO_RESULTS: "Run finished — no new people found",
    STATUS_COMPLETED_ZERO_RESULTS_SEARXNG_UNAVAILABLE: "Discovery failed: SearXNG is unavailable",
    STATUS_FAILED: "Discovery run failed",
    STATUS_INCOMPLETE: "Run ended unexpectedly",
}


def describe(status: str) -> str:
    return STATUS_MESSAGES.get(status, status)
