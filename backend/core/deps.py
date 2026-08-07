"""FastAPI authentication dependencies and cookie handling.

`current_user` is the single gate every protected endpoint goes through, so
there is exactly one place where "who is calling?" is decided.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, Response, status

from config import settings
from core.security import decode_access_token
from services import user_service

REFRESH_COOKIE = "helix_refresh"
OAUTH_STATE_COOKIE = "helix_oauth_state"

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not signed in",
    headers={"WWW-Authenticate": "Bearer"},
)


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def optional_user(request: Request) -> dict | None:
    """Resolve the caller if they're signed in, otherwise None. Use for
    endpoints that work either way."""
    token = _bearer_token(request)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None

    user = user_service.get_by_id(user_id)
    if not user or not user["is_active"]:
        return None
    return user


def current_user(user: dict | None = Depends(optional_user)) -> dict:
    """Require a signed-in caller. Raises 401 otherwise."""
    if user is None:
        raise CREDENTIALS_EXCEPTION
    return user


def current_user_id(user: dict = Depends(current_user)) -> int:
    return user["id"]


def verified_user(user: dict = Depends(current_user)) -> dict:
    """Require a signed-in caller with a confirmed email — only enforced when
    the deployment turns verification on."""
    if settings.require_email_verification and not user["email_verified"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address to continue",
        )
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an administrator account",
        )
    return user


# --- Cookies ----------------------------------------------------------------

def set_refresh_cookie(response: Response, token: str) -> None:
    """httpOnly so page JavaScript — and therefore XSS — cannot read the
    session; Secure and SameSite come from config so local http development
    still works while production gets the strict settings."""
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        path="/",
    )


def get_refresh_cookie(request: Request) -> str:
    return request.cookies.get(REFRESH_COOKIE, "")


def set_oauth_state_cookie(response: Response, state: str) -> None:
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        max_age=600,  # the round trip to a provider and back is a matter of minutes
        httponly=True,
        secure=settings.cookie_secure,
        # The provider redirects back cross-site, so a Strict cookie would not
        # be sent on the callback. Lax is the tightest setting that works.
        samesite="lax",
        domain=settings.cookie_domain or None,
        path="/",
    )


def clear_oauth_state_cookie(response: Response) -> None:
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain or None,
        path="/",
    )


def client_info(request: Request) -> tuple[str, str]:
    """(user_agent, ip) for session bookkeeping. Honours X-Forwarded-For, which
    is what a hosted deployment behind a proxy or load balancer sets."""
    user_agent = request.headers.get("user-agent", "")
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    return user_agent, ip
