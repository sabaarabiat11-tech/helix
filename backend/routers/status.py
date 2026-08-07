from __future__ import annotations

import subprocess

import requests
from fastapi import APIRouter

router = APIRouter(prefix="/api/status", tags=["status"])

SEARXNG_URL = "http://localhost:8080"


def _check_searxng() -> dict:
    result = {"reachable": False, "healthy": False, "json_api_working": False}
    try:
        health = requests.get(f"{SEARXNG_URL}/healthz", timeout=3)
        result["reachable"] = True
        result["healthy"] = health.status_code == 200
    except requests.RequestException:
        return result

    try:
        search = requests.get(
            f"{SEARXNG_URL}/search",
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
