#!/usr/bin/env python3
"""Block until the local SearXNG instance is healthy, or exit non-zero after
a timeout. Used by start.py, and safe to run standalone:

    python scripts/wait_for_searxng.py
    python scripts/wait_for_searxng.py --timeout 60 --url http://localhost:8080

This checks BOTH:
  1. /healthz responds 200 (container is up and serving)
  2. /search?format=json actually returns parseable JSON (the JSON API —
     which is what the pipeline actually depends on — is really working,
     not just that the container process is alive)
"""
from __future__ import annotations

import argparse
import sys
import time

import requests


def wait_for_searxng(base_url: str, timeout: float, poll_interval: float = 2.0) -> bool:
    base_url = base_url.rstrip("/")
    deadline = time.monotonic() + timeout
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        try:
            health_resp = requests.get(f"{base_url}/healthz", timeout=5)
            if health_resp.status_code == 200:
                json_resp = requests.get(
                    f"{base_url}/search",
                    params={"q": "healthcheck", "format": "json"},
                    timeout=5,
                )
                if json_resp.status_code == 200 and "json" in json_resp.headers.get("Content-Type", "").lower():
                    json_resp.json()  # confirm it actually parses
                    print(f"SearXNG is healthy and the JSON API works ({base_url}), after {attempt} attempt(s).")
                    return True
                print(f"[{attempt}] /healthz OK but JSON API not ready yet (status {json_resp.status_code}) — retrying...")
            else:
                print(f"[{attempt}] /healthz returned {health_resp.status_code} — retrying...")
        except requests.RequestException as e:
            print(f"[{attempt}] SearXNG not reachable yet ({e.__class__.__name__}) — retrying...")

        time.sleep(poll_interval)

    print(f"TIMED OUT after {timeout}s waiting for SearXNG at {base_url}.")
    print("Check: docker compose ps   /   docker compose logs searxng")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8080", help="SearXNG base URL")
    parser.add_argument("--timeout", type=float, default=90, help="Max seconds to wait")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between checks")
    args = parser.parse_args()

    ok = wait_for_searxng(args.url, args.timeout, args.poll_interval)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
