"""Authenticated admin API. Every route requires an active admin account."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.collectors.discovery import discover_local_governments
from app.collectors.registry import _slug, sync_registry
from app.collectors.runner import (
    launch_background_run,
    retry_failed_sources,
    run_collection,
    select_sources,
)
from app.database import get_db
from app.models import AuditLog, CollectionRun, Source, Tender, TenderDocument, User
from app.schemas import (
    SourceCreate,
    SourceOut,
    SourceUpdate,
    TenderCreate,
    TenderDocumentOut,
    TenderOut,
    TenderUpdate,
)
from app.scheduler import scheduler_snapshot
from app.security import get_current_admin
from app.services.monitoring import platform_stats
from app.services.duplicates import search_duplicate_groups
from app.services.monitoring import coverage_stats
from app.services.classification import apply_classification

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
    responses={401: {"description": "Admin authentication required"}},
)

LG_TYPES = ["metropolitan_city", "sub_metropolitan_city", "municipality", "rural_municipality"]


def _audit(db: Session, admin: User, action: str, entity_id: int | None, details: str | None = None):
    db.add(AuditLog(actor_user_id=admin.id, action=action, entity_id=entity_id, details=details))


def _tender_payload(rows: list[Tender]) -> list[dict]:
    return [TenderOut.model_validate(row).model_dump(mode="json") for row in rows]


@router.get("/stats")
def admin_stats(db: Session = Depends(get_db)):
    return platform_stats(db)


@router.get("/tenders")
def review_queue(
    verification_status: str | None = "pending",
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Tender).options(selectinload(Tender.documents))
    if verification_status:
        query = query.filter(Tender.verification_status == verification_status)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            Tender.title.ilike(term)
            | Tender.organization_name.ilike(term)
            | Tender.notice_number.ilike(term)
        )
    total = query.count()
    rows = (
        query.order_by(Tender.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": _tender_payload(rows), "total": total, "page": page, "page_size": page_size}


@router.post("/tenders", response_model=TenderOut, status_code=201)
def create_tender(
    payload: TenderCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if payload.notice_number and db.query(Tender).filter(
        Tender.notice_number == payload.notice_number
    ).first():
        raise HTTPException(status_code=409, detail="Duplicate notice number")
    tender = Tender(
        **payload.model_dump(), created_by=admin.id, verification_status="pending", status="open"
    )
    apply_classification(tender)
    db.add(tender)
    db.flush()
    _audit(db, admin, "create", tender.id)
    db.commit()
    db.refresh(tender)
    return tender


@router.patch("/tenders/{tender_id}", response_model=TenderOut)
def update_tender(
    tender_id: int,
    payload: TenderUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    tender = db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(tender, key, value)
    apply_classification(tender)
    _audit(db, admin, "update", tender.id)
    db.commit()
    db.refresh(tender)
    return tender


@router.post("/tenders/{tender_id}/verify", response_model=TenderOut)
def verify_tender(
    tender_id: int,
    decision: str = Query(pattern="^(verified|rejected)$"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    tender = db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    tender.verification_status = decision
    _audit(db, admin, decision, tender.id)
    db.commit()
    db.refresh(tender)
    return tender


@router.post("/tenders/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a CSV file")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV must be 5 MB or smaller")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not reader.fieldnames or not {"title", "organization_name"}.issubset(reader.fieldnames):
            raise ValueError("CSV needs title and organization_name columns")
        added = skipped = 0
        for row in reader:
            title = (row.get("title") or "").strip()
            organization = (row.get("organization_name") or "").strip()
            if not title or not organization:
                skipped += 1
                continue
            notice = (row.get("notice_number") or "").strip() or None
            if notice and db.query(Tender).filter(Tender.notice_number == notice).first():
                skipped += 1
                continue

            def date_value(key):
                value = (row.get(key) or "").strip()
                return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

            db.add(
                Tender(
                    title=title[:500],
                    organization_name=organization[:300],
                    notice_number=notice,
                    category=(row.get("category") or "Other").strip(),
                    province=(row.get("province") or "").strip() or None,
                    district=(row.get("district") or "").strip() or None,
                    municipality=(row.get("municipality") or "").strip() or None,
                    description=(row.get("description") or "").strip() or None,
                    published_date=date_value("published_date"),
                    deadline=date_value("deadline"),
                    source_name=(row.get("source_name") or "CSV import").strip(),
                    source_url=(row.get("source_url") or "").strip() or None,
                    document_url=(row.get("document_url") or "").strip() or None,
                    created_by=admin.id,
                    verification_status="pending",
                    status="open",
                )
            )
            added += 1
        _audit(db, admin, "csv_import", None, f"added={added}; skipped={skipped}")
        db.commit()
        return {
            "success": True,
            "added": added,
            "skipped": skipped,
            "message": "Imported notices require admin verification.",
        }
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}")


@router.get("/sources")
def list_sources(
    q: str | None = None,
    source_type: str | None = None,
    discovery_status: str | None = None,
    active: bool | None = None,
    failing: bool | None = None,
    has_tender_page: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Source)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            Source.name.ilike(term)
            | Source.organization_name.ilike(term)
            | Source.district.ilike(term)
        )
    if source_type:
        query = query.filter(Source.source_type == source_type)
    if discovery_status:
        query = query.filter(Source.discovery_status == discovery_status)
    if active is not None:
        query = query.filter(Source.active.is_(active))
    if failing:
        query = query.filter(Source.consecutive_failures > 0)
    if has_tender_page is True:
        query = query.filter(Source.tender_page_url.isnot(None))
    elif has_tender_page is False:
        query = query.filter(Source.tender_page_url.is_(None))
    total = query.count()
    rows = (
        query.order_by(Source.priority.asc(), Source.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [SourceOut.model_validate(row).model_dump(mode="json") for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/sources", response_model=SourceOut, status_code=201)
def create_source(
    payload: SourceCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    base_slug = _slug(payload.name)
    slug = base_slug
    counter = 2
    while db.query(Source).filter(Source.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    row = Source(
        slug=slug,
        name=payload.name,
        name_ne=payload.name_ne,
        organization_name=payload.organization_name or payload.name,
        source_type=payload.source_type,
        level=payload.level,
        province=payload.province,
        district=payload.district,
        municipality=payload.municipality,
        official_website=payload.official_website,
        tender_page_url=payload.tender_page_url,
        collector_key=payload.collector_key,
        discovery_status="discovered" if payload.tender_page_url else "unregistered",
        active=payload.active,
        priority=payload.priority,
        requires_authorization=payload.requires_authorization,
        notes=payload.notes,
    )
    db.add(row)
    _audit(db, admin, "source_create", None, payload.name)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(
    source_id: int,
    payload: SourceUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    row = db.get(Source, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(row, key, value)
    if changes.get("tender_page_url") and row.discovery_status in {"unregistered", "inaccessible"}:
        row.discovery_status = "discovered"
    row.last_error = None
    row.consecutive_failures = 0
    _audit(db, admin, "source_update", source_id, json.dumps(changes, default=str)[:2000])
    db.commit()
    db.refresh(row)
    return row


@router.post("/sources/{source_id}/toggle", response_model=SourceOut)
def toggle_source(
    source_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    row = db.get(Source, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    row.active = not row.active
    _audit(db, admin, "source_toggle", source_id, f"active={row.active}")
    db.commit()
    db.refresh(row)
    return row


@router.post("/sources/{source_id}/scan")
def scan_source(
    source_id: int,
    wait: bool = False,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    row = db.get(Source, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    if not row.tender_page_url:
        raise HTTPException(status_code=400, detail="Source has no tender page URL yet")
    if wait:
        result = run_collection(db, mode="source", trigger="manual", source_ids=[source_id], limit=1)
    else:
        result = launch_background_run(mode="source", trigger="manual", source_ids=[source_id], limit=1)
    _audit(db, admin, "source_scan", source_id, result.get("status"))
    db.commit()
    return result


@router.post("/sources/retry-failed")
def retry_failed(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    result = retry_failed_sources(db, limit=limit)
    _audit(db, admin, "retry_failed_sources", None, json.dumps(result, default=str)[:2000])
    db.commit()
    return result


@router.post("/collection/run")
def start_collection(
    mode: str = Query("priority", pattern="^(priority|full|local|retry)$"),
    wait: bool = False,
    limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if mode == "retry":
        result = retry_failed_sources(db, limit=limit or 10)
    elif wait:
        sync_registry(db)
        result = run_collection(db, mode=mode, trigger="manual", limit=limit)
    else:
        sync_registry(db)
        result = launch_background_run(mode=mode, trigger="manual", limit=limit)
    _audit(db, admin, "collection_run", None, f"mode={mode}; status={result.get('status')}")
    db.commit()
    return result


@router.get("/collection/runs")
def collection_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(CollectionRun)
    if status:
        query = query.filter(CollectionRun.status == status)
    total = query.count()
    rows = (
        query.order_by(CollectionRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "trigger": row.trigger,
                "mode": row.mode,
                "status": row.status,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
                "duration_ms": row.duration_ms,
                "sources_checked": row.sources_checked,
                "sources_ok": row.sources_ok,
                "sources_failed": row.sources_failed,
                "candidates_found": row.candidates_found,
                "inserted": row.inserted,
                "duplicates": row.duplicates,
                "documents_found": row.documents_found,
                "notes": row.notes,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/collection/runs/{run_id}")
def collection_run_detail(run_id: int, db: Session = Depends(get_db)):
    row = db.get(CollectionRun, run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": row.id,
        "trigger": row.trigger,
        "mode": row.mode,
        "status": row.status,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "duration_ms": row.duration_ms,
        "sources_checked": row.sources_checked,
        "sources_ok": row.sources_ok,
        "sources_failed": row.sources_failed,
        "candidates_found": row.candidates_found,
        "inserted": row.inserted,
        "duplicates": row.duplicates,
        "documents_found": row.documents_found,
        "errors": json.loads(row.errors_json or "[]"),
        "notes": row.notes,
        "scans": [
            {
                "source_id": scan.source_id,
                "source_name": scan.source_name,
                "url": scan.url,
                "status": scan.status,
                "http_status": scan.http_status,
                "items_found": scan.items_found,
                "documents_found": scan.documents_found,
                "inserted": scan.inserted,
                "duplicates": scan.duplicates,
                "duration_ms": scan.duration_ms,
                "error": scan.error,
                "scanned_at": scan.scanned_at,
            }
            for scan in row.scans
        ],
    }


@router.get("/duplicates")
def duplicates(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    groups = search_duplicate_groups(db, limit=limit)
    return {"items": groups, "count": len(groups)}


@router.get("/documents")
def documents(
    download_status: str | None = None,
    tender_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(TenderDocument)
    if download_status:
        query = query.filter(TenderDocument.download_status == download_status)
    if tender_id:
        query = query.filter(TenderDocument.tender_id == tender_id)
    total = query.count()
    rows = (
        query.order_by(TenderDocument.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [TenderDocumentOut.model_validate(row).model_dump(mode="json") for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "status_counts": dict(
            db.query(TenderDocument.download_status, func.count(TenderDocument.id))
            .group_by(TenderDocument.download_status)
            .all()
        ),
    }


@router.post("/discovery/run")
def run_discovery(
    limit: int = Query(8, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    result = discover_local_governments(db, limit=limit)
    _audit(db, admin, "local_discovery", None, json.dumps(result, default=str)[:2000])
    db.commit()
    return result


@router.get("/monitoring")
def monitoring(db: Session = Depends(get_db)):
    return {"platform": platform_stats(db), "scheduler": scheduler_snapshot()}


@router.get("/scheduler")
def scheduler_health():
    return scheduler_snapshot()


@router.get("/audit")
def audit_log(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": row.id,
                "actor_user_id": row.actor_user_id,
                "action": row.action,
                "entity_id": row.entity_id,
                "details": row.details,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.get("/collector/coverage")
def collector_coverage(db: Session = Depends(get_db)):
    """Legacy-compatible collector coverage endpoint."""
    stats = platform_stats(db)["sources"]
    return {
        "registered_sources": stats["registered"],
        "healthy_sources": stats["scanned_successfully"],
        "failed_sources": stats["failing"],
        "never_checked_sources": stats["never_scanned"],
        "requires_authorization": stats["requires_authorization"],
        "coverage": coverage_stats(db),
    }


@router.get("/health")
def admin_health(db: Session = Depends(get_db)):
    from sqlalchemy import text

    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": db.bind.dialect.name,
        "scheduler": scheduler_snapshot(),
        "sources": db.query(Source).count(),
        "tenders": db.query(Tender).count(),
        "documents": db.query(TenderDocument).count(),
    }
