from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from config import settings
from core import deps
from core.security import decode_access_token
from database import sync_from_csv
from run_state import run_state
from services import notification_service
from services.pipeline_log import parse_run_log

router = APIRouter(prefix="/api/run", tags=["run"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"


def _pipeline_command() -> list[str]:
    """What "Run Discovery" actually executes.

    `start.py` is a *local-dev* convenience: it shells out to
    `docker compose up -d` and polls `localhost:8080` before running the
    pipeline, to save a manual step on a laptop. Neither can ever succeed
    inside a hosted container — there is no Docker socket and nothing
    listening on its own loopback — so on a hosted deployment `start.py`
    fails at step one and the real pipeline (`run.py`) never runs at all.

    `run.py` is the pipeline itself. It already does its own short SearXNG
    readiness check and, if unreachable, logs a clear warning and continues
    fail-soft rather than aborting (other sources can still contribute) — see
    its own docstring. That's the right behavior everywhere, so hosted
    deployments call it directly and rely on `SEARXNG_BASE_URL` pointing at
    wherever SearXNG actually runs, instead of trying to manage it locally.
    """
    if settings.is_hosted:
        return [sys.executable, "run.py"]
    return [sys.executable, "start.py"]


async def _stream_process(process: asyncio.subprocess.Process) -> None:
    assert process.stdout is not None
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        decoded = line.decode(errors="replace").rstrip("\n")
        await run_state.broadcast(decoded)

    exit_code = await process.wait()

    # The captured output is the same text a completed run leaves in its log
    # file, so this uses the identical parser routers/stats.py reads on a
    # cold GET — one set of rules for "what actually happened."
    outcome = parse_run_log("\n".join(run_state.log_lines))

    # The database is the app's source of truth — sync immediately on
    # completion rather than waiting for the next GET request to notice the
    # CSV changed, and generate the notification set the moment new data is
    # known. A zero-result or failed run still calls this (force=True is
    # cheap and sync_from_csv is a no-op if nothing changed); it just won't
    # have anything new to report.
    sync_result = sync_from_csv(force=True)
    new_people_count = len(sync_result.get("new_people") or [])
    notification_service.notify_run_completed(sync_result, new_people_count)

    # Only notify if a report was actually (re)written during THIS run —
    # same-day reruns overwrite the same filename, so mtime vs. run start is
    # the only reliable "was this freshly written" check.
    run_started = datetime.fromisoformat(run_state.started_at)
    reports = sorted(REPORTS_DIR.glob("weekly_report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if reports and datetime.fromtimestamp(reports[0].stat().st_mtime) >= run_started:
        notification_service.notify_report_ready(reports[0].name)

    await run_state.finish(datetime.now().isoformat(), exit_code, outcome)


@router.post("")
async def trigger_run(user: dict = Depends(deps.current_user)):
    # The pipeline is shared infrastructure, not per-user work: one run updates
    # the corpus everybody sees. In a multi-tenant deployment it belongs on a
    # schedule, so triggering it from the UI is opt-in via config and otherwise
    # limited to administrators.
    if not settings.allow_user_triggered_runs and not user["is_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Discovery runs are scheduled by the operator on this deployment.",
        )

    if run_state.running:
        raise HTTPException(status_code=409, detail="A discovery run is already in progress.")

    if settings.is_hosted and not settings.searxng_base_url:
        # Fail before spawning anything, with a message that says what to do,
        # rather than letting the run finish in ~15s reporting zero results
        # for a reason the operator has to go dig up.
        raise HTTPException(
            status_code=503,
            detail=(
                "Discovery search backend is not configured. Set SEARXNG_BASE_URL to a "
                "reachable SearXNG instance before running discovery on this deployment."
            ),
        )

    run_state.reset_for_new_run(datetime.now().isoformat())

    process = await asyncio.create_subprocess_exec(
        *_pipeline_command(),
        cwd=str(PROJECT_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    run_state.process = process

    asyncio.create_task(_stream_process(process))

    return {"started": True, "started_at": run_state.started_at}


@router.get("/state")
def get_run_state(_: dict = Depends(deps.current_user)):
    return {
        "running": run_state.running,
        "started_at": run_state.started_at,
        "finished_at": run_state.finished_at,
        "exit_code": run_state.exit_code,
        "can_trigger": settings.allow_user_triggered_runs,
        **run_state.status_payload(),
    }


@router.websocket("/stream")
async def stream_run_logs(websocket: WebSocket, token: str = ""):
    """Live pipeline log stream.

    Browsers cannot set an Authorization header on a WebSocket handshake, so
    the access token arrives as a query parameter instead. It is the same
    short-lived JWT used everywhere else, verified the same way — and because
    it expires in minutes, its appearance in a URL is low-risk.
    """
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4401)  # 4401: application-level "unauthorized"
        return

    await websocket.accept()

    # Replay whatever's already happened this run (so a client that connects
    # mid-run, or reconnects after a refresh, doesn't miss the beginning).
    for line in run_state.log_lines:
        await websocket.send_text(line)

    if not run_state.running:
        await websocket.send_json({"event": "closed", "exit_code": run_state.exit_code, **run_state.status_payload()})
        await websocket.close()
        return

    queue: asyncio.Queue = asyncio.Queue()
    run_state.subscribers.append(queue)

    try:
        while True:
            item = await queue.get()
            if item is None:  # sentinel: run finished
                await websocket.send_json(
                    {"event": "closed", "exit_code": run_state.exit_code, **run_state.status_payload()}
                )
                break
            await websocket.send_text(item)
    except WebSocketDisconnect:
        pass
    finally:
        if queue in run_state.subscribers:
            run_state.subscribers.remove(queue)
        try:
            await websocket.close()
        except RuntimeError:
            pass
