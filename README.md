# Helix — AI × Biology discovery platform

A multi-user web application over an autonomous discovery pipeline. The
pipeline finds professionals working in AI × Biology (ML engineers, AI
scientists, computational biologists, bioinformatics engineers, applied
scientists) at a configurable list of target companies, never duplicating.
Helix turns that into a product: accounts, personalized rankings, watchlists,
email digests.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the layers fit together.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # works as-is; nothing is required for local dev
docker compose up -d          # SearXNG, the pipeline's search backend
```

Two terminals:

```bash
cd backend && uvicorn main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 and create an account. The first account on a fresh
install becomes the administrator, and on an upgraded install it inherits any
watchlist and notifications from the pre-accounts version.

Emails default to the `console` provider, which writes fully rendered messages
to `data/outbox/` — open them in a browser. Verification, password reset and
digests are all testable with no third-party account.

## Scheduled digests

```bash
python backend/workers/digest_worker.py --frequency weekly --dry-run
```

Run it from cron, systemd, Windows Task Scheduler or a Kubernetes CronJob.
Suggested: daily at 08:00, weekly on Monday at 08:00.

## Deploying

Everything deployment-specific is an environment variable — see
[.env.example](.env.example). At minimum, production needs `ENVIRONMENT=production`,
a generated `SECRET_KEY`, and `PUBLIC_URL`/`API_URL` set to your real domain
(email links and OAuth redirects are built from them).

```bash
docker build -t helix .
docker run -p 8000:8000 --env-file .env -v ./data:/app/data helix
```

The image builds the SPA and serves it from the same origin as the API, so a
deployment is one container with no CORS configuration. SQLite is the default;
point `DATABASE_URL` at PostgreSQL to switch, with no code changes.

---

## The discovery pipeline

The pipeline below is unchanged by the web application and can still be run
standalone with `python start.py`.

## Important: how "LinkedIn" discovery actually works

This agent does **not** log into LinkedIn, scrape linkedin.com pages, or
automate a browser against LinkedIn. That would violate LinkedIn's Terms of
Service and typically requires bypassing bot-detection — not something this
project does.

Instead, LinkedIn profile URLs are discovered through a **local,
self-hosted SearXNG instance running in Docker** (`site:linkedin.com/in
"Company" "Role"` queries) — SearXNG is a free, open-source meta-search
engine that federates results from Bing/DuckDuckGo/Wikipedia/etc. Querying
our own local instance's JSON API is not touching linkedin.com directly.
Every LinkedIn URL that ends up in `linkedin_master.csv` came from a real
search result; the agent never guesses or constructs a URL from a name.

**This project previously tried public SearXNG instances and abandoned that
approach.** Public instances proved unreliable in practice: testing from one
network, 63 of 64 public instances tried were rate-limited, blocked, or gave
broken results. Running SearXNG ourselves in Docker fixes this completely —
it's still not a paid service (SearXNG is free/open-source, Docker Desktop is
free for local use), but now there's no other users' traffic sharing our
rate limit, no dependency on volunteer infrastructure staying up, and no
blocking based on IP reputation.

**Verified working (2026-08-06)**: the local instance was built, started,
and used to run a real query — it returned genuine LinkedIn profiles (e.g.
a real "Senior Machine Learning Engineer at Isomorphic Labs" profile URL)
via its DuckDuckGo engine. Full details in "Verification" below.

## Search domains and how each is implemented

| Domain | Implementation | Notes |
|---|---|---|
| LinkedIn | Local SearXNG (Docker), `site:linkedin.com/in` queries against `http://localhost:8080` | primary source |
| Google Search / general web search | same local SearXNG meta-search (aggregates Bing/DuckDuckGo/Wikipedia/etc. — Google itself is not one of the enabled engines by default) | there is no direct Google API integration in this project |
| GitHub | official GitHub REST API | only kept if the user's public bio/blog field contains a real LinkedIn URL |
| Company team pages | `requests` + `BeautifulSoup`, then resolved to a LinkedIn URL via the local SearXNG instance | needs a CSS selector per company for reliable extraction (see `config.yaml`) |
| Google Scholar | `scholarly` package (unofficial, best-effort) | **disabled by default** — no official API; enable at your own risk in `config.yaml`. LinkedIn URLs for authors found this way are still resolved via SearXNG, never guessed. |
| Company blogs | not implemented as a separate source (blogs rarely list individual engineers with LinkedIn URLs) — covered indirectly by SearXNG queries | — |

## Project structure

```
linkdin/
├── start.py                    # ONE-COMMAND ENTRY POINT: docker up -> wait healthy -> run.py
├── run.py                      # pipeline entry point only (own shorter readiness check too)
├── docker-compose.yml          # local SearXNG container definition
├── searxng/
│   └── settings.yml            # SearXNG config: JSON format enabled, limiter disabled
├── config.yaml                 # companies, roles, source toggles, paths, SearXNG base_url
├── requirements.txt
├── .env.example                 # copy to .env — only GITHUB_TOKEN (optional) needed
├── README.md
├── src/
│   ├── config.py               # loads config.yaml + .env
│   ├── models.py                # Person model, URL normalization
│   ├── dedupe_store.py          # reads/appends linkedin_master.csv, dedup logic
│   ├── pipeline.py              # orchestrates sources -> filter -> rank -> append
│   ├── report.py                # writes weekly_report_<date>.md
│   ├── logging_setup.py         # per-run log file + console
│   └── sources/
│       ├── base.py               # DiscoverySource interface (fail-soft wrapper)
│       ├── searxng_search_source.py  # queries local Docker SearXNG only
│       ├── github_source.py
│       ├── company_pages_source.py
│       └── scholar_source.py     # optional, off by default
├── scripts/
│   ├── wait_for_searxng.py     # health-check polling, used by start.py and run.py
│   └── seed_master_from_csv.py  # one-time bootstrap from an existing CSV
└── data/                       # created automatically on first run
    ├── linkedin_master.csv      # the growing, deduplicated master list
    ├── reports/
    │   └── weekly_report_YYYY-MM-DD.md
    └── logs/
        └── run_YYYY-MM-DD_HH-MM-SS.log
```

## Setup

### Prerequisites

- **Docker Desktop** (Windows/Mac/Linux) — https://www.docker.com/products/docker-desktop/
  Must be installed and running before you start SearXNG.
- **Python 3.10+**

### Steps

1. **Install Python dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   `scholarly` is only needed if you enable `sources.google_scholar` in
   `config.yaml`; it's fine if that install fails/is skipped otherwise.

2. **Copy `.env.example` to `.env`.** No API key is required for search —
   SearXNG is our own local Docker container. The only optional value is
   `GITHUB_TOKEN` (raises the GitHub source's rate limit).

3. **Start the local SearXNG instance and run the pipeline — one command:**

   ```bash
   python start.py
   ```

   This does exactly three things, in order: (1) `docker compose up -d`,
   (2) waits until `http://localhost:8080` is actually healthy *and* its
   JSON API responds correctly (not just "container running"), (3) runs
   `python run.py`. See "Verification" below for exactly what this looks
   like the first time.

   To manage the container directly instead:
   ```bash
   docker compose up -d       # start
   docker compose ps          # check health
   docker compose logs -f     # follow logs
   docker compose down        # stop
   ```

4. **Review `config.yaml`** — target companies/roles, weekly target range,
   which sources are enabled, and (for `company_pages`) add real CSS
   selectors for each team page as you find ones that work reliably.

Every run creates/appends to `data/linkedin_master.csv`, writes
`data/reports/weekly_report_<today>.md`, and logs to `data/logs/`.

## Bootstrapping from an existing CSV

If you already have a curated list of people (e.g. from earlier manual
research) and want the agent to treat them as "already known" instead of
re-discovering them, seed the master CSV once:

```bash
python scripts/seed_master_from_csv.py path/to/existing_list.csv
```

The source CSV needs `Name, Title, Company, LinkedIn URL, Location, Reason`
columns (case-insensitive). It's safe to re-run — it uses the exact same
dedup logic as the live pipeline, so it never creates duplicates even if run
against overlapping files.

## Guarantees / behavior

- **Never duplicates**: every candidate is checked against the existing
  master CSV (by normalized LinkedIn URL, and by name+company) before being
  added, and against everyone else found *in the same run*.
- **Append-only**: existing rows in `linkedin_master.csv` are never modified
  or removed by a run.
- **No fabrication**: every source either returns a URL it actually observed
  (search result, API response, scraped page + confirmed via search) or
  returns nothing for that candidate. There is no code path that constructs
  a `linkedin.com/in/...` URL from a guessed slug.
- **Fail-soft**: if one source errors (network issue, bad selector, expired
  token), the run logs it and continues with the remaining sources rather
  than aborting.
- **SearXNG retries**: each query retries against the local instance (with
  backoff) before being skipped — covers transient issues like the container
  still warming up, not a fleet of fallback servers (there's only one
  instance now, by design).
- **Startup ordering guaranteed**: `start.py` waits for a real health check
  (container health + a working JSON response, not just "process started")
  before the pipeline runs; `run.py` repeats a shorter version of this check
  on its own as a safety net if invoked directly.
- **Full logging**: every run writes a timestamped log file under
  `data/logs/` recording what each source found, what was filtered out, and
  why the run finished with however many new people it finished with.

## Weekly target (20–30 new people)

`config.yaml` → `run.min_new_per_run` / `run.max_new_per_run`. If a run finds
fewer than the minimum, it still completes normally (no error) but the
report and log flag it clearly, along with likely causes (the Docker
container wasn't running, target list already well-covered, optional
sources disabled). If more than the maximum are found, they're ranked (target-company
match, target-role match, having a location/reason) and only the top N are
kept — the rest are simply not added this run and will very likely turn up
again (and get added) next week if you widen the source set.

## Scheduling weekly runs with Windows Task Scheduler

**Point the scheduled task at `start.py`, not `run.py`** — `start.py` is what
starts Docker and waits for SearXNG to be healthy; `run.py` alone assumes
that already happened. Docker Desktop should also be set to launch at login
(Docker Desktop → Settings → General → "Start Docker Desktop when you log
in") so it's available before the scheduled task fires, especially on an
unattended/overnight run.

### Option A — GUI

1. Open **Task Scheduler** (search for it in the Start menu).
2. **Action → Create Task…** (not "Basic Task", so you get the full options).
3. **General** tab: name it e.g. `AI-Bio LinkedIn Discovery Agent`. Under
   "Security options", choose **"Run whether user is logged on or not"** if
   you want it to run even when you're not signed in.
4. **Triggers** tab → **New…** → Begin the task **On a schedule** → **Weekly**,
   pick a day/time (e.g. every Monday at 08:00). Under "Advanced settings",
   consider a short **Delay task for** (e.g. 2 minutes) if the task is also
   set to trigger "At log on" so Docker Desktop has time to finish starting.
5. **Actions** tab → **New…** → Action: **Start a program**.
   - **Program/script**: full path to your Python executable, e.g.
     `C:\Users\sabaa arabiat\AppData\Local\Python\pythoncore-3.14-64\python.exe`
     (run `where python` in a terminal to find yours).
   - **Add arguments**: `start.py`
   - **Start in**: `C:\Users\sabaa arabiat\OneDrive\Desktop\linkdin`
     (this must be the project folder so `docker-compose.yml`/`config.yaml`/`.env` are found).
6. **Conditions**/**Settings** tabs: uncheck "Start the task only if the
   computer is on AC power" if this runs on a laptop, and check "Run task as
   soon as possible after a scheduled start is missed" so a missed week
   still catches up.
7. Click **OK**, enter your Windows password if prompted.

### Option B — command line (`schtasks`)

Run this once from an elevated PowerShell or Command Prompt (adjust the
Python path and project path for your machine):

```powershell
schtasks /create /tn "AI-Bio LinkedIn Discovery Agent" /tr "'C:\Users\sabaa arabiat\AppData\Local\Python\pythoncore-3.14-64\python.exe' 'C:\Users\sabaa arabiat\OneDrive\Desktop\linkdin\start.py'" /sc weekly /d MON /st 08:00 /sd 01/01/2026 /it
```

- `/sc weekly /d MON /st 08:00` — every Monday at 8:00 AM.
- `/it` — allow the task to run interactively (skip if using a service account).
- Verify it registered: `schtasks /query /tn "AI-Bio LinkedIn Discovery Agent"`
- Run it immediately to test: `schtasks /run /tn "AI-Bio LinkedIn Discovery Agent"`
- Remove it later if needed: `schtasks /delete /tn "AI-Bio LinkedIn Discovery Agent" /f`

Either way, check `data/logs/` and `data/reports/` after the first scheduled
run to confirm it executed correctly — Task Scheduler will report "the
operation completed successfully" even if the script itself errored out
internally, so the log file is the real source of truth.

## Verification

To manually confirm everything works, in order:

```bash
docker compose up -d
docker compose ps
```
Expect `STATUS` to eventually show `Up ... (healthy)` (takes ~20-30s the
first time).

```bash
curl http://localhost:8080/healthz
```
Expect: `OK`

```bash
curl "http://localhost:8080/search?q=test&format=json"
```
Expect: a JSON body with a non-empty `"results"` array.

```bash
python scripts/wait_for_searxng.py
```
Expect: `SearXNG is healthy and the JSON API works (http://localhost:8080), after 1 attempt(s).`

```bash
python start.py
```
Expect: three numbered steps printing in order, ending with the same
`=== Run complete: N new people added ===` line `run.py` always prints, then
check `data/linkedin_master.csv` for new rows with `LinkedIn URL` values
under `linkedin.com/in/...`, and `data/logs/run_*.log` for lines like
`Source 'searxng_search' produced N candidates.`

## Troubleshooting

**`docker compose up -d` fails / "Cannot connect to the Docker daemon"**
Docker Desktop isn't running. Start it (Windows: Start menu → Docker
Desktop, wait for the whale icon in the system tray to stop animating), then
retry.

**`docker compose ps` shows `(unhealthy)` or stuck on `(health: starting)`**
Check `docker compose logs searxng` for the actual error. Common cause: the
container needs a few seconds longer than the healthcheck's `start_period`
on a slow/first-run machine — it usually self-resolves; if not, `docker
compose restart searxng`.

**Port 8080 already in use**
Something else on your machine is using port 8080. Either stop that service,
or change the port mapping in `docker-compose.yml` (edit `"127.0.0.1:8080:8080"`
to e.g. `"127.0.0.1:8090:8080"`) and set `SEARXNG_BASE_URL=http://localhost:8090`
in `.env` to match.

**`curl http://localhost:8080/search?...` returns HTML instead of JSON**
`searxng/settings.yml` doesn't have `json` under `search.formats`, or the
container is using a stale cached settings file. Confirm the `search:
formats:` block includes `json`, then `docker compose down && docker compose
up -d` to force a clean restart (the settings.yml is bind-mounted, so this
is the same as editing it directly and restarting).

**`python run.py` logs "SearXNG at ... is not reachable/healthy" and results are low**
The container isn't running or isn't healthy yet. Run `python start.py`
instead of `run.py` directly — it handles this for you. If you're already
using `start.py` and still see this, check `docker compose ps` and `docker
compose logs searxng`.

**Individual search engines inside results show up as "unresponsive" (e.g. `["google cse", "timeout"]`)**
Normal — SearXNG queries several upstream engines per search and reports
which ones didn't respond in time; results still come back from whichever
engines did respond (in testing, Wikipedia and DuckDuckGo were reliable,
some others were rate-limited from the test network). This doesn't need
fixing unless *zero* engines ever respond.

**Results come back but zero LinkedIn profiles are extracted**
Check the `Reason`/log for `_parse_item` behavior — the title-parsing regex
expects `"Name - Title - Company | LinkedIn"` or `"Name - Title | LinkedIn"`.
Some real LinkedIn result titles don't match this shape (e.g. a bare `"Name
| LinkedIn"` with no title/company) and are intentionally skipped rather
than guessed — this is working as designed, not a bug.

## Extending

- Add companies/roles: edit the lists in `config.yaml`, no code changes needed.
- Add a new source: subclass `DiscoverySource` in `src/sources/`, implement
  `is_available()` and `discover()`, register it in `build_sources()` in
  `src/pipeline.py`.
- Improve `company_pages` accuracy: add a `selector` (CSS selector string) for
  a company in `config.yaml` once you've inspected its team page's HTML.
