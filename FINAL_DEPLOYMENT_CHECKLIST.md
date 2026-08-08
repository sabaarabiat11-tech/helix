# Final deployment checklist

Everything that could be automated is done. What remains needs credentials
only you have.

**Three steps. About ten minutes.**

---

## Current state

| | |
| --- | --- |
| Frontend | ✅ Live — https://helix-ai-app.vercel.app |
| Backend | ✅ Live — https://helix-production-c193.up.railway.app |
| Environment | ✅ `production` (auto-detected from Railway) |
| CORS | ✅ Accepts the Vercel origin |
| Cookies | ✅ `HttpOnly; SameSite=none; Secure` |
| API docs | ✅ Disabled in production |
| Signup / login | ✅ Verified against the live API |
| Health / ready | ✅ Both 200 |
| **Database** | ⚠️ **SQLite — wiped on every redeploy** |
| **Email** | ⚠️ **`console` — nobody receives anything** |
| **Corpus** | ⚠️ **Empty (0 people)** |

The three warnings are the three steps below.

---

## Step 1 — PostgreSQL (5 min) · REQUIRED

Without this every account, watchlist and note is erased on each deploy.
Railway's container filesystem is ephemeral.

**1.** Railway project → **New** → **Database** → **Add PostgreSQL**

**2.** Open your **API service** → **Variables** → add:

```
DATABASE_URL=postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
```

> The `+psycopg` matters. Railway's own `DATABASE_URL` starts `postgresql://`,
> which SQLAlchemy maps to psycopg2 — not installed. The image ships psycopg 3.
> Using `${{Postgres.*}}` references rather than pasted values means a
> credential rotation propagates by itself.

**3.** Redeploy.

Nothing else. Tables are created on boot, and if a SQLite file is present its
contents are copied across automatically — verified moving all 563 rows,
including the boolean and id-sequence conversions PostgreSQL needs.

**Verify:**
```bash
curl -s https://helix-production-c193.up.railway.app/api/ready
```
`"dialect"` should read `postgresql`.

---

## Step 2 — Resend (3 min) · REQUIRED for email

Until this is set, verification, password-reset and digest emails are written
to a file inside the container and nobody receives them.

**1.** Create a key at [resend.com/api-keys](https://resend.com/api-keys)

**2.** Verify a sending domain at
[resend.com/domains](https://resend.com/domains) — or skip it and use
`onboarding@resend.dev`, which only delivers to your own address (fine for
testing, not for real users).

**3.** Railway → **Variables**:

```
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_your_key_here
EMAIL_FROM=Helix <no-reply@yourdomain.com>
```

**4.** Redeploy.

If the key is missing or wrong the app logs the reason and falls back to the
console provider — it never crashes, and signup keeps working.

**Verify:** sign up with a real address and check the inbox. Or, as an admin:
```bash
curl -X POST "https://helix-production-c193.up.railway.app/api/admin/send-digests?frequency=daily" \
  -H "Authorization: Bearer <your access token>"
```

---

## Step 3 — Populate the corpus (2 min) · REQUIRED for a useful dashboard

The dashboard is empty because `data/linkedin_master.csv` is gitignored — it
holds 514 real people's names, employers and profile URLs, and publishing that
to a public repository would not be appropriate. Your local copy is intact.

Pick one:

**A. Upload your existing CSV** — Railway → your service → **Volumes**, mount
one at `/app/data`, then copy `data/linkedin_master.csv` into it. It imports on
the next boot, and again after every pipeline run.

**B. Run the pipeline against production** — the corpus fills itself on the
first scheduled run. **Needs `SEARXNG_BASE_URL` pointed at a reachable SearXNG
instance first** — without it, "Run Discovery" now correctly refuses to start
(503) rather than running and reporting zero results for an invisible reason.
See [DEPLOYMENT.md](DEPLOYMENT.md) §4 for why a small VPS beats hosting SearXNG
on Railway, and [RAILWAY.md](RAILWAY.md) for how a run's outcome is reported.
Check `GET /api/admin/status` → `searxng` at any time to see exactly what's
configured and whether it's reachable right now.

**C. Leave it empty** — everything works, there is simply nothing to rank yet.

---

## Optional

| Variable | Effect |
| --- | --- |
| `REQUIRE_EMAIL_VERIFICATION=true` | Blocks sign-in until confirmed. Turn on **after** Step 2 |
| `SIGNUP_ENABLED=false` | Closes registration |
| `SCHEDULER_HOUR=8` | UTC hour for the daily email (default 8) |
| `ENABLE_SCHEDULER=false` | Only if you set up real Railway cron jobs instead |
| `GOOGLE_CLIENT_ID` / `_SECRET` | Enables the Google button. Callback: `<API_URL>/api/auth/oauth/google/callback` |
| `GITHUB_CLIENT_ID` / `_SECRET` | Enables the GitHub button |

OAuth is fully implemented; providers without credentials are simply hidden.

---

## Done automatically — nothing for you to do

- **Environment detection** — `RAILWAY_PUBLIC_DOMAIN` implies production and
  supplies `API_URL`, so the cross-site cookie policy resolves itself
- **Cookie policy** — `SameSite=None; Secure` derived by comparing
  `PUBLIC_URL` and `API_URL` hosts; the failure mode is subtle enough that it
  shouldn't be a manual setting
- **Schema creation** and forward migrations on boot
- **SQLite → PostgreSQL import**, guarded so it can't merge into live data
- **Daily and weekly digests** — scheduled in-process, claimed via the database
  so a redeploy can't double-send and multiple replicas can't either
- **Discovery imports** — every completed run syncs into the database
- **Dashboard auto-refresh** — polls while the tab is visible, re-renders only
  when the data actually changed
- **Rate limiting**, security headers, split liveness/readiness probes
- **Startup configuration audit** — remaining problems are logged as `CONFIG:`
  warnings and exposed at `GET /api/admin/status`

---

## Verifying the finished deployment

```bash
API=https://helix-production-c193.up.railway.app

curl -s $API/api/health   # {"status":"ok", ...}
curl -s $API/api/ready    # "dialect":"postgresql"
```

Then in a browser at https://helix-ai-app.vercel.app: sign up, confirm the
email arrives, sign out, sign back in, and reload — the session should survive
the reload. If sign-in works but the next request 401s, `PUBLIC_URL` or
`API_URL` is wrong; [RAILWAY.md](RAILWAY.md) has the symptom table.

Signed in as an administrator (the first account created), `GET /api/admin/status`
returns the deployment's own assessment. An empty `warnings` array means
everything above is complete.
