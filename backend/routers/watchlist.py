from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import deps
from database import sync_from_csv
from services import watchlist_service

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistUpdate(BaseModel):
    notes: str | None = None
    tags: str | None = None
    priority: str | None = None
    status: str | None = None
    reminder_date: str | None = None


@router.get("")
def get_watchlist(user_id: int = Depends(deps.current_user_id)):
    sync_from_csv()
    return watchlist_service.list_watchlist(user_id)


@router.post("/{person_id}")
def follow_person(person_id: int, user_id: int = Depends(deps.current_user_id)):
    sync_from_csv()
    try:
        return watchlist_service.follow(user_id, person_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{person_id}")
def unfollow_person(person_id: int, user_id: int = Depends(deps.current_user_id)):
    return watchlist_service.unfollow(user_id, person_id)


@router.patch("/{person_id}")
def update_watchlist_entry(
    person_id: int, body: WatchlistUpdate, user_id: int = Depends(deps.current_user_id)
):
    try:
        return watchlist_service.update_entry(user_id, person_id, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
