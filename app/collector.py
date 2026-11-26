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

# Dedicated procurement categories; the old bid-notices archive contains general notices.
DEFAULT_SOURCES = [
    "https://ppmo.gov.np/category/purchase-notice/",
    "https://ppmo.gov.np/category/bid-notice/",
]
ALLOWED_HOSTS = {"ppmo.gov.np", "www.ppmo.gov.np"}
NOTICE_PHRASES = (
    "invitation for bid", "invitation for bids", "invitation for electronic",
    "inviting tender", "inviting quotation", "request for proposal",
    "sealed quotation notice", "tender notice", "bid notice",
    "procurement of", "supply of", "construction of",
    "बोलपत्र आह्वान", "बोलपत्रको आह्वान", "बोलपत्र-आह्वान",
    "बोलपत्र आव्हान", "दरभाउपत्र आह्वान", "दरभाउपत्रको आह्वान",
    "दरभाउपत्र आव्हान", "सिलबन्दी दरभाउपत्र आह्वान",
    "आशयपत्र (eoi) आह्वान", "eoi सम्बन्धी सूचना",
)
NON_TENDER_PHRASES = (
    "registration procedure", "registration manual", "user manual",
    "bidder registration", "e-gp system", "submission deadline",
    "extension of the tender", "extension of bid", "public holiday",
    "म्याद थप", "म्याद नपर्ने", "प्रक्रिया पुस्तिका", "दर्ता प्रक्रिया",
    "प्रणालीमा बोलपत्र पेश", "जानकारी सम्बन्धी", "संशोधित सूचना",
    "revised notice", "extension of", "deadline extension",
)
SKIP_WORDS = ("login", "register", "contact", "privacy", "career", "result", "blacklist")
USER_AGENT = "BiddersNepalNoticeBot/1.1 (+https://bidders-nepal-api.onrender.com; public notice discovery)"


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_HOSTS


def _sources() -> list[str]:
    configured = os.getenv("TENDER_SOURCE_URLS", "")
    bases = [x.strip() for x in configured.split(",") if x.strip()] if configured else DEFAULT_SOURCES
    # PPMO paginates these category listings; inspect a bounded recent window.
    sources = []
    for base in bases:
        if not _allowed(base):
            continue
        sources.extend("{}?page={}".format(base, page) for page in range(1, 6))
    return list(dict.fromkeys(url for url in sources if _allowed(url)))


def _canonical_url(url: str) -> str:
    """Normalize harmless URL differences without dropping meaningful query parameters."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme.lower(), (parsed.hostname or "").lower(),
                       parsed.path.rstrip("/") or "/", parsed.params, parsed.query, ""))


def _is_notice_detail_url(url: str) -> bool:
    """Accept individual PPMO content pages, never category/navigation pages."""
    return bool(re.match(r"^/content/\d+/", urlparse(url).path))


def _looks_like_notice(text: str, href: str = "") -> bool:
    """Classify from the link title only; parent/category text creates false positives."""
    title = " ".join((text or "").split()).lower()
    if not title or any(word in title for word in NON_TENDER_PHRASES):
        return False
    if any(word in title for word in ("login", "register", "contact", "privacy", "career", "blacklist")):
        return False
    return any(phrase in title for phrase in NOTICE_PHRASES)


def _organization_from_title(text: str) -> str:
    """Extract an organization only when a clear Nepali possessive prefix exists."""
    title = " ".join((text or "").split())
    match = re.match(
        r"^(?:श्री\s*)?(.+?)(?:को|का)\s+(?=(?:पुनः\s*)?(?:बोलपत्र|दरभाउपत्र|आशयपत्र|eoi))",
        title,
        re.IGNORECASE,
    )
    if not match:
        return "Not identified - admin review required"
    organization = match.group(1).strip(" ,।-")
    if len(organization) < 3 or len(organization) > 300:
        return "Not identified - admin review required"
    return organization


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
    if any(x in value for x in ("consultancy", "consultant", "expression of interest", "eoi", "परामर्श", "आशयपत्र")):
        return "Consultancy"
    if any(x in value for x in ("goods", "supply", "procurement of", "purchase", "आपूर्ति", "सामग्री")):
        return "Goods"
    if any(x in value for x in ("construction", "road", "building", "bridge", "works", "निर्माण", "सडक", "भवन")):
        return "Works"
    if any(x in value for x in ("service", "maintenance", "cleaning", "सेवा")):
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
                target = _canonical_url(urljoin(response.url, (anchor.get("href", "") or "").strip()))
                if not anchor_text or len(anchor_text) < 12 or len(anchor_text) > 500 or not _allowed(target):
                    continue
                if not _is_notice_detail_url(target) or not _looks_like_notice(anchor_text, target):
                    continue
                discovered += 1
                known_urls = {
                    _canonical_url((value or "").strip())
                    for (value,) in db.query(Tender.source_url).filter(Tender.source_url.isnot(None)).all()
                    if (value or "").strip()
                }
                if target in known_urls:
                    duplicates += 1
                    continue
                notice = _notice_number(anchor_text)
                if notice and db.query(Tender).filter(Tender.notice_number == notice).first():
                    duplicates += 1
                    continue
                deadline = _deadline(anchor_text)
                db.add(Tender(
                    title=anchor_text[:500],
                    organization_name=_organization_from_title(anchor_text),
                    notice_number=notice,
                    category=_category(anchor_text),
                    description=("Discovered on a public PPMO page. The procuring entity, "
                                  "deadline, eligibility and documents must be checked against "
                                  "the original notice before verification."),
                    deadline=deadline,
                    source_name="PPMO procurement-notice category (discovery source)",
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
