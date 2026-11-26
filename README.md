# Bidders Nepal API

FastAPI backend starter for a Nepal tender and bidding-notice aggregator.

## Features
- Public search and filtering for **verified** tenders only
- Tender detail endpoint
- Admin JWT login; passwords hashed with Argon2
- Admin tender creation and editing
- Duplicate notice-number check
- Conservative PPMO public-link discovery; candidates remain pending
- Basic deadline and category extraction where the page text is unambiguous
- Automated tests for collector URL safety and parsing
- CSV bulk import (new records remain pending verification)
- Admin verification/rejection workflow and audit history
- SQLite for local testing; PostgreSQL configuration for deployment
- Interactive API docs at /docs

## Run locally (Python 3.11+)
```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

Set environment variables before running:
```bash
export JWT_SECRET='a-long-random-secret'
export ADMIN_EMAIL='admin@example.com'
export ADMIN_PASSWORD='a-strong-password'
uvicorn app.main:app --reload
```
PowerShell:
```powershell
$env:JWT_SECRET='a-long-random-secret'
$env:ADMIN_EMAIL='admin@example.com'
$env:ADMIN_PASSWORD='a-strong-password'
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs. The first startup creates the admin account from the environment variables.

## Main endpoints
- GET /health
- POST /api/v1/auth/login
- GET /api/v1/tenders?q=&category=&province=&district=&status=open&page=1&page_size=20 (verified only)
- GET /api/v1/tenders/all?page=1&page_size=100 (full public record feed: pending + verified; rejected excluded by default)
- GET /api/v1/tenders/{id}
- POST /api/v1/admin/tenders (admin)
- PATCH /api/v1/admin/tenders/{id} (admin)
- GET /api/v1/admin/tenders?verification_status=pending (admin)
- POST /api/v1/admin/tenders/{id}/verify?decision=verified (admin)
- POST /api/v1/admin/tenders/import-csv (admin)
- GET /api/v1/admin/audit (admin)

### Full tender JSON feed

Use `GET /api/v1/tenders/all` for a direct JSON feed of complete tender records, including pending and verified records. It returns up to 100 records by default (maximum 500 per page), with `total`, `page` and `page_size`. Optional filters include `q`, `category`, `province`, `district`, `status`, and `verification_status`. Rejected records are excluded by default; set `include_rejected=true` to include them, or `verification_status=rejected` to view only rejected records. This is a public feed, so pending records are clearly marked with `verification_status` and should not be treated as verified notices.

## Admin workflow
1. POST /api/v1/auth/login with your admin email and password.
2. Copy access_token, click Authorize in Swagger, enter Bearer followed by the token.
3. Create or import tender notices. They enter the pending queue.
4. Check the original source and documents, then verify or reject each notice.
5. Only verified records appear in public search.

CSV requires title and organization_name. Optional columns:
notice_number, category, province, district, description, published_date, deadline,
source_name, source_url, document_url. Use ISO 8601 dates and Nepal offset, e.g.
2026-12-15T17:00:00+05:45.

## Official-source integrations
Potential source portals include Nepal e-GP (https://bolpatra.gov.np/) and PPMO
(https://ppmo.gov.np/). The PPMO public-page discovery adapter is enabled by default and is intentionally limited.
Each additional portal needs a separately reviewed adapter after confirming permitted access,
terms, formats and request frequency. Do not bypass logins, CAPTCHAs or access controls.
The platform should preserve the original notice URL and show the source and verification status.

## Deploy on Render
1. Push this repository to GitHub (already done).
2. In Render choose New + -> Blueprint and connect this repository.
3. Review the services in render.yaml.
4. Set ADMIN_EMAIL and ADMIN_PASSWORD when prompted. Use unique strong credentials.
5. Deploy, then test https://YOUR-SERVICE.onrender.com/health and open /docs.

Free hosting can sleep when idle and free database limits/retention may change. Check Render's current plan terms before relying on it for production. For production use persistent database backups, migrations, monitoring and persistent object storage for tender PDFs. This MVP does not yet store uploaded PDF files; it stores source/document URLs and supports CSV import.

## Before public launch
- Replace wildcard CORS with your real website/app origins.
- Add Alembic database migrations, rate limiting, monitoring and backups.
- Add persistent object storage before enabling PDF uploads.
- Add reviewed source collectors, scheduling, retries and source-check timestamps.
- Add bidder accounts, roles, notifications and admin password reset.
- Clearly state Bidders Nepal is an independent aggregator, not a government agency.


## Automated PPMO public notice discovery

The first collector checks configured public PPMO pages every six hours by default. It extracts
notice-like links from public HTML and stores new candidates as **pending**. It attempts
basic category, notice-number and deadline extraction only when the visible page text is
unambiguous. It does not infer the procuring entity: the organization is explicitly marked
as requiring admin review. Nothing is published automatically. The adapter only requests
HTTPS pages on ppmo.gov.np and rejects redirects outside that host. It does not sign in,
submit forms, bypass CAPTCHAs, call private APIs, or download protected documents. Page
layouts can change, so admins must review each source link and complete missing details.

This first release does not scrape the e-GP bidder portal. Add separate adapters only
after confirming the source's published access rules, permission and a stable public
feed. It is a discovery aid, not a guarantee that every tender is captured.

### Collector settings

- ENABLE_TENDER_COLLECTOR=true (default; set false to pause)
- TENDER_COLLECT_INTERVAL_MINUTES=360 (default six hours; minimum 60)
- TENDER_SOURCE_URLS (optional comma-separated approved HTTPS pages on ppmo.gov.np)

### Run a collection immediately

Sign in at /docs, click Authorize, then call POST /api/v1/admin/collector/run.
Review candidates at GET /api/v1/admin/tenders?verification_status=pending.
Only admin-verified records appear in public tender listings.
