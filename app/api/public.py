"""Public, read-only API. No admin operation is exposed here."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Query as SqlQuery
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import SavedSearch, Source, Tender, TenderChange, TenderDocument
from app.schemas import (
    SavedSearchCreate,
    TenderChangeOut,
    TenderDocumentOut,
    TenderOut,
)
from app.services.monitoring import coverage_stats, platform_stats
from app.services.query import (
    TenderQueryParams,
    apply_filters,
    apply_sort,
    paginate,
    value_counts,
)

router = APIRouter(prefix="/api/v1", tags=["tenders"])

SortKey = Literal["newest", "oldest", "closing", "deadline", "updated"]


def _empty(value: str | None) -> str | None:
    return None if value is None else (value.strip() or None)


def _query_with_documents(query: SqlQuery) -> SqlQuery:
    return query.options(selectinload(Tender.documents))


def _serialise(rows: list[Tender]) -> list[dict]:
    return [TenderOut.model_validate(row).model_dump(mode="json") for row in rows]


def _filters(
    *,
    q: str | None = None,
    category: str | None = None,
    province: str | None = None,
    district: str | None = None,
    municipality: str | None = None,
    organization: str | None = None,
    status: str | None = None,
    verification_status: str | None = None,
    has_documents: bool | None = None,
    published_from: datetime | None = None,
    published_to: datetime | None = None,
    deadline_from: datetime | None = None,
    deadline_to: datetime | None = None,
    include_rejected: bool = False,
    ids: list[int] | None = None,
) -> TenderQueryParams:
    return TenderQueryParams(
        q=_empty(q),
        category=_empty(category),
        province=_empty(province),
        district=_empty(district),
        municipality=_empty(municipality),
        organization=_empty(organization),
        status=_empty(status),
        verification_status=_empty(verification_status),
        has_documents=has_documents,
        published_from=published_from,
        published_to=published_to,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        include_rejected=include_rejected,
        ids=ids,
    )


@router.get("/tenders/all")
def list_all_tenders(
    q: str | None = None,
    category: str | None = None,
    province: str | None = None,
    district: str | None = None,
    municipality: str | None = None,
    organization: str | None = None,
    status: str | None = None,
    verification_status: str | None = Query(default=None, pattern="^(pending|verified|rejected)$"),
    include_rejected: bool = False,
    has_documents: bool | None = None,
    published_from: datetime | None = None,
    published_to: datetime | None = None,
    deadline_from: datetime | None = None,
    deadline_to: datetime | None = None,
    ids: str | None = Query(
        default=None,
        description="Comma-separated tender ids (max 200), used by saved lists.",
        max_length=1200,
    ),
    sort: SortKey = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Public full-record feed including pending notices (rejected excluded by default)."""
    selected_ids: list[int] | None = None
    if ids:
        try:
            selected_ids = [int(item) for item in ids.split(",") if item.strip()][:200]
        except ValueError:
            raise HTTPException(status_code=422, detail="ids must be a comma-separated list of integers")
        if not selected_ids:
            selected_ids = None
    params = _filters(
        q=q,
        category=category,
        province=province,
        district=district,
        municipality=municipality,
        organization=organization,
        status=status,
        verification_status=verification_status,
        has_documents=has_documents,
        published_from=published_from,
        published_to=published_to,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        include_rejected=include_rejected,
        ids=selected_ids,
    )
    query = apply_sort(apply_filters(db.query(Tender), params), sort)
    total, rows = paginate(_query_with_documents(query), page, page_size)
    return {
        "items": _serialise(rows),
        "total": total,
        "page": page,
        "page_size": page_size,
        "sort": sort,
    }


@router.get("/tenders")
def list_tenders(
    q: str | None = None,
    category: str | None = None,
    province: str | None = None,
    district: str | None = None,
    municipality: str | None = None,
    organization: str | None = None,
    status: str | None = "open",
    has_documents: bool | None = None,
    verified_only: bool = Query(
        default=False,
        description=(
            "Restrict to admin-verified records. Off by default because collected notices "
            "stay pending until reviewed; pending records are public and clearly labelled."
        ),
    ),
    sort: SortKey = "closing",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Public listing; pass ``verified_only=true`` for the reviewed-only feed.

    This endpoint used to hard-code the verified filter, which made it return an
    empty page whenever no administrator had reviewed the collected notices yet.
    """
    params = _filters(
        q=q,
        category=category,
        province=province,
        district=district,
        municipality=municipality,
        organization=organization,
        status=status or None,
        verification_status="verified" if verified_only else None,
        has_documents=has_documents,
    )
    query = apply_sort(apply_filters(db.query(Tender), params), sort)
    total, rows = paginate(_query_with_documents(query), page, page_size)
    return {
        "items": _serialise(rows),
        "total": total,
        "page": page,
        "page_size": page_size,
        "sort": sort,
    }


@router.get("/tenders/latest")
def latest_tenders(
    limit: int = Query(10, ge=1, le=100),
    verified_only: bool = False,
    category: str | None = None,
    province: str | None = None,
    db: Session = Depends(get_db),
):
    params = _filters(category=category, province=province)
    if verified_only:
        params.verification_status = "verified"
    query = apply_sort(apply_filters(db.query(Tender), params), "newest").limit(limit)
    rows = _query_with_documents(query).all()
    return {"items": _serialise(rows), "count": len(rows), "verified_only": verified_only}


@router.get("/tenders/closing-soon")
def closing_soon_tenders(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    province: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    params = _filters(province=province, category=category, status="open")
    query = apply_filters(db.query(Tender), params)
    query = (
        query.filter(Tender.deadline.isnot(None))
        .filter(Tender.deadline >= now)
        .filter(Tender.deadline <= now + timedelta(days=days))
    )
    rows = _query_with_documents(
        query.order_by(Tender.deadline.asc(), Tender.id.asc()).limit(limit)
    ).all()
    return {
        "items": _serialise(rows),
        "count": len(rows),
        "days": days,
        "window_ends": (now + timedelta(days=days)).isoformat(),
    }


@router.get("/tenders/{tender_id:int}")
def tender_detail(tender_id: int, db: Session = Depends(get_db)):
    tender = _query_with_documents(
        db.query(Tender).filter(Tender.id == tender_id)
    ).first()
    if not tender or tender.verification_status == "rejected":
        raise HTTPException(status_code=404, detail="Tender not found")
    return TenderOut.model_validate(tender).model_dump(mode="json")


@router.get("/tenders/{tender_id:int}/documents")
def tender_documents(tender_id: int, db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if not tender or tender.verification_status == "rejected":
        raise HTTPException(status_code=404, detail="Tender not found")
    rows = (
        db.query(TenderDocument)
        .filter(TenderDocument.tender_id == tender_id)
        .order_by(TenderDocument.id.asc())
        .all()
    )
    return {
        "tender_id": tender_id,
        "items": [TenderDocumentOut.model_validate(row).model_dump(mode="json") for row in rows],
        "count": len(rows),
        "source_url": tender.source_url,
    }


@router.get("/tenders/{tender_id:int}/changes")
def tender_changes(tender_id: int, db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if not tender or tender.verification_status == "rejected":
        raise HTTPException(status_code=404, detail="Tender not found")
    rows = (
        db.query(TenderChange)
        .filter(TenderChange.tender_id == tender_id)
        .order_by(TenderChange.detected_at.desc())
        .limit(100)
        .all()
    )
    return {
        "tender_id": tender_id,
        "items": [TenderChangeOut.model_validate(row).model_dump(mode="json") for row in rows],
        "count": len(rows),
    }


@router.get("/tenders/{tender_id:int}/sources")
def tender_sources(tender_id: int, db: Session = Depends(get_db)):
    """All source records linked to this tender (canonical + duplicates)."""
    tender = db.get(Tender, tender_id)
    if not tender or tender.verification_status == "rejected":
        raise HTTPException(status_code=404, detail="Tender not found")
    changes = (
        db.query(TenderChange)
        .filter(TenderChange.tender_id == tender_id)
        .filter(TenderChange.change_type == "duplicate_source")
        .all()
    )
    return {
        "tender_id": tender_id,
        "primary_source": {"name": tender.source_name, "url": tender.source_url},
        "additional_sources": [
            {"url": change.source_url, "note": change.note, "detected_at": change.detected_at}
            for change in changes
        ],
        "count": len(changes) + 1,
    }


@router.get("/categories")
def categories(
    province: str | None = None,
    district: str | None = None,
    verification_status: str | None = Query(default=None, pattern="^(pending|verified|rejected)$"),
    db: Session = Depends(get_db),
):
    params = _filters(province=province, district=district, verification_status=verification_status)
    return {
        "items": value_counts(db, Tender.category, params),
        "note": "Counts follow the same filters as /tenders/all unless verification_status is supplied.",
    }


@router.get("/provinces")
def provinces(
    verification_status: str | None = Query(default=None, pattern="^(pending|verified|rejected)$"),
    db: Session = Depends(get_db),
):
    params = _filters(verification_status=verification_status)
    return {"items": value_counts(db, Tender.province, params)}


@router.get("/districts")
def districts(
    province: str | None = None,
    verification_status: str | None = Query(default=None, pattern="^(pending|verified|rejected)$"),
    db: Session = Depends(get_db),
):
    params = _filters(province=province, verification_status=verification_status)
    return {"items": value_counts(db, Tender.district, params)}


@router.get("/municipalities")
def municipalities(
    district: str | None = None,
    province: str | None = None,
    db: Session = Depends(get_db),
):
    params = _filters(district=district, province=province)
    return {"items": value_counts(db, Tender.municipality, params)}


@router.get("/organizations")
def organizations(
    q: str | None = None,
    province: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    params = _filters(province=province)
    return {"items": value_counts(db, Tender.organization_name, params, limit=limit, search=_empty(q))}


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    payload = platform_stats(db)
    return {
        "tenders": payload["tenders"],
        "sources": payload["sources"],
        "documents": payload["documents"],
        "collection": payload["collection"],
        "generated_at": payload["generated_at"],
        "note": "Pending records are public but unverified; check the original notice before bidding.",
    }


@router.get("/coverage")
def coverage(db: Session = Depends(get_db)):
    payload = coverage_stats(db)
    source_rows = db.query(Source)
    payload["sources"] = {
        "registered": source_rows.count(),
        "active": source_rows.filter(Source.active.is_(True)).count(),
        "failing": source_rows.filter(Source.consecutive_failures > 0).count(),
        "requires_authorization": source_rows.filter(Source.requires_authorization.is_(True)).count(),
        "never_scanned": source_rows.filter(Source.last_checked_at.is_(None)).count(),
        "local_governments": source_rows.filter(
            Source.source_type.in_(
                ["metropolitan_city", "sub_metropolitan_city", "municipality", "rural_municipality"]
            )
        ).count(),
    }
    return payload


@router.get("/sources")
def list_public_sources(
    source_type: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Source)
        .filter(Source.active.is_(True))
        .filter(Source.requires_authorization.is_(False))
        .filter(Source.tender_page_url.isnot(None))
    )
    if source_type:
        query = query.filter(Source.source_type == source_type)
    rows = query.order_by(Source.priority.asc(), Source.name.asc()).limit(limit).all()
    return {
        "items": [
            {
                "id": row.id,
                "name": row.name,
                "name_ne": row.name_ne,
                "source_type": row.source_type,
                "level": row.level,
                "province": row.province,
                "district": row.district,
                "website": row.official_website,
                "tender_page_url": row.tender_page_url,
                "last_success_at": row.last_success_at,
                "notices_found": row.notices_found,
                "documents_found": row.documents_found,
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.post("/saved-searches", status_code=201)
def create_saved_search(payload: SavedSearchCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(SavedSearch)
        .filter(SavedSearch.device_id == payload.device_id)
        .count()
    )
    if existing >= 20:
        raise HTTPException(status_code=429, detail="This device already has 20 saved searches")
    row = SavedSearch(
        device_id=payload.device_id,
        label=payload.label,
        filters_json=json.dumps(payload.filters, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "label": row.label,
        "filters": payload.filters,
        "created_at": row.created_at,
    }


@router.get("/saved-searches")
def list_saved_searches(device_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(SavedSearch)
        .filter(SavedSearch.device_id == device_id)
        .order_by(SavedSearch.created_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "label": row.label,
                "filters": json.loads(row.filters_json or "{}"),
                "active": row.active,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.delete("/saved-searches/{search_id:int}")
def delete_saved_search(search_id: int, device_id: str, db: Session = Depends(get_db)):
    row = db.get(SavedSearch, search_id)
    if not row or row.device_id != device_id:
        raise HTTPException(status_code=404, detail="Saved search not found")
    db.delete(row)
    db.commit()
    return {"deleted": True, "id": search_id}


@router.get("/changes")
def recent_changes(
    limit: int = Query(50, ge=1, le=200),
    change_type: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(TenderChange).order_by(TenderChange.detected_at.desc())
    if change_type:
        query = query.filter(TenderChange.change_type == change_type)
    rows = query.limit(limit).all()
    return {"items": [TenderChangeOut.model_validate(row).model_dump(mode="json") for row in rows]}


@router.get("/filters/options")
def filter_options(db: Session = Depends(get_db)):
    """One call that returns every filter menu used by clients."""
    return {
        "categories": value_counts(db, Tender.category),
        "provinces": value_counts(db, Tender.province),
        "districts": value_counts(db, Tender.district),
        "municipalities": value_counts(db, Tender.municipality, limit=60),
        "organizations": value_counts(db, Tender.organization_name, limit=60),
        "statuses": [
            {"value": value, "count": count}
            for value, count in db.query(Tender.status, func.count(Tender.id))
            .group_by(Tender.status)
            .all()
        ],
        "verification_statuses": [
            {"value": value, "count": count}
            for value, count in db.query(Tender.verification_status, func.count(Tender.id))
            .group_by(Tender.verification_status)
            .all()
        ],
    }
