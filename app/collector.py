"""Conservative discovery adapter for public PPMO notice pages.

Discovered pages are candidates only: all records enter the pending review queue.
No login, CAPTCHA, private endpoint, or browser automation is used.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

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
    "बोलपत्र", "दरभाउपत्र", "सिलबन्दी"
)
SKIP_WORDS = ("login", "register", "contact", "privacy", "career", "result", "blacklist")
USER_AGENT = "BiddersNepalNoticeBot/1.0 (+https://bidders-nepal-api.onrender.com; public notice discovery)"


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_HOSTS


def _sources() -> list[str]:
    configured = os.getenv("TENDER_SOURCE_URLS", "")
    sources = [x.strip() for x in configured.split(",") if x.strip()] if configured else DEFAULT_SOURCES
    return [url for url in sources if _allowed(url)]


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


def collect_public_notices(db: Session) -> dict:
    """Fetch allowlisted public pages and insert unseen candidates as pending."""
    discovered = inserted = duplicates = failed = 0
    checked_at = datetime.now(timezone.utc)
    for source_url in _sources():
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
                title = " ".join(anchor.get_text(" ", strip=True).split())
                target = urljoin(response.url, anchor.get("href", ""))
                if not title or len(title) < 12 or len(title) > 500 or not _allowed(target):
                    continue
                if not _looks_like_notice(title, target):
                    continue
                discovered += 1
                fingerprint = hashlib.sha256(target.rstrip("/").lower().encode()).hexdigest()
                existing = db.query(Tender).filter(Tender.source_url == target).first()
                if existing:
                    duplicates += 1
                    continue
                notice = _notice_number(title)
                if notice and db.query(Tender).filter(Tender.notice_number == notice).first():
                    duplicates += 1
                    continue
                db.add(Tender(
                    title=title[:500],
                    organization_name="Public Procurement Monitoring Office (PPMO)",
                    notice_number=notice,
                    category="Other",
                    description="Automatically discovered public notice link. Please review the original notice and complete missing tender details.",
                    source_name="PPMO public website",
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
        "sources_checked": len(_sources()),
        "candidates_found": discovered,
        "inserted_pending_review": inserted,
        "duplicates_skipped": duplicates,
        "source_errors": failed,
        "message": "Candidates are not public until an admin verifies them.",
    }
