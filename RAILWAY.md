# Railway service settings

Why `railway.json` has no `startCommand`, and what the dashboard must match.

## The bug this replaced

`railway.json` used to carry:

```json
"startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT ..."
```

A `startCommand` **overrides the image's `CMD`**, and Railway runs it without a
shell. So `$PORT` was never expanded — uvicorn received the four literal
characters and failed:

```
Invalid value for '--port': '$PORT' is not a valid integer.
```

The Dockerfile's own shell-form `CMD` would have expanded it correctly, but it
was never reached. Two sources of truth for one decision, and the wrong one
won.

Now the port is resolved **in Python** (`backend/serve.py`) and there is no
command string for anything to expand. The image starts the same way whether a
shell is involved or not.

## Dashboard settings to verify

Under **Settings → Deploy**, these must be empty so the image's `CMD` is used:

| Setting          | Required value                                    |
| ---------------- | ------------------------------------------------- |
| Custom Start Command | **empty** — this is what caused the failure    |
| Custom Build Command | **empty** — the Dockerfile handles the build   |
| Healthcheck Path | `/api/ready`                                       |
| Healthcheck Timeout | `120`                                           |
| Root Directory   | empty (repository root — the Dockerfile is there)  |

If a Custom Start Command is set in the dashboard, it wins over `railway.json`
and re-introduces the exact bug. Clearing the field is the fix.

## Environment variables

Required:

| Variable        | Value                                                        |
| --------------- | ------------------------------------------------------------ |
| `ENVIRONMENT`   | `production`                                                  |
| `SECRET_KEY`    | 32+ bytes — `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL`  | `postgresql+psycopg://…` (note the driver — see below)        |
| `PUBLIC_URL`    | `https://helix-ai-app.vercel.app`                             |
| `API_URL`       | your Railway public URL                                       |

**Do not set `PORT`.** Railway injects it; setting it manually can bind a port
the router isn't forwarding to, which presents as a health-check timeout with
no error in the logs.

### The DATABASE_URL driver prefix

Railway's Postgres plugin exposes `postgresql://…`. SQLAlchemy 2.x maps that to
psycopg2, which is not installed — the image ships psycopg 3. Reference the
variable and rewrite the scheme:

```
DATABASE_URL=postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
```

Using `${{Postgres.*}}` references rather than pasted literals means a
credential rotation propagates automatically.

Optional but recommended:

| Variable         | Value        | Why |
| ---------------- | ------------ | --- |
| `EMAIL_PROVIDER` | `resend`     | Otherwise emails only land in `data/outbox/` inside the container |
| `RESEND_API_KEY` | `re_…`       | |
| `EMAIL_FROM`     | `Helix <no-reply@yourdomain.com>` | |
| `LOG_LEVEL`      | `info`       | `debug` for troubleshooting |
| `WEB_CONCURRENCY`| `1`          | Raise only if profiling shows CPU saturation |

## Why the healthcheck is `/api/ready`, not `/api/health`

`/api/health` answers "is the process alive?" and touches nothing external.
`/api/ready` answers "can this instance serve traffic?" and checks the
database, returning 503 when it can't.

Railway should watch **readiness**, so a deploy isn't marked healthy before the
database connection works. But note the consequence: if `DATABASE_URL` is wrong,
the deploy will fail its healthcheck and roll back — which is correct behaviour,
and the logs will name the reason.

## Reading a failed deploy

The startup log line states what the process decided:

```
Helix 4.0.0 starting · env=production · db=postgresql · 514 people · cookies=SameSite:none Secure:True
Split deployment detected (https://helix-ai-app.vercel.app ↔ https://<api>.up.railway.app)
```

| Symptom | Cause |
| ------- | ----- |
| `'$PORT' is not a valid integer` | A Custom Start Command is set in the dashboard |
| `SECRET_KEY must be set` / `too short` | Missing or under 32 bytes |
| `db=sqlite` in production | `DATABASE_URL` not set — data will vanish on redeploy |
| Healthcheck timeout, no errors | `PORT` manually set, or the app bound the wrong interface |
| `cookies=SameSite:lax` in a split deploy | `PUBLIC_URL`/`API_URL` are on the same host or unset |
| "Run Discovery" returns 503 immediately | Correct — `SEARXNG_BASE_URL` is unset. See below |
| Discovery "completes" but Total People stays 0 | `SEARXNG_BASE_URL` points at something unreachable. Check `GET /api/admin/status` |

## Discovery runs and SearXNG

`POST /api/run` behaves differently depending on `settings.is_hosted`
(production or staging):

- **Hosted** (this deployment): invokes `run.py` directly. If
  `SEARXNG_BASE_URL` is unset, the endpoint returns **503 before starting
  anything** — deliberately, rather than running for ~15s and reporting zero
  results for a reason nobody could see.
- **Local dev**: invokes `start.py`, which brings up the docker-compose
  SearXNG container and waits for it, exactly as before. Unchanged.

This distinction exists because `start.py` is a local-only convenience — it
runs `docker compose up -d` and polls `localhost:8080`, neither of which can
ever work inside a Railway container (no Docker socket, nothing listening on
its own loopback). Running it there was the original cause of "Run Finished"
with zero results: `start.py` failed at step one, so the actual pipeline
never ran at all.

**Getting SearXNG reachable from Railway** is the one piece of this that needs
your action — see `DEPLOYMENT.md` §4. In short: a self-hosted SearXNG (a
second Railway service from `docker.io/searxng/searxng:latest`, or a small
VPS) reachable from this service, with `SEARXNG_BASE_URL` pointed at it.
**Never set it to `localhost` here** — the audit at `GET /api/admin/status`
flags that explicitly, since it means the search backend was configured but
misconfigured, not simply left unset.

Once configured, a completed run reports one of:

| `pipeline_status` | Meaning |
| ------------------ | ------- |
| `completed` | Found and saved new people |
| `completed_zero_results` | Ran fine, SearXNG reachable, nobody new found |
| `completed_zero_results_searxng_unavailable` | SearXNG was unreachable this run — the infrastructure problem, distinct from a boring empty run |
| `failed` | The pipeline process crashed |

## Digest cron jobs

The image's working directory is `/app/backend`, so cron commands are relative
to that — not the repository root:

```
python workers/digest_worker.py --frequency daily      # 0 8 * * *
python workers/digest_worker.py --frequency weekly     # 0 8 * * 1
```
