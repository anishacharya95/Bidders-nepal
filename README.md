# Bidders Nepal

An automated Nepal public-procurement aggregation platform: a FastAPI/PostgreSQL backend
with a polite source collector, document discovery, duplicate linking, monitoring, an
authenticated admin dashboard, and a mobile-first Expo app.

**Live API:** https://bidders-nepal-api.onrender.com
**API docs:** https://bidders-nepal-api.onrender.com/docs
**Admin dashboard:** https://bidders-nepal-api.onrender.com/admin
**Mobile app source:** [`mobile/`](mobile/)

Bidders Nepal is an independent aggregator, not a government agency. Every record links
back to the original public notice; unverified values are `null`, never invented.

---

## What it does

- Discovers public tender notices from PPMO, ministries, departments, utilities,
  provincial portals and registered local governments.
- Collects EOI, RFP, RFQ, prequalification, amendments, deadline extensions,
  cancellations, bid-opening and award notices where the source publishes them.
- Extracts title, notice number, organisation, province/district/municipality,
  category, description, publication date, deadline, bid opening, budget, bid security,
  eligibility, contact details, source URL, verification state and timestamps.
- Discovers direct public attachments (PDF, DOC/DOCX, XLS/XLSX, ZIP and more), records
  format, size, type, reachability and parent tender, and links them from the app.
- Prevents duplicates by canonical URL, normalised notice number, source record id,
  organisation + date + title similarity, and same-host/title mirrors. Distinct notices
  are never deleted; additional sources are recorded as changes.
- Tracks amendments and deadline changes as changes on the canonical tender.
- Monitors source health, collection runs, failures, coverage of all 753 local
  governments, document probe results and scheduler state.
- Serves a public read-only API and a navy/white, mobile-first app.

## Repository layout

```
app/
  api/              public.py, admin.py (JSON), admin_ui.py (Jinja dashboard), auth.py
  collectors/       base (HTTP policy), extraction, adapters, registry, discovery, runner
  services/         duplicates, documents, query/facets, monitoring
  data/             local_governments.json (753 units + attribution)
  templates/        admin dashboard HTML
  static/admin.css  dashboard styling
  config.py         environment-driven settings
  database.py       engine + pooling
  database_schema.py idempotent column/table bootstrap
  models.py         SQLAlchemy models
  schemas.py        Pydantic request/response models
  scheduler.py      APScheduler priority/daily/discovery jobs
alembic/            versioned migrations (initial platform migration)
tests/              API, registry, extraction, duplicate, runner and auth tests
mobile/             Expo / React Native app (TypeScript)
```

## Public API

Base: `/api/v1`. Interactive schema at `/docs`.

| Endpoint | Purpose |
| --- | --- |
| `GET /tenders/all` | Full public feed (pending + verified, rejected excluded). `page_size` ≤ 500 |
| `GET /tenders` | Verified-only feed (`page_size` ≤ 100, default status `open`) |
| `GET /tenders/latest` | Newest records (`limit` ≤ 100) |
| `GET /tenders/closing-soon` | Open notices closing within `days` (1–90) |
| `GET /tenders/{id}` | Detail (404 for missing/rejected) |
| `GET /tenders/{id}/documents` | Attachment metadata |
| `GET /tenders/{id}/changes` | Amendments, deadline changes, duplicate links |
| `GET /tenders/{id}/sources` | Primary source + additional sources |
| `GET /search` | Not exposed separately; use `?q=` on `/tenders/all` |
| `GET /categories` | Category counts (respects filters) |
| `GET /provinces`, `/districts`, `/municipalities` | Location facets |
| `GET /organizations` | Organisation facet with `q` search |
| `GET /filters/options` | All filter menus in one call |
| `GET /sources` | Active, verified public sources |
| `GET /coverage` | Local-government coverage + source counts |
| `GET /stats` | Public aggregate counters |
| `GET /changes` | Recent tender changes |
| `POST/GET/DELETE /saved-searches` | Device-scoped saved filters (max 20/device) |

Filters on tender feeds: `q`, `category`, `province`, `district`, `municipality`,
`organization`, `status`, `verification_status`, `has_documents`, `published_from/to`,
`deadline_from/to`, `sort` (`newest|oldest|closing|deadline|updated`), `page`,
`page_size`. Responses use `{items, total, page, page_size}`.

Health: `GET /health` (DB + scheduler) and `GET /health/data` (non-secret counts).

## Collection

Synchronous `requests` fetcher with:

- HTTPS only, `.gov.np` or explicitly approved hosts (`nea.org.np`, `caanepal.gov.np`);
- `robots.txt` checks, per-host delay, bounded response bytes, retries/backoff;
- no login, CAPTCHA or restricted-portal bypass; no document downloads for probing
  (HEAD only, recorded as `unverified`/`available`/`restricted`/`missing`).

Default schedule (Render single instance):

- priority sources every **20 minutes**;
- full scan daily at **02:00 Asia/Kathmandu**;
- incremental local-government website discovery daily;
- per-run source limit, time budget and detail-fetch budget to protect free hosting.

Every run writes `collection_runs` and per-source `source_scans`, updates source health,
inserts new tenders as `pending`, links duplicates and closes expired notices.

### Source registry

National sources include PPMO purchase/bid notices, NEA, Department of Roads, DoLI,
DUDBC, DWSSM, DWRI, CAAN, MoFAGA, Koshi Province, and the official/third-party Bolpatra
portals. The two Bolpatra portals are registered as **requires_authorization** and are
disabled; they are never scraped. Unverified provincial portals are registered as
`unregistered` and tried later.

All **753 local governments** (6 metropolitan, 11 sub-metropolitan, 276 municipalities,
460 rural municipalities) are registered from a bundled dataset with province/district
and Nepali names. Registration is **not** coverage: a unit is only connected after an
HTTPS official site is verified by content and a tender page is found and successfully
scanned. The dashboard reports registered / website-verified / tender-page-verified /
scanned / inaccessible separately.

### Local verification run (26 Nov 2026)

Priority scan of 6 sources against live public sites:

| Source | Result | Notices |
| --- | --- | --- |
| PPMO purchase notices | OK | 125 |
| PPMO bid notices | OK | 109 |
| Nepal Electricity Authority | OK | 1 |
| Department of Roads | OK | 4 |
| Department of Local Infrastructure | OK | 30 |
| DUDBC | Failed | TLS certificate hostname mismatch |

Result: 155 new notices stored as pending, 114 duplicate candidates linked/skipped,
0 attachments verified (the sampled detail pages exposed no direct public file URLs).
A scan is not a claim that every notice or document is available.

## Admin

`/admin` is a server-rendered dashboard (cookie session, CSRF-protected forms) with:

- overview metrics, recent runs, failing sources, pending review;
- source list/add/edit/enable/disable, scan now, website discovery;
- collection runs and per-source scan history/errors;
- approve/reject review queue;
- duplicate notice groups, document status, 753-unit coverage, health/scheduler.

JSON admin API lives under `/api/v1/admin/*` with Bearer authentication
(`POST /api/v1/auth/login`); Swagger's Authorize button uses `/api/v1/auth/token`.
Admin endpoints are never exposed through public routes.

## Local setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET=change-me
export ADMIN_EMAIL=admin@example.com
export ADMIN_PASSWORD='a-long-password'
alembic upgrade head
uvicorn app.main:app --reload
```

Run tests (isolated SQLite, collector disabled, no outbound requests):

```bash
.venv/bin/python -m pytest -q
```

Run one real priority collection against public sources:

```bash
python - <<'PY'
from app.database import SessionLocal
from app.collectors.registry import sync_registry
from app.collectors.runner import run_collection
db = SessionLocal()
sync_registry(db)
print(run_collection(db, mode="priority", trigger="manual"))
PY
```

### Configuration

Core: `DATABASE_URL`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CORS_ORIGINS`,
`ADMIN_COOKIE_SECURE`.

Collector: `ENABLE_TENDER_COLLECTOR`, `TENDER_PRIORITY_INTERVAL_MINUTES` (or legacy
`TENDER_COLLECT_INTERVAL_MINUTES`), `TENDER_FULL_SCAN_CRON`, `TENDER_STARTUP_SCAN`,
`TENDER_TIMEZONE`, `TENDER_PRIORITY_SOURCE_LIMIT`, `TENDER_FULL_SOURCE_LIMIT`,
`TENDER_RUN_BUDGET_SECONDS`, `TENDER_MAX_PAGES_PER_SOURCE`, `TENDER_DETAIL_FETCH_LIMIT`,
`TENDER_HTTP_TIMEOUT_SECONDS`, `TENDER_HOST_DELAY_SECONDS`, `TENDER_PROBE_DOCUMENTS`,
`TENDER_LOCAL_DISCOVERY`, `TENDER_SOURCE_URLS`, `TENDER_USER_AGENT`.

## Deployment

`render.yaml` provisions the Postgres database and web service. The start command runs
`alembic upgrade head && uvicorn app.main:app ...`; startup also applies the idempotent
schema bootstrap, seeds the configured admin and syncs the source registry without
touching existing tender rows.

Render environment: set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in the dashboard (they are
`sync: false`). `JWT_SECRET` is generated by Render. Collector defaults are in
`render.yaml`; tune them there.

Migrations are additive: the initial revision creates missing platform tables/columns
and never drops production data.

## Mobile app

Expo + TypeScript app in [`mobile/`](mobile/) with a premium navy/white/green design.
Screens: home dashboard, all tenders, latest, closing soon, categories, province/district/
municipality/organisation/document filters, tender detail, bid documents, saved tenders,
notifications, and About/contact. It reads only public endpoints and never stores admin
credentials. See [`mobile/README.md`](mobile/README.md) for build commands.

```bash
cd mobile
npm install
npm run typecheck
npx expo start --web
```

## Limitations

- Some government sites block automated access, use invalid TLS certificates, or change
  layout; the dashboard records these instead of hiding them.
- Documents are only listed when the source exposes a direct public file URL; restricted
  portals are not bypassed.
- Not all 753 local governments publish procurement online, and coverage grows through
  verified discovery batches.
- Free Render hosting can cold-start slowly; the app retries and shows honest states.
