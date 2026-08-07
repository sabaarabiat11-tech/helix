"""Shared test fixtures.

Every test run gets a throwaway database and a console mail provider, so the
suite never touches real data and never sends real email. The environment is
configured *before* `main` is imported, because `config.Settings` is resolved
once at import time.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def pytest_configure(config):
    """Point the app at a scratch database before anything imports config."""
    tmp = Path(tempfile.mkdtemp(prefix="helix_test_"))
    os.environ["DATABASE_URL"] = os.environ.get(
        # Allows CI to run the identical suite against PostgreSQL by setting
        # TEST_DATABASE_URL, which is how the Postgres job proves the data
        # layer is portable rather than just claiming it.
        "TEST_DATABASE_URL",
        f"sqlite:///{(tmp / 'test.db').as_posix()}",
    )
    os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("EMAIL_PROVIDER", "console")
    os.environ.setdefault("PUBLIC_URL", "http://localhost:5173")
    os.environ.setdefault("API_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def app():
    import main

    return main.app


@pytest.fixture()
def client(app):
    """A TestClient with lifespan run, so startup migrations have happened."""
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def unique_email():
    """A fresh address per call — accounts persist for the whole session, so
    tests must not collide on email uniqueness."""
    import uuid

    def _make(prefix: str = "user") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"

    return _make


@pytest.fixture()
def registered(client, unique_email):
    """Create an account and return (auth_header, user)."""

    def _make(prefix: str = "user", password: str = "test-password-123"):
        email = unique_email(prefix)
        response = client.post(
            "/api/auth/signup",
            json={"email": email, "password": password, "name": prefix.title()},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return {"Authorization": f"Bearer {body['access_token']}"}, body["user"], password

    return _make


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Rate-limit counters are process-global; without this, a test that logs
    in repeatedly would start failing the moment another test uses the same
    endpoint."""
    from core import middleware

    middleware.backend = middleware.InMemoryRateLimitBackend()
    yield
