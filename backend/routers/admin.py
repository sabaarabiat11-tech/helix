"""Operator endpoints. Administrator-only.

Exists so the things that normally happen on a schedule can be verified
immediately after deploying, without waiting until tomorrow morning or
shelling into the container.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from config import audit_configuration, settings
from core import deps
from database import MASTER_CSV, sync_from_csv
from db import db_conn, engine, scalar
from routers.status import _check_searxng
from run_state import run_state
from services import scheduler_service, user_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/status")
def admin_status(_: dict = Depends(deps.admin_user)):
    """The deployment's own view of whether it is correctly configured.

    Same checks the startup audit logs, exposed over HTTP so they can be read
    without access to the platform's log viewer.
    """
    with db_conn() as conn:
        people = scalar(conn, "SELECT COUNT(*) FROM people") or 0

    return {
        "environment": settings.environment,
        "database": {
            "dialect": engine.dialect.name,
            "people": people,
            "persistent": engine.dialect.name == "postgresql",
        },
        "email": {
            "provider": settings.email_provider,
            "delivers_real_mail": settings.email_provider != "console",
            "from": settings.email_from,
        },
        "cookies": {
            "samesite": settings.cookie_samesite,
            "secure": settings.cookie_secure,
            "cross_site": settings.is_cross_site,
        },
        "urls": {"public": settings.public_url, "api": settings.api_url},
        "scheduler": {
            "enabled": settings.enable_scheduler,
            "hour_utc": settings.scheduler_hour,
            "weekday": settings.scheduler_weekday,
        },
        "pipeline": {
            "master_csv_present": MASTER_CSV.exists(),
            "users": user_service.count_users(),
            "last_run_status": run_state.status_payload()["status"],
            "last_run_new_people": run_state.status_payload()["new_people"],
        },
        # What "Run Discovery" will actually try to reach right now — the
        # single most direct answer to "why is Total People stuck at 0".
        "searxng": _check_searxng(),
        # Empty means nothing is misconfigured.
        "warnings": audit_configuration(),
    }


@router.post("/send-digests")
def send_digests(
    frequency: str = Query("daily", pattern="^(daily|weekly)$"),
    _: dict = Depends(deps.admin_user),
):
    """Send a digest cadence to every subscriber now, ignoring the schedule.

    Deliberately admin-only and not rate-limited by cadence: it is for proving
    delivery works, and an operator who runs it twice gets two emails, which is
    the honest behaviour rather than a silent no-op.
    """
    summaries = scheduler_service.run_due_digests(force=frequency)
    if not summaries:
        raise HTTPException(status_code=500, detail="The digest run produced no result")
    return summaries[0]


@router.post("/sync")
def force_sync(_: dict = Depends(deps.admin_user)):
    """Re-import the pipeline's CSV into the database immediately.

    Normally happens on boot and after every discovery run; this covers the
    case where the CSV was placed on disk out of band.
    """
    result = sync_from_csv(force=True)
    return {
        "synced": result.get("synced", False),
        "rows": result.get("rows", 0),
        "new_people": len(result.get("new_people") or []),
        "new_companies": result.get("new_companies") or [],
    }
