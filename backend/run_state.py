"""In-memory state for the currently running (if any) discovery pipeline
process, shared between the /api/run (trigger + stream) and /api/stats
(pipeline status) endpoints.

Single-process assumption: this lives in one worker's memory, so it only gives
correct answers with exactly one API replica. That already matches this
deployment (`railway.json` sets `numReplicas: 1`, and the pipeline is a single
long-running subprocess that shouldn't be triggered from two places at once
regardless) — noted here so it's a deliberate limit, not a surprise if the
replica count ever changes.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from services.pipeline_log import STATUS_NEVER_RUN, RunOutcome


@dataclass
class RunState:
    running: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    process: asyncio.subprocess.Process | None = None
    log_lines: list[str] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)

    # Set once the run completes, from the actual captured output — see
    # services/pipeline_log.py. None while a run is in progress or before the
    # first run of this process's lifetime.
    outcome: RunOutcome | None = None

    def reset_for_new_run(self, started_at: str) -> None:
        self.running = True
        self.started_at = started_at
        self.finished_at = None
        self.exit_code = None
        self.log_lines = []
        self.outcome = None

    async def broadcast(self, line: str) -> None:
        self.log_lines.append(line)
        for q in list(self.subscribers):
            await q.put(line)

    async def finish(self, finished_at: str, exit_code: int, outcome: RunOutcome) -> None:
        self.running = False
        self.finished_at = finished_at
        self.exit_code = exit_code
        self.outcome = outcome
        for q in list(self.subscribers):
            await q.put(None)  # sentinel: stream closed
        self.subscribers.clear()

    def status_payload(self) -> dict:
        """The fields every consumer (REST poll, WebSocket close event) needs
        to render an honest state — one place so they can't drift apart."""
        if self.running:
            return {"status": "running", "new_people": None, "searxng_reachable": None}
        if self.outcome is not None:
            return self.outcome.as_dict()
        return {"status": STATUS_NEVER_RUN, "new_people": None, "searxng_reachable": None}


run_state = RunState()
