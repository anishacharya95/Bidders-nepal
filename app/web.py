"""Server-rendered public website.

Read-only: every page is built from the platform database, never from sample
data. The JSON API stays at ``/api/v1``; this module only renders HTML.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Tender, TenderChange
from app.services.monitoring import coverage_stats, platform_stats
from app.services.query import (
    TenderQueryParams,
    apply_filters,
    apply_sort,
    value_counts,
)

router = APIRouter(tags=["website"], include_in_schema=False)
templates = Jinja2Templates(directory="app/templates/site")

SORTS = {
    "newest": "Newest published",
    "oldest": "Oldest published",
    "closing": "Closing soonest",
    "updated": "Recently updated",
}
PAGE_SIZE = 20


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _date(value: datetime | None, fmt: str = "%d %b %Y") -> str:
    value = _aware(value)
    return value.strftime(fmt) if value else "Not available"


def _date_time(value: datetime | None) -> str:
    return _date(value, "%d %b %Y, %H:%M")


def _npr(value: float | None) -> str:
    if value is None:
        return "Not available"
    return f"NPR {value:,.0f}"


def _relative(value: datetime | None) -> str:
    value = _aware(value)
    if not value:
        return "Not available"
    delta = datetime.now(timezone.utc) - value
    seconds = delta.total_seconds()
    if seconds < 0:
        return _date(value)
    if seconds < 3600:
        return f"{max(1, int(seconds // 60))} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    if seconds < 604800:
        return f"{int(seconds // 86400)} d ago"
    return _date(value)


def _days_left(value: datetime | None) -> str:
    value = _aware(value)
    if not value:
        return "No deadline published"
    delta = value - datetime.now(timezone.utc)
    days = delta.total_seconds() / 86400
    if days < 0:
        return "Closed"
    if days < 1:
        return "Closes today"
    return f"{int(days)} day{'s' if int(days) != 1 else ''} left"


templates.env.filters["date"] = _date
templates.env.filters["datetime"] = _date_time
templates.env.filters["npr"] = _npr
templates.env.filters["relative"] = _relative
templates.env.filters["days_left"] = _days_left


def _page(request: Request, template: str, *, status_code: int = 200, **context):
    payload = {
        "request": request,
        "path": request.url.path,
        **context,
    }
    return templates.TemplateResponse(request, template, payload, status_code=status_code)


def _count(db: Session, params: TenderQueryParams, *, deadline_days: int | None = None) -> int:
    query = apply_filters(db.query(Tender), params)
    if deadline_days:
        now = datetime.now(timezone.utc)
        query = query.filter(
            Tender.deadline.isnot(None),
            Tender.deadline >= now,
            Tender.deadline <= now + timedelta(days=deadline_days),
        )
    return query.count()


def _fetch(
    db: Session,
    *,
    q: str | None = None,
    category: str | None = None,
    province: str | None = None,
    district: str | None = None,
    organization: str | None = None,
    status: str | None = None,
    verified_only: bool = False,
    sort: str = "newest",
    page: int = 1,
    page_size: int = PAGE_SIZE,
    deadline_days: int | None = None,
    has_documents: bool | None = None,
) -> tuple[TenderQueryParams, int, list[Tender]]:
    params = TenderQueryParams(
        q=(q or "").strip() or None,
        category=(category or "").strip() or None,
        province=(province or "").strip() or None,
        district=(district or "").strip() or None,
        organization=(organization or "").strip() or None,
        status=(status or "").strip() or None,
        verification_status="verified" if verified_only else None,
        has_documents=has_documents,
    )
    query = apply_sort(apply_filters(db.query(Tender), params), sort)
    if deadline_days:
        now = datetime.now(timezone.utc)
        query = query.filter(
            Tender.deadline.isnot(None),
            Tender.deadline >= now,
            Tender.deadline <= now + timedelta(days=deadline_days),
        )
    total = query.order_by(None).count()
    rows = (
        query.options(selectinload(Tender.documents))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return params, total, rows


def _facets(db: Session) -> dict:
    return {
        "categories": value_counts(db, Tender.category),
        "provinces": value_counts(db, Tender.province),
        "districts": value_counts(db, Tender.district, limit=80),
    }


def _list_response(
    request: Request,
    db: Session,
    *,
    template: str = "list.html",
    title: str,
    heading: str,
    subheading: str,
    q: str | None,
    category: str | None,
    province: str | None,
    district: str | None,
    status: str | None,
    verified_only: bool,
    sort: str,
    page: int,
    deadline_days: int | None = None,
    extra: dict | None = None,
):
    sort = sort if sort in SORTS else "newest"
    page = max(1, page)
    params, total, rows = _fetch(
        db,
        q=q,
        category=category,
        province=province,
        district=district,
        status=status,
        verified_only=verified_only,
        sort=sort,
        page=page,
        deadline_days=deadline_days,
    )
    return _page(
        request,
        template,
        title=title,
        heading=heading,
        subheading=subheading,
        rows=rows,
        total=total,
        page=page,
        pages=max(1, math.ceil(total / PAGE_SIZE)),
        sort=sort,
        sorts=SORTS,
        filters={
            "q": q or "",
            "category": category or "",
            "province": province or "",
            "district": district or "",
            "status": status or "",
            "verified_only": verified_only,
            "sort": sort,
            "deadline_days": deadline_days,
        },
        facets=_facets(db),
        **(extra or {}),
    )


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    stats = platform_stats(db)
    _, _, latest = _fetch(db, sort="newest", page_size=8)
    _, _, closing = _fetch(db, sort="closing", page_size=6, deadline_days=14, status="open")
    categories = value_counts(db, Tender.category, limit=6)
    provinces = value_counts(db, Tender.province, limit=8)
    coverage = coverage_stats(db)
    return _page(
        request,
        "home.html",
        title="Nepal government tenders in one place",
        stats=stats,
        latest=latest,
        closing=closing,
        categories=categories,
        provinces=provinces,
        coverage=coverage,
        total_documents=stats["documents"]["total"],
    )


@router.get("/tenders", response_class=HTMLResponse)
def tenders(
    request: Request,
    q: str | None = None,
    category: str | None = None,
    province: str | None = None,
    district: str | None = None,
    status: str | None = None,
    verified_only: bool = False,
    sort: str = "newest",
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    return _list_response(
        request,
        db,
        title="All tenders",
        heading="All tender notices",
        subheading="Every collected notice, newest first. Each record links to its original source.",
        q=q,
        category=category,
        province=province,
        district=district,
        status=status,
        verified_only=verified_only,
        sort=sort,
        page=page,
    )


@router.get("/latest", response_class=HTMLResponse)
def latest(
    request: Request,
    q: str | None = None,
    category: str | None = None,
    province: str | None = None,
    district: str | None = None,
    status: str | None = None,
    verified_only: bool = False,
    sort: str = "newest",
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    return _list_response(
        request,
        db,
        title="Latest tenders",
        heading="Latest tenders",
        subheading="Newly discovered public notices, ordered by publication date.",
        q=q,
        category=category,
        province=province,
        district=district,
        status=status,
        verified_only=verified_only,
        sort=sort,
        page=page,
    )


@router.get("/closing-soon", response_class=HTMLResponse)
def closing_soon(
    request: Request,
    q: str | None = None,
    category: str | None = None,
    province: str | None = None,
    district: str | None = None,
    verified_only: bool = False,
    sort: str = "closing",
    page: int = Query(1, ge=1),
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
):
    return _list_response(
        request,
        db,
        title="Closing soon",
        heading="Closing soon",
        subheading=f"Open notices with a published deadline in the next {days} days.",
        q=q,
        category=category,
        province=province,
        district=district,
        status="open",
        verified_only=verified_only,
        sort=sort,
        page=page,
        deadline_days=days,
        extra={"days": days},
    )


@router.get("/categories", response_class=HTMLResponse)
def categories(request: Request, db: Session = Depends(get_db)):
    counts = value_counts(db, Tender.category)
    return _page(
        request,
        "categories.html",
        title="Tender categories",
        heading="Browse by category",
        counts=counts,
        total=sum(item["count"] for item in counts),
    )


@router.get("/organizations", response_class=HTMLResponse)
def organizations(
    request: Request,
    q: str | None = None,
    province: str | None = None,
    db: Session = Depends(get_db),
):
    params = TenderQueryParams(province=(province or "").strip() or None)
    counts = value_counts(
        db, Tender.organization_name, params, limit=200, search=(q or "").strip() or None
    )
    return _page(
        request,
        "organizations.html",
        title="Organizations",
        heading="Procurement organizations",
        counts=counts,
        q=q or "",
        provinces=value_counts(db, Tender.province),
        province=province or "",
    )


@router.get("/places", response_class=HTMLResponse)
def places(request: Request, db: Session = Depends(get_db)):
    return _page(
        request,
        "places.html",
        title="Provinces and districts",
        heading="Browse by location",
        provinces=value_counts(db, Tender.province),
        districts=value_counts(db, Tender.district, limit=100),
        coverage=coverage_stats(db),
    )


@router.get("/alerts", response_class=HTMLResponse)
def alerts(request: Request, limit: int = Query(80, ge=1, le=200), db: Session = Depends(get_db)):
    rows = (
        db.query(TenderChange)
        .options(selectinload(TenderChange.tender))
        .order_by(TenderChange.detected_at.desc())
        .limit(limit * 2)
        .all()
    )
    rows = [
        row
        for row in rows
        if row.tender is not None and row.tender.verification_status != "rejected"
    ][:limit]
    return _page(
        request,
        "alerts.html",
        title="Tender changes and alerts",
        heading="Latest tender changes",
        rows=rows,
        limit=limit,
    )


@router.get("/saved", response_class=HTMLResponse)
def saved(request: Request):
    return _page(request, "saved.html", title="Saved tenders")


@router.get("/about", response_class=HTMLResponse)
def about(request: Request, db: Session = Depends(get_db)):
    return _page(
        request,
        "about.html",
        title="About Bidders Nepal",
        stats=platform_stats(db),
        coverage=coverage_stats(db),
    )


@router.get("/contact", response_class=HTMLResponse)
def contact(request: Request):
    return _page(request, "contact.html", title="Contact")


@router.get("/tenders/{tender_id:int}", response_class=HTMLResponse)
def tender_detail(tender_id: int, request: Request, db: Session = Depends(get_db)):
    tender = (
        db.query(Tender)
        .options(selectinload(Tender.documents), selectinload(Tender.changes))
        .filter(Tender.id == tender_id)
        .first()
    )
    if not tender or tender.verification_status == "rejected":
        raise HTTPException(status_code=404, detail="Tender not found")
    documents = sorted(tender.documents, key=lambda doc: doc.id)
    changes = sorted(tender.changes, key=lambda row: row.detected_at, reverse=True)[:40]
    additional_sources = [row for row in changes if row.change_type == "duplicate_source"]
    related = (
        db.query(Tender)
        .options(selectinload(Tender.documents))
        .filter(Tender.organization_name == tender.organization_name)
        .filter(Tender.id != tender.id)
        .filter(Tender.verification_status != "rejected")
        .order_by(Tender.created_at.desc())
        .limit(4)
        .all()
    )
    return _page(
        request,
        "tender.html",
        title=tender.title[:120],
        tender=tender,
        documents=documents,
        changes=changes,
        additional_sources=additional_sources,
        related=related,
    )
