from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter

from database import sync_from_csv
from db import db_conn, scalar
from routers.status import _check_docker, _check_searxng
from run_state import run_state

router = APIRouter(prefix="/api/stats", tags=["stats"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = PROJECT_ROOT / "data" / "logs"

RUN_COMPLETE_RE = re.compile(r"Run complete: (\d+) new people added")


def _latest_log_info() -> dict:
    if not LOGS_DIR.exists():
        return {"last_run_time": None, "last_run_new_people": None, "last_run_status": "never_run"}

    log_files = sorted(LOGS_DIR.glob("run_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not log_files:
        return {"last_run_time": None, "last_run_new_people": None, "last_run_status": "never_run"}

    latest = log_files[0]
    mtime = datetime.fromtimestamp(latest.stat().st_mtime).isoformat()

    text = latest.read_text(encoding="utf-8", errors="replace")
    match = RUN_COMPLETE_RE.search(text)
    if match:
        return {
            "last_run_time": mtime,
            "last_run_new_people": int(match.group(1)),
            "last_run_status": "completed",
        }
    if "Traceback" in text or "Run failed" in text:
        return {"last_run_time": mtime, "last_run_new_people": None, "last_run_status": "failed"}
    return {"last_run_time": mtime, "last_run_new_people": None, "last_run_status": "incomplete"}


@router.get("")
def get_dashboard_stats():
    sync_from_csv()

    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    with db_conn() as conn:
        total = scalar(conn, "SELECT COUNT(*) FROM people")
        today_count = scalar(
            conn, "SELECT COUNT(*) FROM people WHERE discovery_date = :today", {"today": today}
        )
        week_count = scalar(
            conn, "SELECT COUNT(*) FROM people WHERE discovery_date >= :week_ago", {"week_ago": week_ago}
        )

    log_info = _latest_log_info()

    if run_state.running:
        pipeline_status = "running"
    else:
        pipeline_status = log_info["last_run_status"]

    return {
        "total_people": total,
        "new_today": today_count,
        "new_this_week": week_count,
        "last_run_time": log_info["last_run_time"],
        "last_run_new_people": log_info["last_run_new_people"],
        "pipeline_status": pipeline_status,
        "searxng": _check_searxng(),
        "docker": _check_docker(),
    }
