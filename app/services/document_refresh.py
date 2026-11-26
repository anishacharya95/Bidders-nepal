"""Periodic re-check of bid-document reachability.

Broken links are common: agencies move files, replace notices and retire old
sites. This job re-probes documents that have not been checked recently and
records their status so the app can show an honest availability label instead of
a blank viewer. It uses the existing collector HTTP client (same host policy,
robots handling and delays), so it never becomes a second collector.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.collectors.base import HttpFetcher
from app.config import settings
from app.models import Source, Tender, TenderDocument
from app.services.documents import probe_document

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def refresh_documents(db: Session, limit: int | None = None, force: bool = False) -> dict:
    if not settings.document_refresh_enabled and not force:
        return {"status": "disabled", "checked": 0}

    limit = limit or settings.document_refresh_batch
    cutoff = _now() - timedelta(hours=settings.document_refresh_hours)

    query = (
        db.query(TenderDocument)
        .join(Tender, Tender.id == TenderDocument.tender_id)
        .filter(Tender.verification_status != "rejected")
        .filter(TenderDocument.is_public.is_(True))
    )
    if not force:
        query = query.filter(
            (TenderDocument.last_checked_at.is_(None)) | (TenderDocument.last_checked_at < cutoff)
        )
    rows = (
        query.order_by(
            TenderDocument.last_checked_at.asc().nulls_first(), TenderDocument.id.asc()
        )
        .limit(limit)
        .all()
    )
    if not rows:
        return {"status": "ok", "checked": 0, "available": 0, "broken": 0}

    feed_hosts = {
        (urlparse(url).hostname or "")
        for (url,) in db.query(Source.tender_page_url)
        .filter(Source.collector_key == "json_api")
        .filter(Source.tender_page_url.isnot(None))
        .all()
    }
    feed_hosts |= {item.strip() for item in settings.json_source_hosts.split(",") if item.strip()}
    fetcher = HttpFetcher(extra_hosts=feed_hosts)

    checked = available = broken = 0
    for document in rows:
        probe = probe_document(fetcher, document.url)
        document.download_status = probe.status
        document.http_status = probe.http_status
        document.is_available = probe.status == "available"
        if probe.content_type and (
            not document.content_type or document.content_type == "application/octet-stream"
        ):
            document.content_type = probe.content_type
        if probe.size_bytes and not document.file_size_bytes:
            document.file_size_bytes = probe.size_bytes
        document.last_checked_at = _now()
        document.checked_count = (document.checked_count or 0) + 1
        checked += 1
        if probe.status == "available":
            available += 1
        elif probe.status in {"missing", "failed"}:
            broken += 1

    db.commit()
    log.info(
        "Document refresh: checked=%s available=%s broken=%s", checked, available, broken
    )
    return {
        "status": "ok",
        "checked": checked,
        "available": available,
        "broken": broken,
    }
