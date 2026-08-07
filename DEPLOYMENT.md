# Deploying Helix

Target architecture:

```
   Browser
      │
      ├──────────────► Vercel          static SPA on a global CDN
      │                  │
      │                  └── VITE_API_URL ──┐
      │                                     ▼
      └──────────────────────────────► Railway         FastAPI + PostgreSQL
                                            │
                                            └────────► SearXNG  (VPS or Railway)
```

Three services, three reasons:

- **Vercel** serves static files from the edge. A React bundle has no reason to
  be served by a Python process in one region.
- **Railway** runs a real container: WebSockets, background workers, a
  persistent PostgreSQL, and subprocesses all work. The API needs every one of
  those.
- **SearXNG** is only used by the discovery pipeline, not by user requests.

---

## 1. PostgreSQL on Railway

Create the project and add the database first, so the API has something to
connect to on its first boot.

```
New Project → Deploy PostgreSQL
```

Railway exposes `DATABASE_URL` as `postgresql://…`. SQLAlchemy needs the driver
named explicitly, so set the API's variable to:

```
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

then override the scheme in the API service:

```
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
```

Copy the values from the Postgres service's *Variables* tab. The schema is
created automatically on first boot — there is no migration step to run.

## 2. The API on Railway

```
New → GitHub Repo → sabaarabiat11-tech/helix
```

Railway reads `railway.json`, builds the root `Dockerfile`, and health-checks
`/api/ready`.

### Required variables

| Variable        | Value                                        |
| --------------- | -------------------------------------------- |
| `ENVIRONMENT`   | `production`                                 |
| `SECRET_KEY`    | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL`  | the `postgresql+psycopg://…` URL from step 1  |
| `PUBLIC_URL`    | your Vercel URL, e.g. `https://helix-ai-app.vercel.app` |
| `API_URL`       | your Railway URL, e.g. `https://helix-api.up.railway.app` |
| `EMAIL_PROVIDER`| `resend`                                     |
| `RESEND_API_KEY`| from [resend.com/api-keys](https://resend.com/api-keys) |
| `EMAIL_FROM`    | `Helix <no-reply@yourdomain.com>`            |

`PUBLIC_URL` and `API_URL` are not cosmetic. Every email link and OAuth
redirect is built from them, and the app compares their hosts to decide the
session-cookie policy — see *Why cookies need care* below.

Do **not** set `PORT`; Railway injects it.

### Optional

| Variable                      | Default | Notes |
| ----------------------------- | ------- | ----- |
| `REQUIRE_EMAIL_VERIFICATION`  | `false` | Turn on once mail delivery is confirmed working |
| `SIGNUP_ENABLED`              | `true`  | Set `false` to close registration |
| `ALLOW_USER_TRIGGERED_RUNS`   | `false` in production | Admins can still trigger runs |
| `GOOGLE_CLIENT_ID` / `_SECRET`| —       | Callback: `<API_URL>/api/auth/oauth/google/callback` |
| `GITHUB_CLIENT_ID` / `_SECRET`| —       | Callback: `<API_URL>/api/auth/oauth/github/callback` |
| `SEARXNG_BASE_URL`            | `http://localhost:8080` | See step 4 |

## 3. The frontend on Vercel

```
Add New → Project → import the same repo
Root Directory: frontend
```

`frontend/vercel.json` supplies the framework preset, SPA rewrites, cache
headers and CSP.

One environment variable:

```
VITE_API_URL = https://helix-api.up.railway.app
```

It is read at **build time**, not runtime — changing it requires a redeploy,
not just a restart.

### Order matters

Vercel and Railway each need the other's URL. Deploy Railway first with a
placeholder `PUBLIC_URL`, deploy Vercel with the real `VITE_API_URL`, then go
back and correct `PUBLIC_URL` on Railway. The second Railway deploy is what
makes sign-in work.

## 4. SearXNG

**Recommendation: a small VPS, not Railway.**

SearXNG is not part of a user request path. It is called by the discovery
pipeline on a schedule, it holds no state worth persisting, and it makes
outbound requests to search engines continuously. Putting it on Railway means
paying for an always-on service that is idle almost all the time, and it puts
Railway's egress IP in front of search engines that rate-limit aggressively —
the exact problem that made public SearXNG instances unusable for this project.

A €4–5/month VPS (Hetzner, DigitalOcean) with its own IP is cheaper, gives the
pipeline a stable reputation with search engines, and is easy to replace.

```bash
git clone https://github.com/sabaarabiat11-tech/helix.git
cd helix
docker compose up -d searxng
```

Then point the API at it:

```
SEARXNG_BASE_URL=http://<vps-ip>:8080
```

Firewall it to the Railway egress range, or run it behind a reverse proxy with
basic auth — it should not be an open public instance.

**If you'd rather keep everything on Railway:** add a second service from the
same repo with `docker.io/searxng/searxng:latest`, mount the `searxng/`
directory, and set `SEARXNG_BASE_URL` to the internal service URL. It works;
it's just the more expensive and more rate-limited option.

## 5. Digest emails

The digest worker is a scheduled command, not a server. On Railway:

```
New → Cron Job
Schedule:  0 8 * * *        (daily 08:00 UTC)
Command:   python workers/digest_worker.py --frequency daily
```

and a second one:

```
Schedule:  0 8 * * 1        (Mondays 08:00 UTC)
Command:   python workers/digest_worker.py --frequency weekly
```

Check what would be sent, without sending it:

```bash
python backend/workers/digest_worker.py --frequency weekly --dry-run
```

---

## Why cookies need care

The refresh token lives in an httpOnly cookie. When the frontend and API are on
**different hosts** — which `helix-ai-app.vercel.app` and `helix-api.up.railway.app`
are — a `SameSite=Lax` cookie is simply not sent, so sign-in appears to succeed
and then every subsequent request returns 401.

`backend/config.py` derives this rather than asking you to configure it: it
compares the hosts of `PUBLIC_URL` and `API_URL`, and when they differ in a
hosted environment it sets `SameSite=None; Secure` automatically. Both must be
correct for that to work, which is the real reason step 2 insists on them.

You can confirm what the running instance decided from its startup log:

```
Helix 4.0.0 starting · env=production · db=postgresql · … · cookies=SameSite:none Secure:True
Split deployment detected (https://helix-ai-app.vercel.app ↔ https://helix-api.up.railway.app)
```

## Verifying a deployment

```bash
curl https://<api>/api/health     # liveness — process is up
curl https://<api>/api/ready      # readiness — database reachable
```

`/api/ready` returns 503 when the database is unreachable, which is what
Railway's health check watches. `/api/health` deliberately checks nothing
external: a liveness probe that fails during a database blip would restart a
healthy process and turn a recoverable outage into a self-inflicted one.

Then in a browser: sign up, confirm the verification email arrives, sign out,
sign back in. If sign-in succeeds but the next page 401s, `PUBLIC_URL` or
`API_URL` is wrong — see above.

## Custom domains

Putting both on subdomains of one registrable domain (`app.helix.com` and
`api.helix.com`) makes them same-site. Cookies then work with `SameSite=Lax`,
which is stricter and avoids third-party-cookie blocking in Safari and
Firefox — worth doing before launch.

```
COOKIE_DOMAIN=.helix.com
```

Set that once both are on the shared parent domain, and the derived policy
relaxes to `Lax` on its own.

## Rolling back

Railway and Vercel both keep previous deployments — redeploy an earlier build
from the dashboard. The database is not versioned with the code; schema changes
are additive (`db/migrations.py` only ever adds columns), so an older image
runs against a newer schema without breaking.

## Cost

| Service    | Tier             | Cost                |
| ---------- | ---------------- | ------------------- |
| Vercel     | Hobby            | free                |
| Railway    | Hobby            | $5/month credit     |
| PostgreSQL | Railway add-on   | included in usage   |
| Resend     | Free             | 3,000 emails/month  |
| SearXNG VPS| Hetzner CX22     | ~€4/month           |
