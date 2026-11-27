"""Server-rendered admin dashboard (Jinja2, cookie session, CSRF double submit)."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import authenticate_user
from app.collectors.discovery import discover_local_governments
from app.collectors.registry import _slug, local_directory_counts, sync_registry
from app.collectors.runner import launch_background_run, retry_failed_sources
from app.config import settings
from app.database import get_db
from app.models import (
    AuditLog,
    CollectionRun,
    CollectionRun as RunModel,
    Source,
    SourceScan,
    Tender,
    TenderChange,
    TenderDocument,
    User,
)
from app.scheduler import scheduler_snapshot
from app.security import (
    clear_admin_cookie,
    get_admin_from_cookie,
    set_admin_cookie,
)
from app.services.duplicates import search_duplicate_groups
from app.services.monitoring import coverage_stats, platform_stats
from app.services.spreadsheet_import import import_tender_rows, parse_spreadsheet

router = APIRouter(prefix="/admin", tags=["admin-dashboard"], include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")
CSRF_COOKIE = "bn_csrf"
LG_TYPES = ["metropolitan_city", "sub_metropolitan_city", "municipality", "rural_municipality"]


def _dt(value, fmt: str = "%d %b %Y, %H:%M") -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    return value.strftime(fmt)


templates.env.filters["dt"] = _dt
templates.env.globals["now"] = datetime.utcnow


def _csrf(request: Request) -> str:
    return request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)


def _check_csrf(request: Request, token: str) -> None:
    expected = request.cookies.get(CSRF_COOKIE)
    if not expected or not token or not secrets.compare_digest(expected, token):
        raise HTTPException(status_code=400, detail="Invalid form token. Reload the page and retry.")


def _render(request: Request, template: str, status_code: int = 200, **context) -> HTMLResponse:
    token = _csrf(request)
    payload = {
        "request": request,
        "csrf_token": token,
        "settings": settings,
        "message": request.query_params.get("message"),
        "error": request.query_params.get("error"),
        **context,
    }
    response = templates.TemplateResponse(request, template, payload, status_code=status_code)
    if request.cookies.get(CSRF_COOKIE) != token:
        response.set_cookie(
            CSRF_COOKIE, token, httponly=True, samesite="lax", secure=settings.admin_cookie_secure
        )
    return response


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    try:
        return get_admin_from_cookie(request, db)
    except HTTPException:
        target = "/admin/login"
        if request.url.path not in {"/admin", "/admin/"}:
            target = f"/admin/login?next={request.url.path}"
        raise HTTPException(status_code=303, headers={"Location": target})


def _redirect(message: str | None = None, path: str = "/admin", error: str | None = None):
    if error:
        return RedirectResponse(f"{path}?error={error}", status_code=303)
    if message:
        return RedirectResponse(f"{path}?message={message}", status_code=303)
    return RedirectResponse(path, status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return _render(request, "login.html", title="Admin sign in")


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    _check_csrf(request, csrf_token)
    try:
        user = authenticate_user(email, password, db)
    except HTTPException:
        return _render(request, "login.html", status_code=401, title="Admin sign in", error="Incorrect email or password")
    response = RedirectResponse("/admin", status_code=303)
    set_admin_cookie(response, user)
    return response


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    _check_csrf(request, csrf_token)
    response = RedirectResponse("/admin/login?message=Signed+out", status_code=303)
    clear_admin_cookie(response)
    return response


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    stats = platform_stats(db)
    runs = db.query(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(6).all()
    failing = (
        db.query(Source)
        .filter(Source.consecutive_failures > 0)
        .order_by(Source.consecutive_failures.desc())
        .limit(8)
        .all()
    )
    recent_tenders = (
        db.query(Tender)
        .filter(Tender.verification_status == "pending")
        .order_by(Tender.created_at.desc())
        .limit(6)
        .all()
    )
    return _render(
        request,
        "dashboard.html",
        title="Overview",
        admin=admin,
        stats=stats,
        runs=runs,
        failing=failing,
        recent_tenders=recent_tenders,
        scheduler=scheduler_snapshot(),
    )



@router.get("/imports", response_class=HTMLResponse)
def imports_page(
    request: Request,
    admin: User = Depends(require_admin),
):
    return _render(request, "imports.html", title="Excel imports", admin=admin)


@router.post("/imports/rollback-20261127")
def rollback_nov27_import(
    request: Request,
    csrf_token: str = Form(...),
    confirm: str = Form(""),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    if confirm != "REMOVE_2014_IMPORTED_TENDERS":
        return _redirect(error="Please confirm the exact import rollback", path="/admin/imports")
    # One-time rollback scope: only new Excel/CSV records created by the Nov 27 upload.
    start = datetime(2026, 11, 27, 7, 50, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 27, 7, 55, 0, tzinfo=timezone.utc)
    query = db.query(Tender).filter(
        Tender.created_by == admin.id,
        Tender.source_name == "Excel/CSV import",
        Tender.created_at >= start,
        Tender.created_at < end,
    )
    count = query.count()
    if count != 2014:
        return _redirect(
            error=f"Rollback stopped safely: expected 2,014 matching new imports but found {count}. No records were deleted.",
            path="/admin/imports",
        )
    query.delete(synchronize_session=False)
    db.add(AuditLog(
        actor_user_id=admin.id,
        action="spreadsheet_import_rollback",
        details=f"Deleted {count} newly-created Excel/CSV tenders from Nov 27 import window; existing tender rows retained.",
    ))
    db.commit()
    return _redirect(
        f"Removed {count} newly imported tenders. Existing tender records were retained.",
        "/admin/imports",
    )


@router.post("/imports")
async def import_spreadsheet_ui(
    request: Request,
    files: list[UploadFile] = File(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    if not files:
        return _redirect(error="Choose at least one .xlsx or .csv file", path="/admin/imports")
    if len(files) > 200:
        return _redirect(error="You can upload up to 200 files at once", path="/admin/imports")

    total_bytes = 0
    totals = {"added": 0, "updated": 0, "skipped": 0}
    failures = []
    successful_files = 0
    for upload in files:
        filename = (upload.filename or "").strip()
        if not filename.lower().endswith((".xlsx", ".csv")):
            failures.append(f"{filename or 'Unnamed file'}: unsupported format")
            continue
        raw = await upload.read()
        total_bytes += len(raw)
        if len(raw) > 10 * 1024 * 1024:
            failures.append(f"{filename}: over 10 MB")
            continue
        if total_bytes > 50 * 1024 * 1024:
            failures.append("Combined upload exceeds 50 MB; remaining files were not processed")
            break
        try:
            rows = parse_spreadsheet(raw, filename)
            if not rows:
                failures.append(f"{filename}: no tender rows found")
                continue
            result = import_tender_rows(db, admin, rows)
            for key in totals:
                totals[key] += result.get(key, 0)
            successful_files += 1
        except Exception as exc:
            db.rollback()
            failures.append(f"{filename}: {str(exc)[:120]}")

    if successful_files == 0:
        detail = "; ".join(failures[:3]) or "No valid spreadsheet files were processed"
        return _redirect(error=detail[:250], path="/admin/imports")
    summary = (
        f"Bulk import finished ({successful_files}/{len(files)} files): "
        f"{totals['added']} added, {totals['updated']} updated, {totals['skipped']} skipped"
    )
    if failures:
        summary += f"; {len(failures)} file(s) had errors"
    return _redirect(summary, "/admin/imports")

@router.get("/sources", response_class=HTMLResponse)
def sources_page(
    request: Request,
    q: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
    failing: bool = False,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(Source)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            Source.name.ilike(term) | Source.district.ilike(term) | Source.organization_name.ilike(term)
        )
    if source_type:
        query = query.filter(Source.source_type == source_type)
    if status:
        query = query.filter(Source.discovery_status == status)
    if failing:
        query = query.filter(Source.consecutive_failures > 0)
    total = query.count()
    rows = (
        query.order_by(Source.priority.asc(), Source.name.asc())
        .offset((page - 1) * 50)
        .limit(50)
        .all()
    )
    return _render(
        request,
        "sources.html",
        title="Sources",
        admin=admin,
        rows=rows,
        total=total,
        page=page,
        pages=max(1, (total + 49) // 50),
        q=q or "",
        source_type=source_type or "",
        status=status or "",
        failing=failing,
        types=sorted(LG_TYPES + ["central_agency", "department", "ministry", "agency", "utility", "provincial", "egp_portal", "third_party", "configured"]),
    )


def _source_form(request: Request, admin: User, source: Source | None, error: str | None = None):
    return _render(
        request,
        "source_form.html",
        title="Edit source" if source else "Add source",
        admin=admin,
        source=source,
        error=error,
    )


@router.get("/sources/new", response_class=HTMLResponse)
def new_source(request: Request, admin: User = Depends(require_admin)):
    return _source_form(request, admin, None)


@router.post("/sources/new")
def create_source_form(
    request: Request,
    name: str = Form(...),
    organization_name: str = Form(""),
    official_website: str = Form(""),
    tender_page_url: str = Form(""),
    source_type: str = Form("agency"),
    province: str = Form(""),
    district: str = Form(""),
    collector_key: str = Form("generic_html"),
    priority: int = Form(3),
    active: str | None = Form(None),
    requires_authorization: str | None = Form(None),
    notes: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    if not name.strip():
        return _source_form(request, admin, None, "Name is required")
    base = _slug(name)
    slug = base
    counter = 2
    while db.query(Source).filter(Source.slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    row = Source(
        slug=slug,
        name=name.strip(),
        organization_name=organization_name.strip() or name.strip(),
        source_type=source_type,
        level="local" if source_type in LG_TYPES else "central",
        province=province.strip() or None,
        district=district.strip() or None,
        official_website=official_website.strip() or None,
        tender_page_url=tender_page_url.strip() or None,
        collector_key=collector_key,
        discovery_status="discovered" if tender_page_url.strip() else "unregistered",
        priority=priority,
        active=bool(active),
        requires_authorization=bool(requires_authorization),
        notes=notes.strip() or None,
    )
    db.add(row)
    db.add(AuditLog(actor_user_id=admin.id, action="source_create_ui", details=row.name))
    db.commit()
    return _redirect(f"Source {row.name} created", "/admin/sources")


@router.get("/sources/{source_id}/edit", response_class=HTMLResponse)
def edit_source(
    source_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_form(request, admin, source)


@router.post("/sources/{source_id}/edit")
def save_source(
    source_id: int,
    request: Request,
    name: str = Form(...),
    organization_name: str = Form(""),
    official_website: str = Form(""),
    tender_page_url: str = Form(""),
    source_type: str = Form("agency"),
    province: str = Form(""),
    district: str = Form(""),
    collector_key: str = Form("generic_html"),
    priority: int = Form(3),
    active: str | None = Form(None),
    requires_authorization: str | None = Form(None),
    notes: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    row = db.get(Source, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    row.name = name.strip()[:300]
    row.organization_name = organization_name.strip()[:300] or row.name
    row.official_website = official_website.strip() or None
    row.tender_page_url = tender_page_url.strip() or None
    row.source_type = source_type
    row.level = "local" if source_type in LG_TYPES else row.level
    row.province = province.strip() or None
    row.district = district.strip() or None
    row.collector_key = collector_key
    row.priority = priority
    row.active = bool(active)
    row.requires_authorization = bool(requires_authorization)
    row.notes = notes.strip() or None
    if row.tender_page_url and row.discovery_status in {"unregistered", "inaccessible"}:
        row.discovery_status = "discovered"
    row.consecutive_failures = 0
    row.last_error = None
    db.add(AuditLog(actor_user_id=admin.id, action="source_update_ui", entity_id=row.id))
    db.commit()
    return _redirect(f"Saved {row.name}", "/admin/sources")


@router.post("/sources/{source_id}/toggle")
def toggle_source(
    source_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    row = db.get(Source, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    row.active = not row.active
    db.add(AuditLog(actor_user_id=admin.id, action="source_toggle_ui", entity_id=row.id, details=str(row.active)))
    db.commit()
    return _redirect(f"{row.name} {'enabled' if row.active else 'disabled'}", "/admin/sources")


@router.post("/sources/{source_id}/scan")
def scan_source_ui(
    source_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    row = db.get(Source, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    if not row.tender_page_url:
        return _redirect(error="This source has no verified tender page URL yet", path="/admin/sources")
    launch_background_run(mode="source", trigger="dashboard", source_ids=[source_id], limit=1)
    return _redirect(f"Scan queued for {row.name}", "/admin/sources")


@router.post("/sources/{source_id}/discover")
def discover_source_ui(
    source_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    from app.collectors.base import HttpFetcher
    from app.collectors.discovery import discover_website

    row = db.get(Source, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    found = discover_website(row, HttpFetcher())
    if found.get("website"):
        row.official_website = found["website"]
        row.tender_page_url = found.get("tender_page_url")
        row.discovery_status = "discovered" if found.get("tender_page_url") else "website_found"
        db.add(AuditLog(actor_user_id=admin.id, action="source_discover_ui", entity_id=row.id, details=row.official_website))
        db.commit()
        return _redirect(f"Verified website for {row.name}", "/admin/sources")
    row.last_error = "No verified HTTPS government website found"
    db.commit()
    return _redirect(error=f"No verified website found for {row.name}", path="/admin/sources")


@router.post("/run")
def manual_run(
    request: Request,
    mode: str = Form("priority"),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    if mode == "retry":
        result = retry_failed_sources(db, limit=10)
        message = f"Retry finished: {result.get('sources_checked', 0)} sources checked"
    else:
        if mode not in {"priority", "full", "local"}:
            mode = "priority"
        sync_registry(db)
        launch_background_run(mode=mode, trigger="dashboard")
        message = f"{mode.title()} collection started in the background"
    db.add(AuditLog(actor_user_id=admin.id, action="run_ui", details=mode))
    db.commit()
    return _redirect(message, "/admin/runs")


@router.post("/retry-failed")
def retry_ui(
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    result = retry_failed_sources(db, limit=10)
    return _redirect(f"Retried failing sources: {result.get('sources_checked', 0)} checked", "/admin/sources")


@router.post("/discovery")
def discovery_ui(
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    result = discover_local_governments(db)
    return _redirect(
        f"Discovery checked {result.get('checked', 0)} local governments, found {result.get('discovered', 0)}",
        "/admin/coverage",
    )


@router.get("/runs", response_class=HTMLResponse)
def runs_page(
    request: Request,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    total = db.query(CollectionRun).count()
    runs = (
        db.query(CollectionRun)
        .order_by(CollectionRun.started_at.desc())
        .offset((page - 1) * 25)
        .limit(25)
        .all()
    )
    return _render(
        request,
        "runs.html",
        title="Collection runs",
        admin=admin,
        runs=runs,
        total=total,
        page=page,
        pages=max(1, (total + 24) // 25),
    )


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    run = db.get(CollectionRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _render(request, "run_detail.html", title=f"Run #{run.id}", admin=admin, run=run)


@router.get("/review", response_class=HTMLResponse)
def review_page(
    request: Request,
    page: int = Query(1, ge=1),
    status: str = "pending",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(Tender).filter(Tender.verification_status == status)
    total = query.count()
    rows = (
        query.order_by(Tender.created_at.desc()).offset((page - 1) * 25).limit(25).all()
    )
    return _render(
        request,
        "review.html",
        title="Review queue",
        admin=admin,
        rows=rows,
        total=total,
        page=page,
        pages=max(1, (total + 24) // 25),
        status=status,
    )


@router.post("/tenders/approve-all")
def approve_all_pending_ui(
    request: Request,
    csrf_token: str = Form(...),
    confirm: str = Form(""),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    if confirm != "APPROVE_ALL_PENDING":
        return _redirect(error="Bulk approval was not confirmed", path="/admin/review")
    pending = db.query(Tender).filter(Tender.verification_status == "pending")
    count = pending.count()
    if count == 0:
        return _redirect("There are no pending tenders to approve", "/admin/review")
    pending.update(
        {Tender.verification_status: "verified"},
        synchronize_session=False,
    )
    db.add(AuditLog(
        actor_user_id=admin.id,
        action="bulk_verify_ui",
        details=f"Approved all {count} tenders that were pending at the time of this action.",
    ))
    db.commit()
    return _redirect(f"Approved {count} pending tenders", "/admin/review")


@router.post("/tenders/{tender_id}/verify")
def verify_ui(
    tender_id: int,
    request: Request,
    decision: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _check_csrf(request, csrf_token)
    if decision not in {"verified", "rejected"}:
        raise HTTPException(status_code=400, detail="Invalid decision")
    tender = db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    tender.verification_status = decision
    db.add(AuditLog(actor_user_id=admin.id, action=f"{decision}_ui", entity_id=tender.id))
    db.commit()
    return _redirect(f"Tender #{tender.id} {decision}", "/admin/review")


@router.get("/duplicates", response_class=HTMLResponse)
def duplicates_page(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    groups = search_duplicate_groups(db, limit=100)
    return _render(request, "duplicates.html", title="Duplicate notices", admin=admin, groups=groups)


@router.get("/documents", response_class=HTMLResponse)
def documents_page(
    request: Request,
    status: str | None = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(TenderDocument)
    if status:
        query = query.filter(TenderDocument.download_status == status)
    total = query.count()
    rows = query.order_by(TenderDocument.id.desc()).offset((page - 1) * 50).limit(50).all()
    counts = dict(
        db.query(TenderDocument.download_status, func.count(TenderDocument.id))
        .group_by(TenderDocument.download_status)
        .all()
    )
    return _render(
        request,
        "documents.html",
        title="Bid documents",
        admin=admin,
        rows=rows,
        counts=counts,
        total=total,
        page=page,
        pages=max(1, (total + 49) // 50),
        status=status or "",
    )


@router.get("/coverage", response_class=HTMLResponse)
def coverage_page(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return _render(
        request,
        "coverage.html",
        title="Local government coverage",
        admin=admin,
        coverage=coverage_stats(db),
        directory=local_directory_counts(),
    )


@router.get("/health", response_class=HTMLResponse)
def health_page(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    db_ok = True
    db_error = None
    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - diagnostic only
        db_ok = False
        db_error = str(exc)
    return _render(
        request,
        "health.html",
        title="System health",
        admin=admin,
        db_ok=db_ok,
        db_error=db_error,
        dialect=db.bind.dialect.name,
        stats=platform_stats(db),
        scheduler=scheduler_snapshot(),
        runs=db.query(CollectionRun).count(),
        failed_scans=db.query(SourceScan).filter(SourceScan.status == "error").count(),
        changes=db.query(TenderChange).count(),
    )
