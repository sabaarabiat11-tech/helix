from __future__ import annotations

from fastapi import APIRouter, Depends

from core import deps
from database import sync_from_csv
from db import utcnow_iso
from services import insights_service

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("")
def get_insights(user_id: int = Depends(deps.current_user_id)):
    sync_from_csv()
    return {
        "generated_at": utcnow_iso(),
        "cards": insights_service.generate_daily_insights(user_id),
    }
