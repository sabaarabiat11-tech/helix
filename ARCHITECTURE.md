# Helix — Architecture

## Layers

```
frontend/          React SPA (Vite, Tailwind, Framer Motion)
backend/
  routers/         HTTP only — parse, authorize, delegate, serialize
  services/        all business logic; no FastAPI imports anywhere inside
  db/              schema, engine, portable query helpers
  core/            security primitives + request plumbing
  workers/         standalone CLI jobs (digest sender)
src/, start.py     the discovery pipeline — UNCHANGED, never imported by backend/
```

The dependency direction is strictly inward: routers → services → db. Nothing
in `services/` imports FastAPI, which is what lets the digest worker reuse the
exact same code paths as the API with no web server running.

## The pipeline boundary

The discovery pipeline was not modified in V3 and is not imported by the
application. The two meet in exactly two places, both in `backend/database.py`:

- `sync_from_csv()` mirrors `data/linkedin_master.csv` into the database after
  every run.
- `export_to_csv()` generates a CSV *from* the database on demand.

Nothing ever writes back to `linkedin_master.csv`.

## Multi-tenancy model

**Discovery data is global; personalization is per-user.**

The `people` table is one shared corpus. It has no `user_id` and never will —
one nightly pipeline run serves every account. What differs per user is the
layer on top:

| Shared            | Per user                                        |
| ----------------- | ----------------------------------------------- |
| `people`, `meta`  | `users`, `user_preferences`, `oauth_accounts`   |
|                   | `watchlist`, `notifications`                     |
|                   | `recommendation_history`, `email_log`            |
|                   | `refresh_tokens`, `email_tokens`                 |

Every per-user table cascades from `users.id`, so account deletion is a single
`DELETE` and the shared corpus is untouched.

## Scoring: two separable questions

`recommendation_service` answers *"how notable is this person?"* — a property
of the person alone, identical for everyone, and cacheable across the corpus.

`personalization_service` answers *"how relevant is this person to **you**?"* —
a pure function of one user's preferences applied on top of the base score,
capped at +25/−20 so a preference match promotes a good candidate rather than
elevating a weak one.

Both sit behind interfaces (`RecommendationEngine`, `InsightsEngine`
Protocols). Swapping either for an ML or LLM implementation is one class plus
one assignment; routers and the frontend never change.

Every adjustment appends a human-readable reason, so no ranking is ever
unexplained.

## Session design

Short-lived JWT access token + long-lived opaque refresh token.

- The **access token** lives in a JavaScript module variable, never
  `localStorage` — anything in `localStorage` is readable by injected script.
  It dies with the tab; `AuthContext` silently re-establishes it on load.
- The **refresh token** is a random secret in an httpOnly cookie, so page
  JavaScript cannot read it. Only its SHA-256 is stored server-side.
- Refresh tokens **rotate** on every use. Presenting an already-rotated token
  means two parties hold it — the session was stolen — so the whole token
  family for that user is revoked.

WebSocket handshakes can't carry an `Authorization` header, so `/api/run/stream`
accepts the same short-lived token as a query parameter.

## Database portability

SQLAlchemy Core over raw SQL, driven by `DATABASE_URL`. Two conventions keep
the SQL dialect-neutral and are followed everywhere:

1. Bind parameters are always **named** (`:user_id`), never `?`.
2. Date arithmetic happens in **Python**, never in SQL — no `strftime`,
   `julianday` or `NOW()`.

Timestamps are stored as ISO-8601 UTC strings, which sort lexicographically in
chronological order, so range queries work identically on both dialects.

One subtlety worth knowing: raw `text()` queries bypass SQLAlchemy's result
type coercion, so SQLite returns `0/1` where psycopg returns real booleans.
`db/engine.py` normalizes boolean columns on the way out, deriving the column
set from the schema itself.

Moving to PostgreSQL:

```bash
pip install "psycopg[binary]"
export DATABASE_URL="postgresql+psycopg://helix:pw@host:5432/helix"
```

## Upgrading a pre-V3 database

The old `watchlist` and `notifications` tables predate accounts. On first boot
they're renamed to `legacy_*_import` holding tables, and the first account
created inherits their contents (on a single-user install, that's the person
whose data it was). If nobody signs up, nothing is destroyed. Verified against
a real 514-row database with no data loss.

## Email

`EmailProvider` is a Protocol; `providers.py` implements console, SMTP, Resend,
SendGrid, Mailgun and SES behind it, selected by `EMAIL_PROVIDER`. Business
logic only calls `sender.send_*`. A misconfigured provider logs loudly and
falls back to console rather than taking down signup.

The default `console` provider writes rendered emails to `data/outbox/`, so
signup, verification, reset and digests are fully testable offline.

Digests run from `backend/workers/digest_worker.py` — a CLI, not an in-process
scheduler, so it scales independently of web traffic and works with cron,
systemd, Task Scheduler or a Kubernetes CronJob:

```bash
python backend/workers/digest_worker.py --frequency weekly --dry-run
```

## Designed-for, not built

These were shaped for but deliberately not implemented, to avoid speculative
tables nobody reads yet:

- **Organizations / teams** — per-user tables scope on `user_id`; adding an
  `organizations` table and widening that to an owner reference is additive.
- **Billing** — `users` is the natural subscription anchor; no schema conflict.
- **Admin dashboard** — `users.is_admin` exists and is enforced
  (`core/deps.admin_user`); the first account on a fresh install becomes admin.
- **LLM / semantic search** — both engines are already behind Protocols.
