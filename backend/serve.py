"""Production entrypoint.

Reads the listen port from the environment **in Python** rather than relying on
the shell to expand `$PORT` in a command string.

That indirection exists for a concrete reason. Platforms that run a container
with an explicit start command (Railway, Fly, Cloud Run) may execute it in exec
form — no shell, no variable expansion — so a command like

    uvicorn main:app --port $PORT

passes the four characters `$PORT` straight to uvicorn, which fails with
"Invalid value for '--port': '$PORT' is not a valid integer". The same command
works perfectly when a shell happens to be involved, which makes the bug
environment-dependent and easy to miss locally.

Starting uvicorn programmatically sidesteps it entirely: there is no command
string to expand, and the port is an `int` before uvicorn ever sees it.

Run with:  python serve.py
"""
from __future__ import annotations

import logging
import os
import sys

import uvicorn

log = logging.getLogger("helix.serve")


def _env_int(name: str, default: int) -> int:
    """Read an integer setting, failing loudly rather than silently guessing.

    A platform that sets PORT to something unparseable is misconfigured, and
    quietly falling back to 8000 would bind the wrong port and present as an
    unexplained health-check timeout instead of an error.
    """
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        sys.exit(f"Environment variable {name}={raw!r} is not a valid integer.")


def main() -> None:
    port = _env_int("PORT", 8000)
    # Railway runs one container per replica and scales horizontally, so extra
    # in-process workers mostly duplicate memory. Overridable for hosts where
    # vertical scaling is the cheaper axis.
    workers = _env_int("WEB_CONCURRENCY", 1)

    log.info("Starting Helix API on 0.0.0.0:%s (workers=%s)", port, workers)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        # Behind Railway's edge the socket peer is the proxy, so without these
        # every client would look like the same IP — which would make the rate
        # limiter throttle all users as one, and mark request scheme as http.
        proxy_headers=True,
        forwarded_allow_ips="*",
        workers=workers if workers > 1 else None,
        # Finish in-flight requests when the platform sends SIGTERM during a
        # redeploy, instead of cutting them off mid-response.
        timeout_graceful_shutdown=20,
        access_log=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
