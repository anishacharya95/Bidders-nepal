"""Search facets derived from fields the source actually publishes.

Procurement type comes from the published category (and explicit phrases in the
notice text); ministry/department come from the procuring-entity name. Nothing is
invented: when the source text does not support a value, the column stays NULL and
the filter never matches that record.
"""
from __future__ import annotations

import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Tender

PROCUREMENT_TYPES = (
    "Goods",
    "Works",
    "Consulting Services",
    "Non-consulting Services",
)

CATEGORY_TO_PROCUREMENT_TYPE = {
    "Goods": "Goods",
    "Works": "Works",
    "Consultancy": "Consulting Services",
    "Services": "Non-consulting Services",
}

MINISTRY_MARKERS = ("ministry", "मन्त्रालय")
DEPARTMENT_MARKERS = (
    "department",
    "division",
    "directorate",
    "office",
    "authority",
    "board",
    "commission",
    "center",
    "centre",
    "institute",
    "corporation",
    "company",
    "university",
    "hospital",
    "विभाग",
    "कार्यालय",
    "प्राधिकरण",
    "आयोग",
    "बोर्ड",
    "निगम",
)

_EXPLICIT_TYPE_PATTERNS = (
    ("Non-consulting Services", (r"non[\s-]?consulting services?",)),
    ("Consulting Services", (r"(?<!non[\s-])consult(?:ing|ancy) services?", r"consultancy")),
    ("Works", (r"works? contract", r"construction of", r"civil works")),
    ("Goods", (r"supply and delivery", r"supply of", r"procurement of goods")),
)


def procurement_type_for(category: str | None, text: str | None = None) -> str | None:
    """Return one of PROCUREMENT_TYPES when the published data supports it."""
    basis = f"{category or ''} {(text or '')}".lower()
    for label, patterns in _EXPLICIT_TYPE_PATTERNS:
        if any(re.search(pattern, basis) for pattern in patterns):
            return label
    if category:
        mapped = CATEGORY_TO_PROCUREMENT_TYPE.get(category)
        if mapped:
            return mapped
    return None


def ministry_for(organization: str | None) -> str | None:
    """A ministry is recorded only when the entity name names a ministry."""
    value = (organization or "").strip()
    if not value:
        return None
    lowered = value.lower()
    if any(marker in lowered for marker in MINISTRY_MARKERS):
        return value[:300]
    return None


def department_for(organization: str | None) -> str | None:
    """A department/agency is recorded when the entity name names one.

    Ministries already carry their own facet, so they are not duplicated here.
    """
    value = (organization or "").strip()
    if not value or ministry_for(value):
        return None
    lowered = value.lower()
    if any(marker in lowered for marker in DEPARTMENT_MARKERS):
        return value[:300]
    return None


def apply_classification(tender: Tender) -> None:
    """Fill the derived facets on a tender in place (only when still empty)."""
    text = " ".join(filter(None, (tender.title, tender.description, tender.notice_type)))
    if not tender.procurement_type:
        tender.procurement_type = procurement_type_for(tender.category, text)
    if not tender.ministry:
        tender.ministry = ministry_for(tender.organization_name)
    if not tender.department:
        tender.department = department_for(tender.organization_name)


def backfill_classifications(db: Session, limit: int = 5000) -> dict:
    """Backfill derived facets for records collected before the columns existed.

    Uses set-based SQL updates so a large production table is not loaded into
    memory. Idempotent: repeated calls only touch rows that are still empty.
    """
    updated = {"procurement_type": 0, "ministry": 0, "department": 0}

    def limited_ids(*conditions):
        """A limited id subquery: PostgreSQL/SQLite reject UPDATE ... LIMIT."""
        query = db.query(Tender.id)
        for condition in conditions:
            query = query.filter(condition)
        return select(query.limit(limit).subquery().c.id)

    for category, label in CATEGORY_TO_PROCUREMENT_TYPE.items():
        count = (
            db.query(Tender)
            .filter(Tender.id.in_(limited_ids(
                Tender.procurement_type.is_(None), Tender.category == category
            )))
            .update({Tender.procurement_type: label}, synchronize_session=False)
        )
        updated["procurement_type"] += int(count or 0)

    ministry_filters = [Tender.organization_name.ilike(f"%{marker}%") for marker in MINISTRY_MARKERS]
    count = (
        db.query(Tender)
        .filter(Tender.id.in_(limited_ids(
            Tender.ministry.is_(None),
            Tender.organization_name.isnot(None),
            or_(*ministry_filters),
        )))
        .update({Tender.ministry: Tender.organization_name}, synchronize_session=False)
    )
    updated["ministry"] += int(count or 0)

    department_filters = [
        Tender.organization_name.ilike(f"%{marker}%") for marker in DEPARTMENT_MARKERS
    ]
    count = (
        db.query(Tender)
        .filter(Tender.id.in_(limited_ids(
            Tender.department.is_(None),
            Tender.ministry.is_(None),
            Tender.organization_name.isnot(None),
            or_(*department_filters),
        )))
        .update({Tender.department: Tender.organization_name}, synchronize_session=False)
    )
    updated["department"] += int(count or 0)

    db.commit()
    return updated
