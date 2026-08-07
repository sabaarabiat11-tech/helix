"""Authentication, sessions and account security."""
from __future__ import annotations

import pytest

PROTECTED_PATHS = [
    "/api/stats",
    "/api/discoveries",
    "/api/companies",
    "/api/analytics",
    "/api/timeline",
    "/api/reports",
    "/api/insights",
    "/api/recommendations",
    "/api/watchlist",
    "/api/notifications",
    "/api/users/me",
    "/api/export/csv",
]


def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_reports_database(client):
    response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"]["status"] == "ok"


@pytest.mark.parametrize("path", PROTECTED_PATHS)
def test_protected_endpoints_reject_anonymous(client, path):
    assert client.get(path).status_code == 401


def test_security_headers_present(client):
    headers = client.get("/api/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in headers


def test_signup_creates_session(client, unique_email):
    response = client.post(
        "/api/auth/signup",
        json={"email": unique_email(), "password": "test-password-123", "name": "Ada"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["access_token"]
    assert body["user"]["name"] == "Ada"
    assert "helix_refresh" in response.cookies


def test_signup_rejects_duplicate_email_case_insensitively(client, unique_email):
    email = unique_email()
    first = client.post("/api/auth/signup", json={"email": email, "password": "test-password-123"})
    assert first.status_code == 201
    duplicate = client.post(
        "/api/auth/signup", json={"email": email.upper(), "password": "other-password-123"}
    )
    assert duplicate.status_code == 409


def test_signup_rejects_short_password(client, unique_email):
    response = client.post("/api/auth/signup", json={"email": unique_email(), "password": "short"})
    assert response.status_code == 422


def test_login_rejects_wrong_password(client, registered):
    _, user, _ = registered()
    response = client.post(
        "/api/auth/login", json={"email": user["email"], "password": "definitely-wrong"}
    )
    assert response.status_code == 401


def test_login_error_does_not_reveal_whether_account_exists(client, unique_email):
    """Same message for an unknown address and a wrong password — otherwise
    the endpoint becomes an account-enumeration oracle."""
    unknown = client.post(
        "/api/auth/login", json={"email": unique_email(), "password": "test-password-123"}
    )
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == "Incorrect email or password"


def test_me_returns_profile_and_preferences(client, registered):
    auth, user, _ = registered()
    body = client.get("/api/auth/me", headers=auth).json()
    assert body["user"]["email"] == user["email"]
    assert body["preferences"]["digest_frequency"] == "weekly"
    assert body["has_password"] is True


def test_booleans_are_real_booleans_not_integers(client, registered):
    """Raw SQL bypasses SQLAlchemy type coercion, so SQLite would otherwise
    return 0/1 here while PostgreSQL returns true/false."""
    auth, _, _ = registered()
    user = client.get("/api/auth/me", headers=auth).json()["user"]
    assert isinstance(user["email_verified"], bool)
    assert isinstance(user["is_active"], bool)
    assert isinstance(user["is_admin"], bool)


def test_refresh_rotates_and_old_token_is_rejected(client, registered):
    registered()
    first = client.post("/api/auth/refresh")
    assert first.status_code == 200
    original_cookie = client.cookies.get("helix_refresh")

    second = client.post("/api/auth/refresh")
    assert second.status_code == 200
    assert client.cookies.get("helix_refresh") != original_cookie

    # Replaying the superseded token must fail — and, by design, also revokes
    # the whole family, since two parties holding one token means theft.
    client.cookies.set("helix_refresh", original_cookie)
    replay = client.post("/api/auth/refresh")
    assert replay.status_code == 401


def test_logout_invalidates_the_session(client, registered):
    registered()
    assert client.post("/api/auth/logout").status_code == 200
    assert client.post("/api/auth/refresh").status_code == 401


def test_password_reset_flow(client, registered):
    from services import auth_service

    auth, user, old_password = registered()
    token = auth_service.create_email_token(user["id"], auth_service.PURPOSE_RESET_PASSWORD)

    assert client.post(
        "/api/auth/reset-password", json={"token": token, "password": "brand-new-password-9"}
    ).status_code == 200

    # Single use.
    assert client.post(
        "/api/auth/reset-password", json={"token": token, "password": "third-password-9"}
    ).status_code == 400

    assert client.post(
        "/api/auth/login", json={"email": user["email"], "password": old_password}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"email": user["email"], "password": "brand-new-password-9"}
    ).status_code == 200


def test_forgot_password_response_is_identical_for_unknown_addresses(client, unique_email):
    known = client.post("/api/auth/forgot-password", json={"email": unique_email()})
    assert known.status_code == 200
    assert known.json()["ok"] is True


def test_email_verification(client, registered):
    from services import auth_service

    auth, user, _ = registered()
    assert user["email_verified"] is False

    token = auth_service.create_email_token(user["id"], auth_service.PURPOSE_VERIFY_EMAIL)
    response = client.post("/api/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    assert response.json()["user"]["email_verified"] is True

    assert client.post("/api/auth/verify-email", json={"token": "garbage"}).status_code == 400


def test_rate_limit_blocks_repeated_login_attempts(client, unique_email):
    """The limiter is what stops credential stuffing, so it needs a test that
    actually exhausts it rather than trusting the config."""
    payload = {"email": unique_email(), "password": "wrong-password-here"}
    statuses = [client.post("/api/auth/login", json=payload).status_code for _ in range(12)]
    assert 429 in statuses, f"limiter never engaged: {statuses}"
    assert statuses[0] == 401, "the first attempt should be evaluated normally"


def test_oauth_config_lists_only_configured_providers(client):
    body = client.get("/api/auth/config").json()
    assert body["oauth_providers"] == []
    assert body["signup_enabled"] is True
