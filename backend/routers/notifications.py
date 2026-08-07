from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core import deps
from services import notification_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def get_notifications(
    unread_only: bool = Query(False), user_id: int = Depends(deps.current_user_id)
):
    return {
        "notifications": notification_service.list_notifications(user_id, unread_only=unread_only),
        "unread_count": notification_service.unread_count(user_id),
    }


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user_id: int = Depends(deps.current_user_id)):
    notification_service.mark_read(user_id, notification_id)
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(user_id: int = Depends(deps.current_user_id)):
    notification_service.mark_all_read(user_id)
    return {"ok": True}
