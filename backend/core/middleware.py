"""Production middleware: security headers and rate limiting.

Both are implemented in-process with no external dependency. That is a
deliberate trade-off worth stating plainly:

The rate limiter's counters live in this process's memory. With a single
Railway instance that is exactly right — it stops credential stuffing and
password-reset spam with zero infrastructure. Scale to multiple instances and
each one keeps its own counters, so the effective limit multiplies by the
replica count. The fix is a shared store, which is why the limiter sits behind
`RateLimitBackend`: swapping in Redis is one new class, not a rewrite.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings

log = logging.getLogger("helix.middleware")


# --- Security headers -------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Defence-in-depth response headers.

    Note there is no Content-Security-Policy here. This process serves a JSON
    API, and in the target deployment the HTML comes from Vercel — a CSP set
    here would not apply to the pages that need one, and `vercel.json` carries
    it instead. Setting a misleading one here would be worse than none.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS only over real HTTPS — sending it over plain http is
        # meaningless, and sending it in local development would pin
        # localhost to https in the browser and break the next dev session.
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


# --- Rate limiting ----------------------------------------------------------

@dataclass(frozen=True)
class RateLimitRule:
    requests: int
    window_seconds: int

    @property
    def description(self) -> str:
        return f"{self.requests} requests per {self.window_seconds}s"


# Only endpoints where abuse is cheap and consequential are limited. Ordinary
# reads are left alone — throttling a dashboard the user is actively clicking
# through creates support tickets, not security.
RATE_LIMIT_RULES: dict[str, RateLimitRule] = {
    "/api/auth/login": RateLimitRule(10, 300),
    "/api/auth/signup": RateLimitRule(5, 3600),
    "/api/auth/forgot-password": RateLimitRule(5, 3600),
    "/api/auth/reset-password": RateLimitRule(10, 3600),
    "/api/auth/verify-email": RateLimitRule(20, 3600),
    "/api/auth/resend-verification": RateLimitRule(5, 3600),
    "/api/auth/change-password": RateLimitRule(10, 3600),
    "/api/users/me/send-test-digest": RateLimitRule(5, 3600),
    "/api/run": RateLimitRule(5, 3600),
}


class RateLimitBackend(Protocol):
    """Contract a shared store (Redis, Memcached) must satisfy to replace the
    in-memory backend when running more than one instance."""

    def hit(self, key: str, rule: RateLimitRule) -> tuple[bool, int]: ...


class InMemoryRateLimitBackend:
    """Sliding-window counter kept in process memory.

    A deque of timestamps per key gives an exact sliding window rather than the
    burst-at-the-boundary behaviour of fixed windows, and stays small because
    entries outside the window are discarded on every read.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_sweep = time.monotonic()

    def hit(self, key: str, rule: RateLimitRule) -> tuple[bool, int]:
        """Record an attempt. Returns (allowed, seconds_until_retry)."""
        now = time.monotonic()
        window_start = now - rule.window_seconds
        timestamps = self._hits[key]

        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) >= rule.requests:
            retry_after = max(1, int(timestamps[0] + rule.window_seconds - now))
            return False, retry_after

        timestamps.append(now)
        self._maybe_sweep(now)
        return True, 0

    def _maybe_sweep(self, now: float) -> None:
        """Drop keys that have gone quiet, so a long-running process doesn't
        accumulate an entry per IP forever."""
        if now - self._last_sweep < 600:
            return
        self._last_sweep = now
        stale = [key for key, hits in self._hits.items() if not hits or now - hits[-1] > 3600]
        for key in stale:
            del self._hits[key]
        if stale:
            log.debug("Rate limiter swept %s idle keys", len(stale))


backend: RateLimitBackend = InMemoryRateLimitBackend()


def client_identity(request: Request) -> str:
    """Best available caller identity.

    Behind Railway's proxy the socket address is the proxy, so
    X-Forwarded-For's first entry is the real client. That header is
    caller-controlled in general, but on a platform that overwrites it at the
    edge it is trustworthy — and the fallback keeps things working locally.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rule = RATE_LIMIT_RULES.get(request.url.path)

        # Only guard state-changing calls; a GET to one of these paths (or a
        # CORS preflight) is not an attempt.
        if rule is None or request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await call_next(request)

        key = f"{client_identity(request)}:{request.url.path}"
        allowed, retry_after = backend.hit(key, rule)

        if not allowed:
            log.warning("Rate limit hit for %s on %s", key, request.url.path)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many attempts. Please wait a moment and try again.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
