"""Platform monitoring and source-coverage statistics."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.collectors.registry import local_directory_counts
from app.models import (
    CollectionRun,
    Source,
    SourceScan,
    Tender,
    TenderChange,
    TenderDocument,
)

LG_TYPE_LABELS = {
    "metropolitan_city": "Metropolitan cities",
    "sub_metropolitan_city": "Sub-metropolitan cities",
    "municipality": "Municipalities",
    "rural_municipality": "Rural municipalities",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def coverage_stats(db: Session) -> dict:
    directory = local_directory_counts()
    lg_types = [
        "metropolitan_city",
        "sub_metropolitan_city",
        "municipality",
        "rural_municipality",
    ]

    by_type = []
    for source_type in lg_types:
        base = db.query(Source).filter(Source.source_type == source_type)
        by_type.append(
            {
                "type": LG_TYPE_LABELS[source_type],
                "directory_expected": directory[
                    {
                        "metropolitan_city": "metropolitan",
                        "sub_metropolitan_city": "sub_metropolitan",
                        "municipality": "municipality",
                        "rural_municipality": "rural_municipality",
                    }[source_type]
                ],
                "registered": base.count(),
                "website_verified": base.filter(Source.official_website.isnot(None)).count(),
                "tender_page_verified": base.filter(Source.tender_page_url.isnot(None)).count(),
                "scanned_successfully": base.filter(Source.last_success_at.isnot(None)).count(),
                "failing": base.filter(Source.consecutive_failures > 0).count(),
            }
        )

    local_rows = db.query(Source).filter(Source.source_type.in_(lg_types))
    statuses = dict(
        db.query(Source.discovery_status, func.count(Source.id))
        .filter(Source.source_type.in_(lg_types))
        .group_by(Source.discovery_status)
        .all()
    )

    return {
        "dataset": directory,
        "local_governments": {
            "directory_entries": directory["total"],
            "registered_in_platform": local_rows.count(),
            "website_verified": local_rows.filter(Source.official_website.isnot(None)).count(),
            "tender_page_verified": local_rows.filter(Source.tender_page_url.isnot(None)).count(),
            "scanned_successfully": local_rows.filter(Source.last_success_at.isnot(None)).count(),
            "unregistered": local_rows.filter(Source.discovery_status == "unregistered").count(),
            "inaccessible": local_rows.filter(Source.discovery_status == "inaccessible").count(),
            "inactive": local_rows.filter(Source.active.is_(False)).count(),
            "statuses": statuses,
            "by_type": by_type,
        },
        "note": (
            "Directory entries come from an official-format local-government dataset. "
            "A local government is counted as connected only after its official website and "
            "tender page are verified and successfully scanned. All 753 are not claimed as connected."
        ),
    }


def platform_stats(db: Session) -> dict:
    now = _now()
    week_ahead = now + timedelta(days=7)
    day_ago = now - timedelta(hours=24)

    sources_total = db.query(Source).count()
    sources_active = db.query(Source).filter(Source.active.is_(True)).count()
    sources_with_page = db.query(Source).filter(Source.tender_page_url.isnot(None)).count()
    sources_failing = db.query(Source).filter(Source.consecutive_failures > 0).count()
    sources_auth = db.query(Source).filter(Source.requires_authorization.is_(True)).count()
    sources_scanned_ok = db.query(Source).filter(Source.last_success_at.isnot(None)).count()

    tender_rows = dict(
        db.query(Tender.verification_status, func.count(Tender.id))
        .group_by(Tender.verification_status)
        .all()
    )
    total_tenders = sum(tender_rows.values())

    open_tenders = (
        db.query(Tender)
        .filter(Tender.status == "open")
        .filter(Tender.verification_status != "rejected")
        .count()
    )
    closing_soon = (
        db.query(Tender)
        .filter(Tender.status == "open")
        .filter(Tender.deadline.isnot(None))
        .filter(Tender.deadline >= now)
        .filter(Tender.deadline <= week_ahead)
        .count()
    )

    document_rows = dict(
        db.query(TenderDocument.download_status, func.count(TenderDocument.id))
        .group_by(TenderDocument.download_status)
        .all()
    )
    documents_total = sum(document_rows.values())

    last_run = db.query(CollectionRun).order_by(CollectionRun.started_at.desc()).first()
    recent_errors = (
        db.query(SourceScan)
        .filter(SourceScan.status == "error")
        .filter(SourceScan.scanned_at >= day_ago)
        .count()
    )
    duplicates_detected = (
        db.query(TenderChange).filter(TenderChange.change_type == "duplicate_source").count()
    )

    return {
        "generated_at": now.isoformat(),
        "sources": {
            "registered": sources_total,
            "active": sources_active,
            "inactive": sources_total - sources_active,
            "with_tender_page": sources_with_page,
            "scanned_successfully": sources_scanned_ok,
            "failing": sources_failing,
            "requires_authorization": sources_auth,
            "never_scanned": db.query(Source)
            .filter(Source.tender_page_url.isnot(None))
            .filter(Source.last_checked_at.is_(None))
            .count(),
        },
        "tenders": {
            "total": total_tenders,
            "verified": tender_rows.get("verified", 0),
            "pending": tender_rows.get("pending", 0),
            "rejected": tender_rows.get("rejected", 0),
            "open": open_tenders,
            "closing_soon_7d": closing_soon,
            "new_last_24h": db.query(Tender).filter(Tender.created_at >= day_ago).count(),
        },
        "documents": {
            "total": documents_total,
            "available": document_rows.get("available", 0),
            "unverified": document_rows.get("unverified", 0),
            "failed": document_rows.get("failed", 0),
            "restricted": document_rows.get("restricted", 0),
        },
        "collection": {
            "last_run": {
                "id": last_run.id,
                "status": last_run.status,
                "mode": last_run.mode,
                "started_at": last_run.started_at,
                "finished_at": last_run.finished_at,
                "inserted": last_run.inserted,
                "sources_checked": last_run.sources_checked,
                "sources_failed": last_run.sources_failed,
            }
            if last_run
            else None,
            "errors_last_24h": recent_errors,
            "duplicates_detected": duplicates_detected,
            "runs_last_7d": db.query(CollectionRun)
            .filter(CollectionRun.started_at >= now - timedelta(days=7))
            .count(),
        },
        "changes": {
            "total": db.query(TenderChange).count(),
            "last_24h": db.query(TenderChange).filter(TenderChange.detected_at >= day_ago).count(),
        },
        "coverage": coverage_stats(db),
    }
