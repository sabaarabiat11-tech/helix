#!/usr/bin/env python3
"""One-command startup: brings up the local SearXNG Docker container, waits
until it's actually healthy (container health check AND a working JSON API
response — not just "container running"), then runs the discovery pipeline.

Usage:
    python start.py

This is what you should point Windows Task Scheduler at for the weekly run
(see README.md) — it's the one command that guarantees Docker is up before
the pipeline tries to search.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.wait_for_searxng import wait_for_searxng  # noqa: E402


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=PROJECT_ROOT, **kwargs)


def docker_compose_up() -> bool:
    # Prefer the modern `docker compose` subcommand; fall back to the legacy
    # standalone `docker-compose` if that's what's installed.
    for base_cmd in (["docker", "compose"], ["docker-compose"]):
        try:
            result = run(base_cmd + ["up", "-d"])
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            continue
    print("ERROR: could not run 'docker compose up -d' (or 'docker-compose up -d'). "
          "Is Docker Desktop installed and running?")
    return False


def main() -> int:
    print("=== Step 1/3: starting local SearXNG (Docker) ===")
    if not docker_compose_up():
        return 1

    print()
    print("=== Step 2/3: waiting for SearXNG to become healthy ===")
    if not wait_for_searxng("http://localhost:8080", timeout=90):
        print("Aborting — pipeline will not run without a working SearXNG instance.")
        return 1

    print()
    print("=== Step 3/3: running the discovery pipeline ===")
    result = run([sys.executable, "run.py"])
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
