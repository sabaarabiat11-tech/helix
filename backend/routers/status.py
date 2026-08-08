from __future__ import annotations

import subprocess

import requests
from fastapi import APIRouter

from config import settings

router = APIRouter(prefix="/api/status", tags=["status"])


def _check_searxng() -> dict:
    """Reachability of whatever SearXNG endpoint this deployment is actually
    configured to use — never a hardcoded address.

    Previously this always probed `http://localhost:8080`, regardless of
    `SEARXNG_BASE_URL`. On Railway that meant the dashboard reported
    "unreachable" no matter what the operator configured, because nothing was
    ever listening on the container's own loopback interface — it was
    checking the wrong host, not reporting a real outage.
    """
    base_url = settings.searxng_base_url
    result = {
        "configured": bool(base_url),
        "base_url": base_url or None,
        "reachable": False,
        "healthy": False,
        "json_api_working": False,
    }
    if not base_url:
        return result

    try:
        health = requests.get(f"{base_url}/healthz", timeout=3)
        result["reachable"] = True
        result["healthy"] = health.status_code == 200
    except requests.RequestException:
        return result

    try:
        search = requests.get(
            f"{base_url}/search",
            params={"q": "healthcheck", "format": "json"},
            timeout=5,
        )
        if search.status_code == 200 and "json" in search.headers.get("Content-Type", "").lower():
            search.json()
            result["json_api_working"] = True
    except (requests.RequestException, ValueError):
        pass

    return result


def _check_docker() -> dict:
    """Best-effort local-dev diagnostic only.

    A hosted deployment (Railway, Render, ...) has no Docker daemon inside its
    own container by design, so `container_found: false` there is the
    *correct* and expected answer, not a fault — `_check_searxng` above, keyed
    off the real configured URL, is the signal that actually matters in
    production. This stays around only because it's still useful when running
    the app locally against the docker-compose SearXNG.
    """
    result = {"docker_cli_available": False, "container_found": False, "container_status": None}
    try:
        proc = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}|{{.State.Health.Status}}", "ai-bio-searxng"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        result["docker_cli_available"] = True
        if proc.returncode == 0:
            result["container_found"] = True
            parts = proc.stdout.strip().split("|")
            result["container_status"] = parts[0] if parts else None
            result["container_health"] = parts[1] if len(parts) > 1 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return result


@router.get("")
def get_status():
    return {
        "searxng": _check_searxng(),
        "docker": _check_docker(),
    }
