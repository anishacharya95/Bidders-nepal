"""Shared tender query building, sorting, facets and pagination."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.models import Tender, TenderDocument


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TenderQueryParams:
    q: str | None = None
    category: str | None = None
    procurement_type: str | None = None
    province: str | None = None
    district: str | None = None
    municipality: str | None = None
    organization: str | None = None
    ministry: str | None = None
    department: str | None = None
    notice_number: str | None = None
    source: str | None = None
    status: str | None = None
    verification_status: str | None = None
    has_documents: bool | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    deadline_from: datetime | None = None
    deadline_to: datetime | None = None
    expiring_days: int | None = None
    include_rejected: bool = False
    ids: list[int] | None = None


def _deadline_utc():
    """Normalise a possibly-naive deadline column for comparison with UTC now."""
    return Tender.deadline


def apply_filters(query: Query, params: TenderQueryParams) -> Query:
    if params.ids:
        query = query.filter(Tender.id.in_(params.ids))
    if params.verification_status:
        query = query.filter(Tender.verification_status == params.verification_status)
    elif not params.include_rejected:
        query = query.filter(Tender.verification_status != "rejected")

    if params.q:
        term = f"%{params.q.strip()}%"
        query = query.filter(
            or_(
                Tender.title.ilike(term),
                Tender.organization_name.ilike(term),
                Tender.notice_number.ilike(term),
                Tender.description.ilike(term),
                Tender.municipality.ilike(term),
                Tender.district.ilike(term),
                Tender.province.ilike(term),
                Tender.source_name.ilike(term),
                Tender.ministry.ilike(term),
                Tender.department.ilike(term),
                Tender.procurement_type.ilike(term),
                Tender.category.ilike(term),
            )
        )
    if params.category:
        query = query.filter(Tender.category == params.category)
    if params.procurement_type:
        query = query.filter(Tender.procurement_type == params.procurement_type)
    if params.province:
        query = query.filter(Tender.province.ilike(params.province))
    if params.district:
        query = query.filter(Tender.district.ilike(params.district))
    if params.municipality:
        query = query.filter(Tender.municipality.ilike(params.municipality))
    if params.organization:
        query = query.filter(Tender.organization_name.ilike(f"%{params.organization}%"))
    if params.ministry:
        query = query.filter(Tender.ministry.ilike(f"%{params.ministry}%"))
    if params.department:
        query = query.filter(Tender.department.ilike(f"%{params.department}%"))
    if params.notice_number:
        term = f"%{params.notice_number.strip()}%"
        query = query.filter(
            or_(Tender.notice_number.ilike(term), Tender.raw_source_id.ilike(term))
        )
    if params.source:
        term = f"%{params.source.strip()}%"
        query = query.filter(
            or_(Tender.source_name.ilike(term), Tender.source_url.ilike(term))
        )

    if params.status:
        status = params.status.strip().lower()
        now = _now()
        if status in {"active", "open"}:
            # "Open" must still be within its deadline: a notice whose deadline
            # has passed is expired even if the last scan marked it open.
            query = query.filter(Tender.status == "open")
            query = query.filter(or_(Tender.deadline.is_(None), Tender.deadline >= now))
        elif status in {"expired", "past"}:
            query = query.filter(Tender.deadline.isnot(None))
            query = query.filter(Tender.deadline < now)
            query = query.filter(Tender.status.notin_(["cancelled", "awarded"]))
        else:
            query = query.filter(Tender.status == status)

    if params.has_documents is True:
        query = query.filter(
            or_(
                Tender.document_url.isnot(None),
                Tender.documents.any(TenderDocument.id.isnot(None)),
            )
        )
    elif params.has_documents is False:
        query = query.filter(Tender.document_url.is_(None))
        query = query.filter(~Tender.documents.any(TenderDocument.id.isnot(None)))
    if params.published_from:
        query = query.filter(Tender.published_date >= params.published_from)
    if params.published_to:
        query = query.filter(Tender.published_date <= params.published_to)
    if params.deadline_from:
        query = query.filter(Tender.deadline >= params.deadline_from)
    if params.deadline_to:
        query = query.filter(Tender.deadline <= params.deadline_to)
    if params.expiring_days:
        now = _now()
        query = query.filter(Tender.deadline.isnot(None))
        query = query.filter(Tender.deadline >= now)
        query = query.filter(Tender.deadline <= now + timedelta(days=params.expiring_days))
    return query


def apply_sort(query: Query, sort: str | None) -> Query:
    if sort == "oldest":
        return query.order_by(
            func.coalesce(Tender.published_date, Tender.created_at).asc(), Tender.id.asc()
        )
    if sort == "closing":
        return query.order_by(Tender.deadline.asc().nulls_last(), Tender.created_at.desc())
    if sort == "updated":
        return query.order_by(Tender.updated_at.desc(), Tender.id.desc())
    if sort == "deadline":
        return query.order_by(Tender.deadline.asc().nulls_last(), Tender.created_at.desc())
    if sort == "organization":
        return query.order_by(
            Tender.organization_name.asc().nulls_last(),
            func.coalesce(Tender.published_date, Tender.created_at).desc(),
            Tender.id.desc(),
        )
    if sort == "published":
        return query.order_by(
            Tender.published_date.desc().nulls_last(), Tender.id.desc()
        )
    return query.order_by(
        func.coalesce(Tender.published_date, Tender.created_at).desc(), Tender.id.desc()
    )


def paginate(query: Query, page: int, page_size: int) -> tuple[int, list[Tender]]:
    total = query.order_by(None).count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return total, rows


def value_counts(
    db: Session,
    column,
    params: TenderQueryParams | None = None,
    *,
    limit: int = 100,
    search: str | None = None,
) -> list[dict]:
    query = db.query(column.label("value"), func.count(Tender.id).label("count")).filter(
        column.isnot(None), column != ""
    )
    if params:
        query = apply_filters(query, params)
    if search:
        query = query.filter(column.ilike(f"%{search}%"))
    rows = query.group_by(column).order_by(func.count(Tender.id).desc()).limit(limit).all()
    return [{"value": value, "count": count} for value, count in rows]
