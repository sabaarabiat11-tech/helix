"""Authentication endpoints.

A note on responses: signup, forgot-password and resend-verification always
report success regardless of whether the address is registered. Revealing which
emails have accounts would turn these into an account-enumeration oracle.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from config import settings
from core import deps
from services import auth_service, oauth_service, user_service
from services.auth_service import AuthError
from services.email import sender
from services.oauth_service import OAuthError

log = logging.getLogger("helix.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- Schemas ----------------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8, max_length=200)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(default="", max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


# --- Helpers ----------------------------------------------------------------

def _session_response(response: Response, user: dict, session: dict) -> dict:
    deps.set_refresh_cookie(response, session["refresh_token"])
    return {
        "user": user,
        "access_token": session["access_token"],
        "token_type": "bearer",
        "expires_in": session["expires_in"],
    }


def _send_verification(user: dict) -> None:
    token = auth_service.create_email_token(user["id"], auth_service.PURPOSE_VERIFY_EMAIL)
    sender.send_verification_email(user, token)


# --- Public config ----------------------------------------------------------

@router.get("/config")
def auth_config():
    """What the sign-in UI needs to render itself correctly for this
    deployment — which OAuth buttons exist, whether signup is open."""
    return {
        "signup_enabled": settings.signup_enabled,
        "require_email_verification": settings.require_email_verification,
        "oauth_providers": oauth_service.available_providers(),
        "app_name": settings.app_name,
    }


# --- Email + password -------------------------------------------------------

@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, request: Request, response: Response):
    if not settings.signup_enabled:
        raise HTTPException(status_code=403, detail="New account signups are currently disabled")

    try:
        auth_service.validate_password(payload.password)
        user = user_service.create_user(
            email=payload.email, password=payload.password, name=payload.name
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _send_verification(user)
    prefs = user_service.get_preferences(user["id"])
    sender.send_welcome_email(user, prefs.get("digest_frequency", "weekly"))

    user_agent, ip = deps.client_info(request)
    session = auth_service.issue_session(user["id"], user_agent, ip)
    return _session_response(response, user, session)


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response):
    try:
        user = auth_service.authenticate(payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user_agent, ip = deps.client_info(request)
    session = auth_service.issue_session(user["id"], user_agent, ip)
    return _session_response(response, user, session)


@router.post("/refresh")
def refresh(request: Request, response: Response):
    try:
        session = auth_service.rotate_session(
            deps.get_refresh_cookie(request), *deps.client_info(request)
        )
    except AuthError as exc:
        deps.clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return _session_response(response, session["user"], session)


@router.post("/logout")
def logout(request: Request, response: Response):
    auth_service.revoke_session(deps.get_refresh_cookie(request))
    deps.clear_refresh_cookie(response)
    return {"ok": True}


@router.post("/logout-all")
def logout_all(response: Response, user: dict = Depends(deps.current_user)):
    auth_service.revoke_all_sessions(user["id"])
    deps.clear_refresh_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(deps.current_user)):
    return {
        "user": user,
        "preferences": user_service.get_preferences(user["id"]),
        "linked_providers": oauth_service.linked_providers(user["id"]),
        "has_password": user_service.has_password(user["id"]),
    }


# --- Email verification -----------------------------------------------------

@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest):
    try:
        user = auth_service.verify_email(payload.token)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "user": user}


@router.post("/resend-verification")
def resend_verification(user: dict = Depends(deps.current_user)):
    if user["email_verified"]:
        return {"ok": True, "already_verified": True}
    _send_verification(user)
    return {"ok": True, "already_verified": False}


# --- Password reset ---------------------------------------------------------

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    user = user_service.get_by_email(payload.email)
    if user and user["is_active"]:
        token = auth_service.create_email_token(user["id"], auth_service.PURPOSE_RESET_PASSWORD)
        sender.send_password_reset_email(user, token)
    else:
        log.info("Password reset requested for unknown address %s", payload.email)

    return {
        "ok": True,
        "message": "If an account exists for that address, a reset link is on its way.",
    }


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, response: Response):
    try:
        auth_service.reset_password(payload.token, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # reset_password revokes every session; make sure the stale cookie in this
    # browser goes too, so the user lands on a clean sign-in.
    deps.clear_refresh_cookie(response)
    return {"ok": True, "message": "Password updated. You can sign in now."}


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, user: dict = Depends(deps.current_user)):
    try:
        auth_service.change_password(user["id"], payload.current_password, payload.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


# --- OAuth ------------------------------------------------------------------

@router.get("/oauth/{provider}/start")
def oauth_start(provider: str, next: str = "/"):
    """Begin the OAuth dance. Returns a redirect to the provider with the
    signed state also stored in a cookie for the callback to compare."""
    try:
        url, state = oauth_service.build_authorize_url(provider, next_path=next)
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    deps.set_oauth_state_cookie(response, state)
    return response


@router.get("/oauth/{provider}/callback")
def oauth_callback(
    provider: str,
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
):
    """Provider redirect target.

    Always ends in a redirect back to the SPA — on success with a one-time
    handoff code in the fragment-free query string, on failure with a readable
    message — because the user's browser lands here directly and must not see
    raw JSON.
    """
    def fail(message: str) -> RedirectResponse:
        redirect = RedirectResponse(
            sender.app_url(f"/login?error={_quote(message)}"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
        deps.clear_oauth_state_cookie(redirect)
        return redirect

    if error:
        return fail(f"{provider.capitalize()} sign-in was cancelled")
    if not code or not state:
        return fail("Sign-in response was incomplete")

    # The state must match the cookie this server set AND carry a valid
    # signature — together these defeat CSRF on the callback.
    if state != request.cookies.get(deps.OAUTH_STATE_COOKIE, ""):
        return fail("Sign-in request expired, please try again")

    try:
        parsed = oauth_service.parse_state(state)
        if parsed.get("p") != provider:
            return fail("Sign-in request did not match")

        access_token = oauth_service.exchange_code(provider, code)
        profile = oauth_service.fetch_profile(provider, access_token)
        user = oauth_service.resolve_user(provider, profile)
    except OAuthError as exc:
        return fail(str(exc))
    except Exception:
        log.exception("Unexpected failure in %s OAuth callback", provider)
        return fail("Something went wrong signing you in")

    user_agent, ip = deps.client_info(request)
    session = auth_service.issue_session(user["id"], user_agent, ip)

    next_path = parsed.get("next") or "/"
    if not next_path.startswith("/"):
        # Never redirect to an absolute URL supplied through state — that would
        # be an open redirect.
        next_path = "/"

    redirect = RedirectResponse(
        sender.app_url(f"/auth/callback?next={_quote(next_path)}"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    # The SPA has no access token yet; it calls /refresh on load, and this
    # cookie is what makes that succeed.
    deps.set_refresh_cookie(redirect, session["refresh_token"])
    deps.clear_oauth_state_cookie(redirect)
    return redirect


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
