"""Conservative duplicate detection.

Rules, in priority order:
1. identical canonical source URL or identical raw source identifier;
2. identical normalised notice / tender number;
3. same organisation + same deadline + very similar title;
4. same source host + identical normalised title + same publication date.

Titles that merely look alike are not merged: the organisation or notice
identity must agree. False negatives are preferred over destroying distinct
notices.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Tender

TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "ref", "source")
TRACKING_KEYS = {"fbclid", "gclid", "ref", "source", "utm_source", "utm_medium", "utm_campaign"}


def normalise_space(value: str | None) -> str:
    return " ".join((value or "").split())


def normalise_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^\w\u0900-\u097F]+", " ", text)
    return " ".join(text.split())


def normalise_notice_number(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def canonical_url(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/") or "/"
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() not in TRACKING_KEYS and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    query.sort()
    return urlunparse(("https", host, path, "", urlencode(query), ""))


def title_similarity(left: str | None, right: str | None) -> float:
    a, b = normalise_text(left), normalise_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def content_hash(*, title: str, organization: str, notice_number: str | None, deadline: datetime | None) -> str:
    import hashlib

    payload = "|".join(
        [
            normalise_text(title),
            normalise_text(organization),
            normalise_notice_number(notice_number),
            deadline.isoformat() if deadline else "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class DuplicateMatch:
    tender: Tender
    reason: str
    confidence: float


def find_duplicate(
    db: Session,
    *,
    source_url: str | None,
    notice_number: str | None,
    title: str,
    organization_name: str,
    deadline: datetime | None = None,
    published_date: datetime | None = None,
    raw_source_id: str | None = None,
    exclude_id: int | None = None,
) -> DuplicateMatch | None:
    url = canonical_url(source_url)
    if url:
        candidates = (
            db.query(Tender)
            .filter(Tender.source_url.isnot(None))
            .filter(Tender.source_url.ilike(f"%{urlparse(url).path[:120]}%"))
            .limit(40)
            .all()
        )
        for tender in candidates:
            if exclude_id and tender.id == exclude_id:
                continue
            if canonical_url(tender.source_url) == url:
                return DuplicateMatch(tender, "canonical_source_url", 1.0)

    normalised_notice = normalise_notice_number(notice_number)
    if normalised_notice and len(normalised_notice) >= 4:
        short = normalise_space(notice_number)[:60]
        rows = (
            db.query(Tender)
            .filter(Tender.notice_number.isnot(None))
            .filter(Tender.notice_number.ilike(f"%{short[:12]}%"))
            .limit(60)
            .all()
        )
        for tender in rows:
            if exclude_id and tender.id == exclude_id:
                continue
            if normalise_notice_number(tender.notice_number) == normalised_notice:
                return DuplicateMatch(tender, "notice_number", 0.99)

    if raw_source_id:
        row = (
            db.query(Tender)
            .filter(Tender.raw_source_id == raw_source_id)
            .filter(Tender.id != exclude_id if exclude_id else True)
            .first()
        )
        if row:
            return DuplicateMatch(row, "source_record_id", 0.99)

    # Fuzzy comparison only among the same organisation (or same source host).
    org_norm = normalise_text(organization_name)
    if not org_norm or "not identified" in org_norm:
        return None

    rows = (
        db.query(Tender)
        .filter(Tender.organization_name.ilike(f"%{normalise_space(organization_name)[:40]}%"))
        .filter(Tender.id != exclude_id if exclude_id else True)
        .order_by(Tender.created_at.desc())
        .limit(50)
        .all()
    )
    for tender in rows:
        if normalise_text(tender.organization_name) != org_norm:
            continue
        similarity = title_similarity(tender.title, title)
        if similarity >= 0.92 and (
            (deadline and tender.deadline and _same_moment(tender.deadline, deadline))
            or (published_date and tender.published_date and _same_day(tender.published_date, published_date))
        ):
            return DuplicateMatch(tender, "similar_title_same_org_and_date", round(similarity, 3))

    # Same title text on the same host and same publication day is a mirror.
    same_title = (
        db.query(Tender)
        .filter(Tender.title == title)
        .filter(Tender.source_url.isnot(None))
        .order_by(Tender.created_at.desc())
        .limit(20)
        .all()
    )
    host = urlparse(url).hostname if url else None
    for tender in same_title:
        if exclude_id and tender.id == exclude_id:
            continue
        tender_host = urlparse(tender.source_url or "").hostname
        if host and tender_host == host and (
            not published_date
            or not tender.published_date
            or _same_day(tender.published_date, published_date)
        ):
            return DuplicateMatch(tender, "same_host_same_title", 0.9)

    return None


def _same_moment(left: datetime, right: datetime) -> bool:
    try:
        return abs(left.timestamp() - right.timestamp()) < 60
    except (ValueError, OSError):
        return left.replace(tzinfo=None) == right.replace(tzinfo=None)


def _same_day(left: datetime, right: datetime) -> bool:
    return left.date() == right.date()


def search_duplicate_groups(db: Session, limit: int = 50) -> list[dict]:
    """Surface likely duplicates for admins without deleting anything."""
    rows = (
        db.query(Tender)
        .filter(Tender.notice_number.isnot(None))
        .order_by(Tender.created_at.desc())
        .limit(2000)
        .all()
    )
    groups: dict[str, list[Tender]] = {}
    for tender in rows:
        key = normalise_notice_number(tender.notice_number)
        if len(key) >= 4:
            groups.setdefault(key, []).append(tender)
    results: list[dict] = []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda item: item.id)
        results.append(
            {
                "key": key,
                "notice_number": items[0].notice_number,
                "tenders": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "organization_name": item.organization_name,
                        "source_name": item.source_name,
                        "source_url": item.source_url,
                        "verification_status": item.verification_status,
                        "created_at": item.created_at,
                    }
                    for item in items
                ],
            }
        )
        if len(results) >= limit:
            break
    return results
