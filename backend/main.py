"""Helix API — the web application behind the AI × Biology discovery product.

Layering, outermost to innermost:

    routers/    HTTP only — parse, authorize, delegate, serialize
    services/   all business logic; no FastAPI imports anywhere in here
    db/         schema, engine, portable query helpers
    core/       cross-cutting security and request plumbing

The discovery pipeline (src/, run.py, start.py) sits outside all of it and is
never imported or modified. The only interaction is triggering `python
start.py` as a subprocess when someone clicks "Run Discovery" — exactly what
they would do from a terminal — and reading the CSV it produces.

Run locally with:
    uvicorn main:app --reload --port 8000        (from the backend/ directory)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import audit_configuration, settings
from core import deps
from core.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from database import sync_from_csv
from db import db_conn, engine, init_db, scalar
from routers import (
    analytics,
    auth,
    companies,
    discoveries,
    export,
    insights,
    notifications,
    recommendations,
    reports,
    run,
    search,
    stats,
    status,
    timeline,
    users,
    watchlist,
)

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
)
log = logging.getLogger("helix")

APP_VERSION = "4.0.0"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    result = sync_from_csv(force=True)
    log.info(
        "%s %s starting · env=%s · db=%s · %s people · cookies=SameSite:%s Secure:%s",
        settings.app_name,
        APP_VERSION,
        settings.environment,
        "postgresql" if not settings.is_sqlite else "sqlite",
        result.get("rows", 0),
        settings.cookie_samesite,
        settings.cookie_secure,
    )
    if settings.is_cross_site:
        log.info("Split deployment detected (%s ↔ %s)", settings.public_url, settings.api_url)
    log.info("CORS allows: %s", ", ".join(settings.cors_origins) or "(nothing)")
    if not settings.is_production and settings.email_provider == "console":
        log.info("Email provider is 'console' — messages are written to data/outbox/")

    # Surface misconfiguration in the deploy log rather than letting it show up
    # later as "sign-in doesn't work" with no obvious cause.
    for problem in audit_configuration():
        log.warning("CONFIG: %s", problem)

    yield

    # Graceful shutdown. Railway sends SIGTERM and waits before SIGKILL;
    # returning connections to the pool here means in-flight queries finish and
    # PostgreSQL doesn't accumulate abandoned backends across deploys.
    log.info("Shutting down — disposing database connection pool")
    engine.dispose()


app = FastAPI(
    title=f"{settings.app_name} API",
    version=APP_VERSION,
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Middleware runs in reverse registration order, so the last one added is the
# outermost. Security headers are registered last so they apply to every
# response — including the 429s produced by the rate limiter below it.
app.add_middleware(RateLimitMiddleware)

# Origins come from config, never hardcoded, so the same image serves
# localhost in development and a Vercel domain in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Set CORS_ORIGIN_REGEX to also admit Vercel preview builds, whose
    # hostnames carry a per-build hash and can't be listed in advance.
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,  # required for the httpOnly refresh cookie
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

app.add_middleware(SecurityHeadersMiddleware)


# --- Routers ----------------------------------------------------------------
# Auth is public by definition. Everything else requires a signed-in caller;
# declaring that once per router here — rather than on ~40 individual
# endpoints — means a new endpoint is protected by default, and forgetting a
# dependency can't silently expose data.

app.include_router(auth.router)

PROTECTED = [Depends(deps.current_user)]

app.include_router(users.router)  # every endpoint declares its own dependency
app.include_router(stats.router, dependencies=PROTECTED)
app.include_router(discoveries.router, dependencies=PROTECTED)
app.include_router(companies.router, dependencies=PROTECTED)
app.include_router(analytics.router, dependencies=PROTECTED)
app.include_router(reports.router, dependencies=PROTECTED)
app.include_router(status.router, dependencies=PROTECTED)
app.include_router(timeline.router, dependencies=PROTECTED)
app.include_router(export.router, dependencies=PROTECTED)
# These declare per-endpoint dependencies because their handlers need the
# caller's identity, not just the fact that there is one.
app.include_router(recommendations.router)
app.include_router(insights.router)
app.include_router(watchlist.router)
app.include_router(notifications.router)
app.include_router(search.router)
# run/ mixes an authenticated HTTP API with a WebSocket that authenticates via
# a query parameter, so it handles authorization endpoint by endpoint.
app.include_router(run.router)


@app.get("/api/health")
def health():
    """Liveness: is the process up?

    Deliberately touches nothing external. A liveness probe that checks the
    database will fail during a brief database blip and cause the platform to
    restart a perfectly healthy process — turning a recoverable dependency
    outage into an outage of your own making. Readiness is where dependencies
    belong.
    """
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "version": APP_VERSION,
    }


@app.get("/api/ready")
def ready():
    """Readiness: can this instance actually serve traffic?

    Checks the database, because without it every authenticated request fails.
    Returns 503 when it can't, so a load balancer routes around this instance
    instead of sending it requests that are guaranteed to error.
    """
    checks: dict[str, object] = {}
    healthy = True

    try:
        with db_conn() as conn:
            people = scalar(conn, "SELECT COUNT(*) FROM people")
        checks["database"] = {
            "status": "ok",
            "dialect": engine.dialect.name,
            "people": people,
        }
    except Exception as exc:
        healthy = False
        log.error("Readiness check failed on database: %s", exc)
        checks["database"] = {"status": "error", "error": str(exc)[:200]}

    # Reported, never fatal: the email provider only matters when something is
    # actually being sent, and a mail outage shouldn't drain the whole service.
    checks["email_provider"] = {"status": "ok", "provider": settings.email_provider}

    body = {"status": "ready" if healthy else "not_ready", "version": APP_VERSION, "checks": checks}
    return body if healthy else JSONResponse(status_code=503, content=body)


# --- Static frontend --------------------------------------------------------
# In production the built SPA is served by this same process, so a deployment
# is one container and one origin — no CORS, no separate static host. In
# development Vite serves the frontend and this block simply doesn't apply.

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        """Serve the built SPA, falling back to index.html so client-side
        routes (/login, /settings, ...) survive a hard refresh."""
        candidate = (FRONTEND_DIST / full_path).resolve()
        # Containment check: a crafted path must not escape the dist directory.
        if candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST.resolve()):
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

else:
    @app.get("/", include_in_schema=False)
    def dev_root():
        return {
            "message": f"{settings.app_name} API is running.",
            "frontend": "Not built. Run `npm run dev` in frontend/, or `npm run build` to serve it from here.",
            "docs": "/api/docs" if not settings.is_production else None,
        }
