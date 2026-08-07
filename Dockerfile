# Helix API — the image Railway builds and runs.
#
# Backend only. The frontend is a static build served by Vercel's CDN, so
# bundling it here would mean rebuilding and redeploying the API every time a
# button changes colour, and would put the SPA behind a single origin instead
# of a global edge network.
#
# The discovery pipeline (src/, start.py, config.yaml) ships in the image
# because the API can trigger it and the digest worker runs from the same code.
#
#   docker build -t helix-api .
#   docker run -p 8000:8000 --env-file .env helix-api

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so a code change doesn't invalidate the pip layer.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    # psycopg is only needed in production, where DATABASE_URL points at
    # PostgreSQL. Installed here so the same image works either way.
    && pip install --no-cache-dir "psycopg[binary]>=3.1"

COPY backend/ ./backend/
COPY src/ ./src/
COPY start.py run.py config.yaml ./

# Writable state. On Railway with PostgreSQL this holds only pipeline
# artifacts (logs, reports); with SQLite it also holds the database, which
# then needs a mounted volume to survive a redeploy.
RUN mkdir -p data \
    && adduser --disabled-password --gecos "" --uid 10001 helix \
    && chown -R helix:helix /app
USER helix

EXPOSE 8000

# Liveness, not readiness — see the endpoint docstrings in backend/main.py for
# why a health check must not touch the database.
#
# The port is read from the environment rather than hardcoded: Railway assigns
# a random $PORT, so a probe pinned to 8000 would check a port nothing is
# listening on and report every healthy container as unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen(f\"http://127.0.0.1:{os.getenv('PORT','8000')}/api/health\").status==200 else 1)"

WORKDIR /app/backend

# Exec form, and the port is resolved inside Python by serve.py.
#
# The obvious `CMD uvicorn main:app --port ${PORT:-8000}` works here but is a
# trap: any platform that overrides the image's CMD with its own start command
# (Railway's `deploy.startCommand`, Fly's `[processes]`) re-introduces the
# literal-`$PORT` bug, because those are frequently run without a shell.
# Keeping the port logic in Python means the entrypoint behaves identically
# whether or not a shell is in the picture.
CMD ["python", "serve.py"]
