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

## Digest cron jobs

The image's working directory is `/app/backend`, so cron commands are relative
to that — not the repository root:

```
python workers/digest_worker.py --frequency daily      # 0 8 * * *
python workers/digest_worker.py --frequency weekly     # 0 8 * * 1
```
