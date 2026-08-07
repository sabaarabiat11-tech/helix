"""OAuth 2.0 sign-in for Google, GitHub and LinkedIn.

Implemented directly against each provider's HTTP endpoints rather than through
a framework, because the flow is small and the security-relevant parts — state
validation, account linking — are clearer when they're visible.

Providers whose client id/secret are absent are simply not offered: the API
reports which ones are configured and the UI renders only those buttons, so a
deployment with no OAuth apps registered still works normally.

**Account linking.** If an OAuth identity's verified email matches an existing
account, the identity is linked to it rather than creating a duplicate. That is
what lets someone sign up with a password and later click "Continue with
Google" and land in the same account. Providers that don't verify emails are
treated as unverified and never auto-link.
"""
from __future__ import annotations

import json
import logging
import secrets
from urllib.parse import urlencode

import httpx

from config import OAuthProviderConfig, settings
from core.security import sign_state, verify_state
from db import db_conn, execute, insert_returning_id, row, utcnow_iso
from services import user_service

log = logging.getLogger("helix.oauth")

HTTP_TIMEOUT = 15.0


class OAuthError(Exception):
    """Any failure in the OAuth exchange. Message is safe to show the user."""


def available_providers() -> list[dict]:
    return [
        {"id": name, "label": name.capitalize()}
        for name in settings.enabled_oauth_providers
    ]


def _provider_config(provider: str) -> OAuthProviderConfig:
    config = settings.oauth_providers.get(provider)
    if config is None:
        raise OAuthError(f"Unknown sign-in provider: {provider}")
    if not config.configured:
        raise OAuthError(f"{provider.capitalize()} sign-in is not enabled on this deployment")
    return config


def build_authorize_url(provider: str, next_path: str = "/") -> tuple[str, str]:
    """Return (authorize_url, state). The caller stores `state` in a short-lived
    cookie and compares it on the callback."""
    config = _provider_config(provider)

    # The state carries the post-login destination and a nonce, HMAC-signed so
    # the callback can verify this server issued it and that the redirect
    # target wasn't tampered with.
    nonce = secrets.token_urlsafe(16)
    payload = json.dumps({"n": nonce, "p": provider, "next": next_path}, separators=(",", ":"))
    state = f"{_b64(payload)}.{sign_state(payload)}"

    params = {
        "client_id": config.client_id,
        "redirect_uri": settings.oauth_redirect_uri(provider),
        "response_type": "code",
        "scope": config.scope,
        "state": state,
    }
    if provider == "google":
        # Ask for a refresh-free, always-fresh consent screen selection so
        # switching Google accounts works as users expect.
        params["prompt"] = "select_account"

    return f"{config.authorize_url}?{urlencode(params)}", state


def parse_state(state: str) -> dict:
    try:
        encoded, signature = state.split(".", 1)
        payload = _unb64(encoded)
    except (ValueError, UnicodeDecodeError) as exc:
        raise OAuthError("Sign-in request was malformed") from exc

    if not verify_state(payload, signature):
        raise OAuthError("Sign-in request could not be verified")

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise OAuthError("Sign-in request was malformed") from exc


def exchange_code(provider: str, code: str) -> str:
    """Trade the authorization code for an access token."""
    config = _provider_config(provider)
    data = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "code": code,
        "redirect_uri": settings.oauth_redirect_uri(provider),
        "grant_type": "authorization_code",
    }
    try:
        response = httpx.post(
            config.token_url,
            data=data,
            headers={"Accept": "application/json"},
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise OAuthError(f"Could not reach {provider.capitalize()}") from exc

    if response.status_code >= 400:
        log.error("%s token exchange failed (%s): %s", provider, response.status_code, response.text[:300])
        raise OAuthError(f"{provider.capitalize()} rejected the sign-in attempt")

    try:
        token = response.json().get("access_token")
    except ValueError as exc:
        raise OAuthError(f"{provider.capitalize()} returned an unreadable response") from exc

    if not token:
        raise OAuthError(f"{provider.capitalize()} did not return an access token")
    return token


def fetch_profile(provider: str, access_token: str) -> dict:
    """Normalize each provider's user endpoint into
    {provider_account_id, email, email_verified, name, avatar_url}."""
    config = _provider_config(provider)
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    try:
        response = httpx.get(config.userinfo_url, headers=headers, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthError(f"Could not read your {provider.capitalize()} profile") from exc

    if provider == "google":
        return {
            "provider_account_id": str(data.get("sub") or ""),
            "email": (data.get("email") or "").strip(),
            "email_verified": bool(data.get("email_verified")),
            "name": (data.get("name") or "").strip(),
            "avatar_url": data.get("picture") or "",
        }

    if provider == "linkedin":
        return {
            "provider_account_id": str(data.get("sub") or ""),
            "email": (data.get("email") or "").strip(),
            "email_verified": bool(data.get("email_verified")),
            "name": (data.get("name") or "").strip(),
            "avatar_url": data.get("picture") or "",
        }

    if provider == "github":
        email = (data.get("email") or "").strip()
        email_verified = False
        if not email:
            # GitHub omits the email from /user when the user keeps it private;
            # the dedicated endpoint returns it when the token has user:email.
            email, email_verified = _github_primary_email(headers)
        else:
            email_verified = True
        return {
            "provider_account_id": str(data.get("id") or ""),
            "email": email,
            "email_verified": email_verified,
            "name": (data.get("name") or data.get("login") or "").strip(),
            "avatar_url": data.get("avatar_url") or "",
        }

    raise OAuthError(f"Unsupported provider: {provider}")


def _github_primary_email(headers: dict) -> tuple[str, bool]:
    try:
        response = httpx.get(
            "https://api.github.com/user/emails", headers=headers, timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        for entry in response.json():
            if entry.get("primary"):
                return (entry.get("email") or "").strip(), bool(entry.get("verified"))
    except (httpx.HTTPError, ValueError):
        log.warning("Could not read GitHub email addresses")
    return "", False


def resolve_user(provider: str, profile: dict) -> dict:
    """Find, link, or create the account behind an OAuth identity."""
    account_id = profile.get("provider_account_id")
    if not account_id:
        raise OAuthError(f"{provider.capitalize()} did not identify your account")

    # 1. This exact identity has signed in before.
    with db_conn() as conn:
        link = row(
            conn,
            "SELECT user_id FROM oauth_accounts "
            "WHERE provider = :provider AND provider_account_id = :account_id",
            {"provider": provider, "account_id": account_id},
        )
    if link:
        user = user_service.get_by_id(link["user_id"])
        if not user:
            raise OAuthError("The linked account no longer exists")
        if not user["is_active"]:
            raise OAuthError("This account has been disabled")
        return user

    email = (profile.get("email") or "").strip()

    # 2. A verified email matching an existing account links to it. Requiring
    #    verification is what stops someone registering an unverified address
    #    at a provider to take over a Helix account.
    if email and profile.get("email_verified"):
        existing = user_service.get_by_email(email)
        if existing:
            if not existing["is_active"]:
                raise OAuthError("This account has been disabled")
            _link_identity(existing["id"], provider, account_id, email)
            if not existing["email_verified"]:
                user_service.mark_email_verified(existing["id"])
            log.info("Linked %s identity to existing user %s", provider, existing["id"])
            return user_service.get_by_id(existing["id"])

    # 3. Otherwise create a new account.
    if not email:
        raise OAuthError(
            f"{provider.capitalize()} didn't share an email address. "
            "Make your email public there, or sign up with an email and password."
        )
    if not settings.signup_enabled:
        raise OAuthError("New account signups are currently disabled")

    user = user_service.create_user(
        email=email,
        password=None,
        name=profile.get("name") or "",
        avatar_url=profile.get("avatar_url") or "",
        email_verified=bool(profile.get("email_verified")),
    )
    _link_identity(user["id"], provider, account_id, email)
    log.info("Created user %s from %s sign-in", user["id"], provider)
    return user


def _link_identity(user_id: int, provider: str, account_id: str, email: str) -> None:
    with db_conn() as conn:
        insert_returning_id(
            conn,
            """
            INSERT INTO oauth_accounts (user_id, provider, provider_account_id, email, created_at)
            VALUES (:user_id, :provider, :account_id, :email, :created_at)
            """,
            {
                "user_id": user_id,
                "provider": provider,
                "account_id": account_id,
                "email": email,
                "created_at": utcnow_iso(),
            },
        )


def linked_providers(user_id: int) -> list[str]:
    with db_conn() as conn:
        found = execute(
            conn,
            "SELECT provider FROM oauth_accounts WHERE user_id = :user_id ORDER BY provider",
            {"user_id": user_id},
        ).mappings().all()
    return [r["provider"] for r in found]


def unlink_provider(user_id: int, provider: str) -> None:
    """Remove a linked identity, refusing to leave the account unreachable."""
    remaining = [p for p in linked_providers(user_id) if p != provider]
    if not remaining and not user_service.has_password(user_id):
        raise OAuthError(
            "Set a password before unlinking your only sign-in method, "
            "otherwise you'd be locked out."
        )
    with db_conn() as conn:
        execute(
            conn,
            "DELETE FROM oauth_accounts WHERE user_id = :user_id AND provider = :provider",
            {"user_id": user_id, "provider": provider},
        )


# --- base64url without padding ----------------------------------------------

def _b64(value: str) -> str:
    import base64

    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _unb64(value: str) -> str:
    import base64

    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding).decode("utf-8")
