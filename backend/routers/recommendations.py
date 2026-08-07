from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core import deps
from database import sync_from_csv
from services import personalization_service

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("")
def get_recommendations(
    limit: int = Query(10, ge=1, le=50),
    exclude_followed: bool = Query(False),
    user_id: int = Depends(deps.current_user_id),
):
    """Ranked for the signed-in user. `recommended_today` keeps its original
    name so existing clients are unaffected; it is now personalized."""
    sync_from_csv()
    ranked = personalization_service.rank_for_user(
        user_id, limit=limit, exclude_followed=exclude_followed
    )
    personalization_service.record_shown(user_id, ranked)
    return {"recommended_today": ranked}


@router.get("/bundle")
def get_recommendation_bundle(user_id: int = Depends(deps.current_user_id)):
    """Everything the Recommendations page shows, in one round trip: today's
    top 5, the week's top 10, people to follow, trending companies, and the
    most active organizations — plus which preferences were applied."""
    sync_from_csv()
    bundle = personalization_service.recommendations_bundle(user_id)
    personalization_service.record_shown(user_id, bundle["top_today"])
    return bundle
