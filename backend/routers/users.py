"""Account profile, preferences and email settings."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import deps
from services import digest_service, oauth_service, personalization_service, user_service
from services.oauth_service import OAuthError

router = APIRouter(prefix="/api/users", tags=["users"])


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=500)


class PreferencesUpdate(BaseModel):
    theme: str | None = None
    focus_areas: list[str] | None = None
    preferred_companies: list[str] | None = None
    preferred_locations: list[str] | None = None
    seniority_preference: str | None = None
    min_score: int | None = Field(default=None, ge=0, le=100)
    digest_frequency: str | None = None
    digest_hour: int | None = Field(default=None, ge=0, le=23)
    timezone: str | None = None
    notify_new_recommendations: bool | None = None
    notify_pipeline_complete: bool | None = None
    notify_new_companies: bool | None = None
    notify_weekly_report: bool | None = None
    notify_ai_insights: bool | None = None


@router.get("/me")
def get_me(user: dict = Depends(deps.current_user)):
    return {
        "user": user,
        "preferences": user_service.get_preferences(user["id"]),
        "linked_providers": oauth_service.linked_providers(user["id"]),
        "has_password": user_service.has_password(user["id"]),
    }


@router.patch("/me")
def update_me(payload: ProfileUpdate, user: dict = Depends(deps.current_user)):
    try:
        updated = user_service.update_profile(user["id"], name=payload.name, avatar_url=payload.avatar_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user": updated}


@router.get("/me/preferences")
def get_preferences(user: dict = Depends(deps.current_user)):
    return user_service.get_preferences(user["id"])


@router.patch("/me/preferences")
def update_preferences(payload: PreferencesUpdate, user: dict = Depends(deps.current_user)):
    try:
        return user_service.update_preferences(
            user["id"], **payload.model_dump(exclude_unset=True, exclude_none=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/send-test-digest")
def send_test_digest(user: dict = Depends(deps.current_user)):
    """Send the user their own digest right now, so they can see exactly what
    the scheduled one will look like before committing to a cadence."""
    prefs = user_service.get_preferences(user["id"])
    period = prefs.get("digest_frequency", "weekly")
    if period == "off":
        period = "weekly"

    sent = digest_service.send_digest(user, period)
    if not sent:
        raise HTTPException(
            status_code=502,
            detail="Could not send the email. Check the server's email configuration.",
        )
    return {"ok": True, "sent_to": user["email"], "period": period}


@router.get("/me/recommendation-history")
def recommendation_history(limit: int = 100, user: dict = Depends(deps.current_user)):
    return {"history": personalization_service.history(user["id"], limit=limit)}


@router.delete("/me/oauth/{provider}")
def unlink_oauth(provider: str, user: dict = Depends(deps.current_user)):
    try:
        oauth_service.unlink_provider(user["id"], provider)
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "linked_providers": oauth_service.linked_providers(user["id"])}


@router.delete("/me")
def delete_account(user: dict = Depends(deps.current_user)):
    """Permanently delete the account and everything scoped to it. The shared
    discovery corpus is untouched — it isn't the user's data."""
    user_service.delete_user(user["id"])
    return {"ok": True}
