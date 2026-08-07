from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core import deps
from database import sync_from_csv
from services import search_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(q: str = Query("", min_length=0), user_id: int = Depends(deps.current_user_id)):
    if not q.strip():
        return {"people": [], "companies": [], "watchlist": []}
    sync_from_csv()
    return search_service.global_search(q.strip(), user_id=user_id)
