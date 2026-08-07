from __future__ import annotations

from fastapi import APIRouter

from database import sync_from_csv
from services import timeline_service

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


@router.get("")
def get_timeline():
    sync_from_csv()
    return timeline_service.get_timeline()
