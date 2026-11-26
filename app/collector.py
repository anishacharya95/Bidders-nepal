"""Conservative discovery adapter for public PPMO notice pages.

This adapter discovers candidate links only. It does not claim PPMO is the
procuring entity, and every candidate remains pending until an admin checks
the original notice. No login, CAPTCHA bypass, private API, or protected
document download is performed.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models import Tender

log = logging.getLogger(__name__)

DEFAULT_SOURCES = [
    "https://ppmo.gov.np/category/bid-notices/",
    "https://ppmo.gov.np/",
]
ALLOWED_HOSTS = {"ppmo.gov.np", "www.ppmo.gov.np"}
KEYWORDS = (
    "invitation for bid", "invitation for electronic", "tender", "quotation",
    "expression of interest", "request for proposal", "bid notice",
    "बोलपत्र", "दरभाउपत्र", "सिलबन्दी",
)
SKIP_WORDS = ("login", "register", "contact", "privacy", "career", "result", "blacklist")
USER_AGENT = "BiddersNepalNoticeBot/1.1 (+https://bidders-nepal-api.onrender.com; public notice discovery)"


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_HOSTS


def _sources() -> list[str]:
    configured = os.getenv("TENDER_SOURCE_URLS", "")
    sources = [x.strip() for x in configured.split(",") if x.strip()] if configured else DEFAULT_SOURCES
    return list(dict.fromkeys(url for url in sources if _allowed(url)))


def _canonical_url(url: str) -> str:
    """Normalize harmless URL differences without dropping meaningful query parameters."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme.lower(), (parsed.hostname or "").lower(),
                       parsed.path.rstrip("/") or "/", parsed.params, parsed.query, ""))


def _looks_like_notice(text: str, href: str) -> bool:
    haystack = f"{text} {href}".lower()
    return any(word in haystack for word in KEYWORDS) and not any(word in haystack for word in SKIP_WORDS)


def _notice_number(text: str) -> str | None:
    patterns = [
        r"\b(?:IFB|RFP|EOI|PQ|NCB|SQ)[\w./() -]{3,70}",
        r"\b\d{2,4}/\d{2,4}(?:/\d{2,4})?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip(" -.,;")[:150]
    return None


def _category(text: str) -> str:
    value = text.lower()
    if any(x in value for x in ("consultancy", "consultant", "expression of interest", "eoi")):
        return "Consultancy"
    if any(x in value for x in ("goods", "supply", "procurement of", "purchase")):
        return "Goods"
    if any(x in value for x in ("construction", "road", "building", "bridge", "works")):
        return "Works"
    if any(x in value for x in ("service", "maintenance", "cleaning")):
        return "Services"
    return "Other"


def _deadline(text: str) -> datetime | None:
    """Parse only unambiguous dates; leave other formats for human review."""
    patterns = (
        r"\b(20\d{2}-\d{2}-\d{2})\b",
        r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2})\b",
        r"\b([A-Za-z]{3,9}\s+\d{1,2},?\s+20\d{2})\b",
    )
    formats = ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y")
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        raw = re.sub(r"\s+", " ", match.group(1)).replace(",", "")
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    return None


def collect_public_notices(db: Session) -> dict:
    """Fetch allowlisted public pages and insert unseen candidates as pending."""
    discovered = inserted = duplicates = failed = 0
    checked_at = datetime.now(timezone.utc)
    sources = _sources()
    for source_url in sources:
        try:
            response = requests.get(
                source_url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                timeout=(8, 20),
                allow_redirects=True,
            )
            response.raise_for_status()
            if not _allowed(response.url):
                raise ValueError("Redirected outside the approved PPMO host")
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.select("a[href]"):
                anchor_text = " ".join(anchor.get_text(" ", strip=True).split())
                parent_text = " ".join(anchor.parent.get_text(" ", strip=True).split()) if anchor.parent else ""
                context = " ".join(dict.fromkeys(x for x in (anchor_text, parent_text) if x))
                target = _canonical_url(urljoin(response.url, anchor.get("href", "")))
                if not anchor_text or len(anchor_text) < 12 or len(anchor_text) > 500 or not _allowed(target):
                    continue
                if not _looks_like_notice(context, target):
                    continue
                discovered += 1
                existing = db.query(Tender).filter(Tender.source_url == target).first()
                if existing:
                    duplicates += 1
                    continue
                notice = _notice_number(context)
                if notice and db.query(Tender).filter(Tender.notice_number == notice).first():
                    duplicates += 1
                    continue
                deadline = _deadline(context)
                db.add(Tender(
                    title=anchor_text[:500],
                    organization_name="Not identified - admin review required",
                    notice_number=notice,
                    category=_category(context),
                    description=("Discovered on a public PPMO page. The procuring entity, "
                                  "deadline, eligibility and documents must be checked against "
                                  "the original notice before verification."),
                    deadline=deadline,
                    source_name="PPMO public website (discovery source)",
                    source_url=target,
                    verification_status="pending",
                    status="open",
                ))
                inserted += 1
            db.commit()
        except Exception as exc:
            db.rollback()
            failed += 1
            log.warning("Collector failed for %s: %s", source_url, exc)
    return {
        "checked_at": checked_at.isoformat(),
        "sources_checked": len(sources),
        "candidates_found": discovered,
        "inserted_pending_review": inserted,
        "duplicates_skipped": duplicates,
        "source_errors": failed,
        "message": "Discovered links are candidates, not confirmed tenders. Verify the original notice before publication.",
    }
