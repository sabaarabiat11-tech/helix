"""In-memory state for the currently running (if any) discovery pipeline
process, shared between the /api/run (trigger + stream) and /api/stats
(pipeline status) endpoints. Single-process dev server assumption — this is
a local dashboard, not a multi-worker production deployment.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class RunState:
    running: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    process: asyncio.subprocess.Process | None = None
    log_lines: list[str] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)

    def reset_for_new_run(self, started_at: str) -> None:
        self.running = True
        self.started_at = started_at
        self.finished_at = None
        self.exit_code = None
        self.log_lines = []

    async def broadcast(self, line: str) -> None:
        self.log_lines.append(line)
        for q in list(self.subscribers):
            await q.put(line)

    async def finish(self, finished_at: str, exit_code: int) -> None:
        self.running = False
        self.finished_at = finished_at
        self.exit_code = exit_code
        for q in list(self.subscribers):
            await q.put(None)  # sentinel: stream closed
        self.subscribers.clear()


run_state = RunState()
