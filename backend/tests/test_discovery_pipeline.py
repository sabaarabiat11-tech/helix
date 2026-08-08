"""The discovery run trigger, its outcome reporting, and the SearXNG status
endpoint — the path this whole module exists to keep honest end to end:
button click -> subprocess -> real search -> database -> dashboard.
"""
from __future__ import annotations

import dataclasses
import subprocess
import sys

from services.pipeline_log import (
    STATUS_COMPLETED,
    STATUS_COMPLETED_ZERO_RESULTS,
    STATUS_COMPLETED_ZERO_RESULTS_SEARXNG_UNAVAILABLE,
    STATUS_FAILED,
    STATUS_INCOMPLETE,
    parse_run_log,
)

# --- pipeline_log.parse_run_log ---------------------------------------------
# These fixtures use the exact strings run.py and wait_for_searxng.py log, so
# a wording change in either place is exactly what would break this — see
# services/pipeline_log.py's module docstring.

SEARXNG_UNREACHABLE_LINE = (
    "2026-08-08 00:00:15 [WARNING] run: SearXNG at http://searxng.internal:8080 is not "
    "reachable/healthy. Continuing anyway (fail-soft) -- the searxng_search source will "
    "be skipped for this run. Run 'docker compose up -d' (or 'python start.py') to fix this."
)
SEARXNG_HEALTHY_LINE = (
    "SearXNG is healthy and the JSON API works (http://searxng.internal:8080), after 2 attempt(s)."
)


def test_zero_results_with_searxng_down_is_reported_as_infrastructure_failure():
    """This is the exact production symptom: the run "completes" (exit 0,
    fail-soft) but found nobody because its only working source was down. That
    must not look identical to a healthy run that legitimately found nobody new."""
    text = f"{SEARXNG_UNREACHABLE_LINE}\n=== Run complete: 0 new people added (target 20-30/week) ==="
    outcome = parse_run_log(text)
    assert outcome.status == STATUS_COMPLETED_ZERO_RESULTS_SEARXNG_UNAVAILABLE
    assert outcome.new_people == 0
    assert outcome.searxng_reachable is False
    assert outcome.succeeded is True  # the process did complete; this is not a crash


def test_zero_results_with_searxng_up_is_just_zero_results():
    """SearXNG working but nobody new found is a normal, boring outcome — must
    not be confused with the infrastructure-failure case above."""
    text = f"{SEARXNG_HEALTHY_LINE}\n=== Run complete: 0 new people added (target 20-30/week) ==="
    outcome = parse_run_log(text)
    assert outcome.status == STATUS_COMPLETED_ZERO_RESULTS
    assert outcome.searxng_reachable is True


def test_successful_run_with_results():
    text = f"{SEARXNG_HEALTHY_LINE}\n=== Run complete: 7 new people added (target 20-30/week) ==="
    outcome = parse_run_log(text)
    assert outcome.status == STATUS_COMPLETED
    assert outcome.new_people == 7
    assert outcome.succeeded is True


def test_unhandled_exception_is_failed_not_silently_zero():
    text = "Traceback (most recent call last):\n  File \"run.py\", line 40\nValueError: boom"
    outcome = parse_run_log(text)
    assert outcome.status == STATUS_FAILED
    assert outcome.succeeded is False


def test_process_that_never_reached_its_summary_line_is_incomplete_not_completed():
    """A process that was killed, or exited some other way run.py doesn't log
    about, must not be reported as a successful empty run."""
    text = "2026-08-08 00:00:00 [INFO] run: === AI x Biology LinkedIn discovery run starting ==="
    outcome = parse_run_log(text)
    assert outcome.status == STATUS_INCOMPLETE
    assert outcome.new_people is None
    assert outcome.succeeded is False


def test_real_historical_log_still_parses(tmp_path):
    """Regression pin against an actual log this pipeline produced, so a
    future regex tweak can't silently stop matching real output."""
    real_log = tmp_path / "run_real.log"
    real_log.write_text(
        "2026-08-07 00:30:27,201 [INFO] run: Checking local SearXNG readiness at "
        "http://localhost:8080 ...\n"
        "2026-08-07 00:47:50,854 [INFO] run: === Run complete: 3 new people added "
        "(target 20-30/week) ===\n",
        encoding="utf-8",
    )
    outcome = parse_run_log(real_log.read_text(encoding="utf-8"))
    assert outcome.status == STATUS_COMPLETED
    assert outcome.new_people == 3


# --- /api/run ----------------------------------------------------------------

def _settings_like(base, **overrides):
    """`Settings` is a frozen dataclass (deliberately — see config.py), so
    tests that need a different value build a modified copy and monkeypatch
    the *importing module's* `settings` name, rather than mutating the shared
    singleton in place."""
    return dataclasses.replace(base, **overrides)


def test_trigger_run_refuses_when_hosted_and_searxng_unconfigured(client, registered, monkeypatch):
    """The whole point of failing before spawning anything: a hosted deployment
    with no SEARXNG_BASE_URL should say so immediately, not spend ~15s running
    a subprocess just to report zero results for an undiscoverable reason."""
    import routers.run as run_router
    from config import settings

    auth, _, _ = registered()
    # is_hosted is a derived @property (from `environment`), not a plain
    # field, so it's overridden by switching environment to production rather
    # than by trying to replace the property itself.
    hosted = _settings_like(settings, environment="production", searxng_base_url="")
    monkeypatch.setattr(run_router, "settings", hosted)

    response = client.post("/api/run", headers=auth)
    assert response.status_code == 503
    assert "SEARXNG_BASE_URL" in response.json()["detail"]


def test_run_state_reports_never_run_before_any_run(client, registered):
    auth, _, _ = registered()
    body = client.get("/api/run/state", headers=auth).json()
    assert body["running"] is False
    assert body["status"] in ("never_run", None) or body["status"] == "never_run"


def test_pipeline_command_selects_run_py_when_hosted(monkeypatch):
    """The actual fix: a hosted deployment must invoke the pipeline directly,
    never the local-only Docker/localhost bootstrapper that can only fail
    there. Exercises the real decision function, not a re-implementation of it."""
    import routers.run as run_router
    from config import settings

    monkeypatch.setattr(run_router, "settings", _settings_like(settings, environment="production"))
    command = run_router._pipeline_command()
    assert command == [sys.executable, "run.py"]
    assert "start.py" not in command


def test_pipeline_command_keeps_start_py_for_local_dev(monkeypatch):
    """The existing local workflow (python start.py -> brings up Docker SearXNG
    -> runs the pipeline) must be unchanged outside a hosted deployment."""
    import routers.run as run_router
    from config import settings

    monkeypatch.setattr(run_router, "settings", _settings_like(settings, environment="development"))
    assert run_router._pipeline_command() == [sys.executable, "start.py"]


# --- /api/status --------------------------------------------------------------

def test_searxng_status_reports_not_configured_when_url_is_empty(monkeypatch):
    import routers.status as status_router
    from config import settings

    monkeypatch.setattr(status_router, "settings", _settings_like(settings, searxng_base_url=""))
    result = status_router._check_searxng()
    assert result["configured"] is False
    assert result["reachable"] is False
    # Must not have attempted a network call to a nonexistent target.


def test_searxng_status_probes_the_configured_url_not_a_hardcoded_one(monkeypatch):
    """This is the actual production bug: the status check used to hardcode
    localhost:8080 regardless of what was configured, so it could never
    report a hosted deployment's real SearXNG as reachable even when it was."""
    import routers.status as status_router
    from config import settings

    probed = {}

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}

        def json(self):
            return {"results": []}

    def fake_get(url, **kwargs):
        probed["url"] = url
        return FakeResponse()

    monkeypatch.setattr(
        status_router, "settings",
        _settings_like(settings, searxng_base_url="https://searxng.example.internal:8080"),
    )
    monkeypatch.setattr(status_router.requests, "get", fake_get)

    result = status_router._check_searxng()
    assert result["configured"] is True
    assert "searxng.example.internal" in probed["url"]
    assert result["json_api_working"] is True


# --- Startup configuration audit ---------------------------------------------

def test_audit_flags_unset_searxng_url_in_production():
    from config import audit_configuration, settings

    hosted_unconfigured = _settings_like(settings, environment="production", searxng_base_url="")
    import config as config_module

    original = config_module.settings
    try:
        config_module.settings = hosted_unconfigured
        problems = audit_configuration()
    finally:
        config_module.settings = original

    assert any("SEARXNG_BASE_URL is unset" in p for p in problems)


def test_audit_flags_localhost_searxng_url_in_production():
    import config as config_module
    from config import audit_configuration, settings

    hosted_localhost = _settings_like(
        settings, environment="production", searxng_base_url="http://localhost:8080"
    )
    original = config_module.settings
    try:
        config_module.settings = hosted_localhost
        problems = audit_configuration()
    finally:
        config_module.settings = original

    assert any("not reachable from inside a hosted container" in p for p in problems)


def test_audit_is_quiet_when_searxng_is_properly_configured():
    import config as config_module
    from config import audit_configuration, settings

    # Also needs a real database and mail provider configured, or those
    # unrelated warnings would make this assertion meaningless.
    healthy = _settings_like(
        settings,
        environment="production",
        searxng_base_url="https://searxng.example.com",
        database_url="postgresql+psycopg://u:p@host/db",
        email_provider="resend",
        public_url="https://helix.example.com",
        cookie_samesite="none",
    )
    original = config_module.settings
    try:
        config_module.settings = healthy
        problems = audit_configuration()
    finally:
        config_module.settings = original

    assert not any("SEARXNG" in p for p in problems)


# --- /api/admin/status --------------------------------------------------------

def test_admin_status_includes_searxng_section(client, registered):
    """This is the endpoint RAILWAY.md points operators at to diagnose
    exactly this class of problem, so it has to actually carry the
    information, not just database/email/cookies."""
    auth, user, _ = registered()
    from db import db_conn, execute
    with db_conn() as conn:
        execute(conn, "UPDATE users SET is_admin = :a WHERE id = :i", {"a": True, "i": user["id"]})

    body = client.get("/api/admin/status", headers=auth).json()
    assert "searxng" in body
    for key in ("configured", "base_url", "reachable", "json_api_working"):
        assert key in body["searxng"]
    assert "last_run_status" in body["pipeline"]


# --- Real local SearXNG (skipped if the dev container isn't running) --------

def _local_searxng_up() -> bool:
    try:
        proc = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", "ai-bio-searxng"],
            capture_output=True, text=True, timeout=5,
        )
        return proc.returncode == 0 and "healthy" in proc.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def test_status_endpoint_against_the_real_local_searxng(client, registered, monkeypatch):
    """Not a mock: this hits the actual healthy ai-bio-searxng container this
    project runs locally, proving _check_searxng's fix works against a real
    server, not just a stubbed one. Skips itself if that container isn't up."""
    import pytest

    if not _local_searxng_up():
        pytest.skip("local ai-bio-searxng container is not running")

    import routers.status as status_router
    from config import settings

    auth, _, _ = registered()
    monkeypatch.setattr(
        status_router, "settings", _settings_like(settings, searxng_base_url="http://localhost:8080")
    )

    body = client.get("/api/status", headers=auth).json()
    assert body["searxng"]["configured"] is True
    assert body["searxng"]["reachable"] is True
    assert body["searxng"]["json_api_working"] is True
