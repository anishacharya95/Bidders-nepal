"""Orchestrated collection runs with duplicate handling, change tracking and health."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.collectors.adapters import Candidate, CollectionError, collect_source, enrich_candidate
from app.collectors.base import HttpFetcher
from app.collectors.registry import register_extra_source, register_json_source, sync_registry
from app.config import settings
from app.models import (
    CollectionRun,
    CollectorSource,
    Source,
    SourceScan,
    Tender,
    TenderChange,
    TenderDocument,
)
from app.services.documents import DiscoveredDocument, probe_document
from app.services.duplicates import content_hash, find_duplicate

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def select_sources(db: Session, mode: str, limit: int | None = None, source_ids: list[int] | None = None) -> list[Source]:
    query = (
        db.query(Source)
        .filter(Source.active.is_(True))
        .filter(Source.requires_authorization.is_(False))
        .filter(Source.tender_page_url.isnot(None))
    )
    if source_ids:
        query = query.filter(Source.id.in_(source_ids))
    elif mode == "priority":
        query = query.filter(Source.priority <= 2)
    elif mode == "local":
        query = query.filter(
            Source.source_type.in_(
                ["metropolitan_city", "sub_metropolitan_city", "municipality", "rural_municipality"]
            )
        )
    limit = limit or (
        settings.collector_priority_limit if mode == "priority" else settings.collector_full_limit
    )
    return (
        query.order_by(Source.priority.asc(), Source.last_checked_at.asc().nulls_first())
        .limit(limit)
        .all()
    )


def _status_for(deadline: datetime | None, notice_type: str | None = None) -> str:
    """Derive a status from the notice type and deadline.

    A cancellation notice is never "open" even when it carries a deadline, and an
    award notice is not biddable either.
    """
    if notice_type == "cancellation":
        return "cancelled"
    if notice_type == "award":
        return "awarded"
    if deadline is None:
        return "open"
    reference = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    return "open" if reference >= _now() else "closed"


def _document_rows(
    documents: list[DiscoveredDocument], source_url: str, fetcher: HttpFetcher, probe_budget: list[int]
) -> list[TenderDocument]:
    rows: list[TenderDocument] = []
    seen: set[str] = set()
    for doc in documents:
        if doc.url in seen:
            continue
        seen.add(doc.url)
        metadata = None
        if settings.collector_probe_documents and probe_budget[0] > 0 and fetcher.permitted(doc.url):
            probe_budget[0] -= 1
            metadata = probe_document(fetcher, doc.url)
        rows.append(
            TenderDocument(
                label=doc.label[:500],
                url=doc.url,
                document_type=doc.document_type or "attachment",
                source_url=source_url,
                file_format=doc.file_format,
                download_status=metadata.status if metadata else "unverified",
                content_type=metadata.content_type if metadata else None,
                file_size_bytes=metadata.size_bytes if metadata else None,
                last_checked_at=_now() if metadata else None,
                is_public=not metadata or metadata.status != "restricted",
            )
        )
    return rows


def _merge_documents(
    tender: Tender, documents: list[TenderDocument], db: Session
) -> int:
    existing = {doc.url for doc in tender.documents}
    added = 0
    for document in documents:
        if document.url in existing:
            continue
        tender.documents.append(document)
        existing.add(document.url)
        added += 1
        db.add(
            TenderChange(
                tender_id=tender.id,
                change_type="document_added",
                field="documents",
                new_value=document.url,
                note=f"New public document discovered: {document.label[:200]}",
                source_url=tender.source_url,
            )
        )
    if added and not tender.document_url:
        tender.document_url = documents[0].url
    return added


def _apply_candidate(tender: Tender, candidate: Candidate, db: Session) -> list[TenderChange]:
    """Update NULL fields and record meaningful source changes."""
    changes: list[TenderChange] = []

    def record(kind: str, field: str, old, new):
        change = TenderChange(
            tender_id=tender.id,
            change_type=kind,
            field=field,
            old_value=None if old is None else str(old)[:2000],
            new_value=None if new is None else str(new)[:2000],
            source_url=candidate.url,
        )
        db.add(change)
        changes.append(change)

    if candidate.deadline and tender.deadline and candidate.deadline != tender.deadline:
        record("deadline_changed", "deadline", tender.deadline, candidate.deadline)
        tender.deadline = candidate.deadline
    elif candidate.deadline and not tender.deadline:
        tender.deadline = candidate.deadline

    new_status = _status_for(tender.deadline, tender.notice_type)
    if tender.status != new_status:
        record("status_changed", "status", tender.status, new_status)
        tender.status = new_status

    if candidate.bid_opening_date and not tender.bid_opening_date:
        tender.bid_opening_date = candidate.bid_opening_date
    if candidate.published_date and not tender.published_date:
        tender.published_date = candidate.published_date
    if candidate.notice_number and not tender.notice_number:
        tender.notice_number = candidate.notice_number
    if candidate.description and not tender.description:
        tender.description = candidate.description
    if candidate.estimated_budget_npr and not tender.estimated_budget_npr:
        tender.estimated_budget_npr = candidate.estimated_budget_npr
    if candidate.bid_security_npr and not tender.bid_security_npr:
        tender.bid_security_npr = candidate.bid_security_npr
    if candidate.eligibility and not tender.eligibility:
        tender.eligibility = candidate.eligibility
    if candidate.contact_info and not tender.contact_info:
        tender.contact_info = candidate.contact_info
    if candidate.province and not tender.province:
        tender.province = candidate.province
    if candidate.district and not tender.district:
        tender.district = candidate.district
    if candidate.municipality and not tender.municipality:
        tender.municipality = candidate.municipality
    if candidate.notice_type and not tender.notice_type:
        tender.notice_type = candidate.notice_type
    if (
        candidate.organization_name
        and "not identified" not in candidate.organization_name.lower()
        and "not identified" in (tender.organization_name or "").lower()
        and tender.verification_status != "verified"
    ):
        tender.organization_name = candidate.organization_name[:300]

    tender.last_seen_at = _now()
    tender.seen_count = (tender.seen_count or 1) + 1
    tender.content_hash = content_hash(
        title=tender.title,
        organization=tender.organization_name,
        notice_number=tender.notice_number,
        deadline=tender.deadline,
    )
    return changes


def _legacy_health(
    db: Session,
    source: Source,
    *,
    ok: bool,
    error: str | None,
    notices: int,
    documents: int,
    run_id: int,
) -> None:
    url = source.tender_page_url or source.official_website or f"registry://{source.slug}"
    record = db.query(CollectorSource).filter(CollectorSource.url == url).first()
    if not record:
        record = CollectorSource(url=url, source_name=source.name)
        db.add(record)
    record.source_name = source.name[:200]
    record.source_type = source.source_type
    record.priority = source.priority
    record.last_run_id = run_id
    record.last_checked_at = _now()
    record.notices_found = notices
    record.documents_found = documents
    if ok:
        record.status = "ok"
        record.last_success_at = _now()
        record.last_error = None
        record.consecutive_failures = 0
    else:
        record.status = "error"
        record.last_error = (error or "Unknown error")[:4000]
        record.consecutive_failures = (record.consecutive_failures or 0) + 1


def run_collection(
    db: Session,
    *,
    mode: str = "priority",
    trigger: str = "manual",
    source_ids: list[int] | None = None,
    limit: int | None = None,
) -> dict:
    started_monotonic = time.monotonic()
    started_at = _now()
    run = CollectionRun(trigger=trigger, mode=mode, status="running", started_at=started_at)
    db.add(run)
    db.commit()
    db.refresh(run)

    errors: list[dict] = []
    source_summaries: list[dict] = []
    totals = {
        "sources_checked": 0,
        "sources_ok": 0,
        "sources_failed": 0,
        "candidates_found": 0,
        "inserted": 0,
        "updated": 0,
        "duplicates": 0,
        "documents_found": 0,
    }

    try:
        if mode in {"priority", "full"}:
            sync_registry(db)
        for extra in [item.strip() for item in settings.extra_source_urls.split(",") if item.strip()]:
            register_extra_source(db, extra)
        for feed in [item.strip() for item in settings.json_source_urls.split(",") if item.strip()]:
            register_json_source(db, feed)
        db.commit()

        sources = select_sources(db, mode, limit=limit, source_ids=source_ids)
        feed_hosts = {
            urlparse(source.tender_page_url).hostname or ""
            for source in sources
            if source.collector_key == "json_api" and source.tender_page_url
        }
        feed_hosts |= {
            item.strip() for item in settings.json_source_hosts.split(",") if item.strip()
        }
        fetcher = HttpFetcher(extra_hosts=feed_hosts)
        detail_budget = settings.collector_detail_fetch_limit

        for source in sources:
            if time.monotonic() - started_monotonic > settings.collector_run_budget_seconds:
                errors.append({"scope": "runner", "message": "Run budget reached; remaining sources deferred"})
                break

            totals["sources_checked"] += 1
            source_pk = source.id
            scan = SourceScan(
                run_id=run.id,
                source_id=source.id,
                source_name=source.name,
                url=source.tender_page_url or "",
                scanned_at=_now(),
            )
            source_notices = 0
            source_docs = 0
            source_inserted = 0
            source_duplicates = 0
            scan_started = time.monotonic()

            try:
                result = collect_source(source, fetcher)
                scan.http_status = result.http_status
                scan.duration_ms = result.duration_ms

                for candidate in result.candidates:
                    totals["candidates_found"] += 1
                    source_notices += 1
                    duplicate = find_duplicate(
                        db,
                        source_url=candidate.url,
                        notice_number=candidate.notice_number,
                        title=candidate.title,
                        organization_name=candidate.organization_name,
                        deadline=candidate.deadline,
                        published_date=candidate.published_date,
                        raw_source_id=candidate.raw_source_id,
                    )
                    if duplicate:
                        totals["duplicates"] += 1
                        source_duplicates += 1
                        existing = duplicate.tender
                        if candidate.url and existing.source_url and candidate.url != existing.source_url:
                            db.add(
                                TenderChange(
                                    tender_id=existing.id,
                                    change_type="duplicate_source",
                                    note=f"Same notice also found at {candidate.url} ({duplicate.reason})",
                                    source_url=candidate.url,
                                )
                            )
                        elif candidate.documents:
                            # Probe a small budget here too: duplicate sources used to
                            # store every attachment as "unverified", so real reachable
                            # bid documents were reported as unconfirmed.
                            docs = _document_rows(
                                candidate.documents,
                                existing.source_url or candidate.url,
                                fetcher,
                                [max(1, min(6, settings.collector_detail_fetch_limit))],
                            )
                            added = _merge_documents(existing, docs, db)
                            totals["documents_found"] += added
                            source_docs += added
                        db.commit()
                        continue

                    if detail_budget > 0:
                        detail_budget -= 1
                        try:
                            candidate = enrich_candidate(candidate, fetcher)
                        except Exception:
                            log.warning("Detail enrichment failed for %s", candidate.url, exc_info=True)

                    documents = _document_rows(
                        candidate.documents, candidate.url, fetcher, [max(1, min(6, 6))]
                    )
                    source_docs += len(documents)
                    totals["documents_found"] += len(documents)

                    tender = Tender(
                        title=candidate.title[:500],
                        notice_number=candidate.notice_number,
                        organization_name=(candidate.organization_name or source.organization_name or source.name)[:300],
                        category=candidate.category or "Other",
                        province=candidate.province or source.province,
                        district=candidate.district or source.district,
                        municipality=candidate.municipality or (
                            source.municipality if source.level == "local" else None
                        ),
                        description=candidate.description,
                        published_date=candidate.published_date,
                        deadline=candidate.deadline,
                        bid_opening_date=candidate.bid_opening_date,
                        estimated_budget_npr=candidate.estimated_budget_npr,
                        bid_security_npr=candidate.bid_security_npr,
                        notice_type=candidate.notice_type,
                        eligibility=candidate.eligibility,
                        contact_info=candidate.contact_info,
                        source_name=source.name[:200],
                        source_url=candidate.url,
                        document_url=documents[0].url if documents else None,
                        status=_status_for(candidate.deadline, candidate.notice_type),
                        verification_status="pending",
                        source_id=source.id,
                        raw_source_id=candidate.raw_source_id,
                        content_hash=content_hash(
                            title=candidate.title,
                            organization=candidate.organization_name or source.name,
                            notice_number=candidate.notice_number,
                            deadline=candidate.deadline,
                        ),
                        first_seen_at=_now(),
                        last_seen_at=_now(),
                        seen_count=1,
                    )
                    db.add(tender)
                    db.flush()
                    for document in documents:
                        tender.documents.append(document)
                    db.add(
                        TenderChange(
                            tender_id=tender.id,
                            change_type="discovered",
                            note=f"First seen on {source.name}",
                            source_url=candidate.url,
                        )
                    )
                    totals["inserted"] += 1
                    source_inserted += 1
                    db.commit()

                source.last_checked_at = _now()
                source.last_success_at = _now()
                source.last_error = None
                source.consecutive_failures = 0
                source.notices_found = source_notices
                source.documents_found = source_docs
                source.discovery_status = "active"
                scan.status = "ok"
                scan.items_found = source_notices
                scan.documents_found = source_docs
                scan.inserted = source_inserted
                scan.duplicates = source_duplicates
                totals["sources_ok"] += 1
                _legacy_health(
                    db, source, ok=True, error=None, notices=source_notices, documents=source_docs, run_id=run.id
                )
                db.add(scan)
                db.commit()
                source_summaries.append(
                    {
                        "name": source.name,
                        "url": source.tender_page_url,
                        "status": "ok",
                        "items": source_notices,
                        "inserted": source_inserted,
                        "duplicates": source_duplicates,
                        "documents": source_docs,
                        "duration_ms": result.duration_ms,
                        "http_status": result.http_status,
                    }
                )
            except (CollectionError, Exception) as exc:  # per-source isolation
                db.rollback()
                totals["sources_failed"] += 1
                message = str(exc)[:2000] or exc.__class__.__name__
                source = db.get(Source, source_pk)
                if source:
                    source.last_checked_at = _now()
                    source.last_error = message
                    source.consecutive_failures = (source.consecutive_failures or 0) + 1
                    if isinstance(exc, CollectionError):
                        source.discovery_status = (
                            "requires_authorization"
                            if "authorized access" in message.lower()
                            else "inaccessible"
                        )
                    else:
                        source.discovery_status = "inaccessible"
                scan.status = "error"
                scan.error = message
                scan.duration_ms = int((time.monotonic() - scan_started) * 1000)
                db.add(scan)
                if source:
                    _legacy_health(db, source, ok=False, error=message, notices=0, documents=0, run_id=run.id)
                db.commit()
                errors.append({"source": source.name if source else "unknown", "message": message})
                source_summaries.append(
                    {
                        "name": source.name if source else "unknown",
                        "url": source.tender_page_url if source else "",
                        "status": "error",
                        "error": message,
                        "duration_ms": scan.duration_ms,
                    }
                )
                log.warning("Collection failed for %s: %s", source.name if source else "?", message)

        closed = close_expired_tenders(db)
        run.finished_at = _now()
        run.duration_ms = int((time.monotonic() - started_monotonic) * 1000)
        run.status = (
            "completed"
            if totals["sources_failed"] == 0
            else "partial" if totals["sources_ok"] > 0 else "failed"
        )
        for key, value in totals.items():
            setattr(run, key, value)
        run.errors_json = json.dumps(errors[:100], ensure_ascii=False)
        run.notes = f"Closed {closed} expired tenders. Requests made: {fetcher.requests_made}."
        db.commit()
    except Exception as exc:  # catastrophic runner error still finalises the run
        db.rollback()
        log.exception("Collection run failed")
        run = db.get(CollectionRun, run.id)
        if run:
            run.status = "failed"
            run.finished_at = _now()
            run.duration_ms = int((time.monotonic() - started_monotonic) * 1000)
            run.errors_json = json.dumps([{"scope": "runner", "message": str(exc)[:2000]}])
            db.commit()
        raise
    finally:
        pass

    return {
        "run_id": run.id,
        "trigger": trigger,
        "mode": mode,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration_ms": run.duration_ms,
        "sources_checked": totals["sources_checked"],
        "sources_ok": totals["sources_ok"],
        "sources_failed": totals["sources_failed"],
        "candidates_found": totals["candidates_found"],
        "inserted": totals["inserted"],
        "duplicates": totals["duplicates"],
        "documents_found": totals["documents_found"],
        "errors": errors,
        "sources": source_summaries,
        "message": "Discovered records are stored as pending until an administrator verifies them.",
    }


def close_expired_tenders(db: Session) -> int:
    """Mark open tenders whose published deadline has passed as closed."""
    now = _now()
    count = (
        db.query(Tender)
        .filter(Tender.status == "open")
        .filter(Tender.deadline.isnot(None))
        .filter(Tender.deadline < now)
        .update({Tender.status: "closed", Tender.updated_at: now}, synchronize_session=False)
    )
    db.commit()
    return int(count or 0)


def launch_background_run(
    mode: str = "priority",
    trigger: str = "admin",
    source_ids: list[int] | None = None,
    limit: int | None = None,
) -> dict:
    """Start a collection without blocking the API request (Render-friendly)."""
    import threading

    from app.database import SessionLocal

    def _target():
        session = SessionLocal()
        try:
            run_collection(
                session, mode=mode, trigger=trigger, source_ids=source_ids, limit=limit
            )
        except Exception:
            log.exception("Background collection run failed")
            session.rollback()
        finally:
            session.close()

    thread = threading.Thread(target=_target, name=f"collect-{mode}", daemon=True)
    thread.start()
    return {
        "status": "scheduled",
        "mode": mode,
        "trigger": trigger,
        "message": "Collection started in the background. Refresh collection history for results.",
    }


def retry_failed_sources(db: Session, limit: int = 10) -> dict:
    rows = (
        db.query(Source)
        .filter(Source.active.is_(True))
        .filter(Source.requires_authorization.is_(False))
        .filter(Source.tender_page_url.isnot(None))
        .filter(Source.consecutive_failures > 0)
        .order_by(Source.consecutive_failures.desc(), Source.last_checked_at.asc())
        .limit(limit)
        .all()
    )
    if not rows:
        return {"retried": 0, "message": "No failing sources to retry."}
    return run_collection(
        db,
        mode="retry",
        trigger="retry",
        source_ids=[row.id for row in rows],
        limit=len(rows),
    )
