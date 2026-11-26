# Bidders Nepal API

FastAPI backend starter for a Nepal tender and bidding-notice aggregator.

## Features
- Public search and filtering for **verified** tenders only
- Tender detail endpoint
- Admin JWT login; passwords hashed with Argon2
- Admin tender creation and editing
- Duplicate notice-number check
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
- GET /api/v1/tenders?q=&category=&province=&district=&status=open&page=1&page_size=20
- GET /api/v1/tenders/{id}
- POST /api/v1/admin/tenders (admin)
- PATCH /api/v1/admin/tenders/{id} (admin)
- GET /api/v1/admin/tenders?verification_status=pending (admin)
- POST /api/v1/admin/tenders/{id}/verify?decision=verified (admin)
- POST /api/v1/admin/tenders/import-csv (admin)
- GET /api/v1/admin/audit (admin)

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
(https://ppmo.gov.np/). Automated collectors are **not enabled in this starter**.
Each portal needs a separately reviewed adapter after confirming permitted access,
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
