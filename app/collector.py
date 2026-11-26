"""Conservative discovery adapters for public Nepal procurement notice pages.

Only public, allowlisted pages are fetched. New candidates remain pending until
an administrator checks the original notice. No login, CAPTCHA bypass, private
API, or protected document download is performed.
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

# Official public sources. PPMO remains the national source; agency and local
# government pages add notices that may not be easy to discover centrally.
PPMO_SOURCES = [
    "https://ppmo.gov.np/category/purchase-notice/",
    "https://ppmo.gov.np/category/bid-notice/",
]
OFFICIAL_SOURCES = [
    "https://www.nea.org.np/en/tender/prequalification",
    "https://www.dor.gov.np/dorfcb",
    "https://bhadrapurmun.gov.np/en/public-procurement-tender-notices",
    "https://damakmun.gov.np/en/public-procurement-tender-notices",
    "https://arjundharamun.gov.np/en/public-procurement-tender-notices",
    "https://kankaImun.gov.np/ne/public-procurement-tender-notices",
    "https://itaharimun.gov.np/ne/public-procurement-tender-notices",
    "https://www.dharan.gov.np/ne/public-procurement-tender-notices",
    "https://pokharamun.gov.np/public-procurement-tender-notices",
    "https://gorkhamun.gov.np/en/public-procurement-tender-notices",
    "https://banepamun.gov.np/en/public-procurement-tender-notices",
    "https://tilottamamun.gov.np/en/public-procurement-tender-notices",
    "https://sainamainamun.gov.np/en/public-procurement-tender-notices",
    "https://ramdhunimun.gov.np/en/public-procurement-tender-notices",
]
ALLOWED_HOSTS = {
    "ppmo.gov.np", "www.ppmo.gov.np", "nea.org.np", "www.nea.org.np",
    "dor.gov.np", "www.dor.gov.np", "bhadrapurmun.gov.np",
    "damakmun.gov.np", "arjundharamun.gov.np", "kankaImun.gov.np",
    "itaharimun.gov.np", "www.dharan.gov.np", "pokharamun.gov.np",
    "gorkhamun.gov.np", "banepamun.gov.np", "tilottamamun.gov.np",
    "sainamainamun.gov.np", "ramdhunimun.gov.np",
}
NOTICE_PHRASES = (
    "invitation for bid", "invitation for bids", "invitation for electronic",
    "invitation for e-bid", "invitation for e-bids", "inviting tender",
    "inviting quotation", "request for proposal", "request for expression",
    "sealed quotation", "sealed bid", "tender notice", "bid notice",
    "procurement of", "supply of", "construction of", "e-bid",
    "बोलपत्र आह्वान", "बोलपत्रको आह्वान", "बोलपत्र-आह्वान",
    "बोलपत्र आब्हान", "बोलपत्र आव्हान", "दरभाउपत्र आह्वान",
    "दरभाउपत्रको आह्वान", "सिलबन्दी दरभाउपत्र", "आशयपत्र (eoi) आह्वान",
    "eoi सम्बन्धी सूचना",
)
NON_TENDER_PHRASES = (
    "registration procedure", "registration manual", "user manual",
    "bidder registration", "e-gp system", "submission deadline",
    "extension of the tender", "extension of bid", "deadline extension",
    "contract award", "award notice", "letter of intent", "notice of intent",
    "bid opening", "tender cancellation", "amendment", "addendum",
    "clarification", "shortlisted consulting", "public holiday",
    "म्याद थप", "म्याद नपर्ने", "प्रक्रिया पुस्तिका", "दर्ता प्रक्रिया",
    "संशोधित सूचना", "बोलपत्र स्वीकृत", "आशयको सूचना", "बोलपत्र खोलेको",
    "ठेक्का स्वीकृत",
)
USER_AGENT = "BiddersNepalNoticeBot/1.2 (+https://bidders-nepal-api.onrender.com; public notice discovery)"


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_HOSTS


def _sources() -> list[str]:
    configured = os.getenv("TENDER_SOURCE_URLS", "")
    extra = [x.strip() for x in configured.split(",") if x.strip()]
    # Keep PPMO pagination bounded. Other sources are queried at their public
    # listing URL; their own pagination is not guessed.
    ppmo = [f"{base}?page={page}" for base in PPMO_SOURCES for page in range(1, 6)]
    return list(dict.fromkeys(
        url for url in ppmo + OFFICIAL_SOURCES + extra if _allowed(url)
    ))


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme.lower(), (parsed.hostname or "").lower(),
                       parsed.path.rstrip("/") or "/", parsed.params, parsed.query, ""))


def _looks_like_notice(text: str) -> bool:
    title = " ".join((text or "").split()).lower()
    if not title or any(phrase in title for phrase in NON_TENDER_PHRASES):
        return False
    return any(phrase in title for phrase in NOTICE_PHRASES)


def _organization_from_title(text: str) -> str:
    title = " ".join((text or "").split())
    match = re.match(
        r"^(?:श्री\s*)?(.+?)(?:को|का)\s+(?=(?:पुनः\s*)?(?:बोलपत्र|दरभाउपत्र|आशयपत्र|eoi))",
        title, re.IGNORECASE,
    )
    if not match:
        return "Not identified - admin review required"
    organization = match.group(1).strip(" ,।-")
    return organization if 3 <= len(organization) <= 300 else "Not identified - admin review required"


def _notice_number(text: str) -> str | None:
    patterns = [
        r"\b(?:IFB|RFP|EOI|PQ|NCB|SQ)[\w./() -]{3,70}",
        r"\b[A-Z]{2,}[A-Z0-9./()_-]{2,}(?:/[A-Z0-9._-]+){1,5}\b",
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


def _source_name(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    names = {
        "ppmo.gov.np": "PPMO", "www.ppmo.gov.np": "PPMO",
        "nea.org.np": "Nepal Electricity Authority", "www.nea.org.np": "Nepal Electricity Authority",
        "dor.gov.np": "Department of Roads", "www.dor.gov.np": "Department of Roads",
    }
    if host in names:
        return names[host]
    return host.replace("www.", "").split(".")[0].replace("mun", "").title() + " Municipality"


def _is_document_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"))


def _candidate_rows(soup: BeautifulSoup, page_url: str):
    """Yield title, organization, notice number, deadline, source page, document URL."""
    host = (urlparse(page_url).hostname or "").lower()
    if host in {"nea.org.np", "www.nea.org.np"}:
        for row in soup.select("table tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) < 6:
                continue
            values = [" ".join(cell.get_text(" ", strip=True).split()) for cell in cells]
            if len(values) < 7 or not values[2] or not values[3]:
                continue
            title, office, number = values[3], values[1], values[2]
            if len(title) < 12:
                continue
            links = cells[4].select("a[href]")
            doc_url = urljoin(page_url, links[0]["href"]) if links else None
            if doc_url and not _allowed(doc_url):
                doc_url = None
            yield title, office, number, _deadline(" ".join(values)), page_url, doc_url
        return

    for anchor in soup.select("a[href]"):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if len(title) < 12 or len(title) > 500 or not _looks_like_notice(title):
            continue
        target = _canonical_url(urljoin(page_url, (anchor.get("href") or "").strip()))
        if not _allowed(target) or target == _canonical_url(page_url):
            continue
        if host in {"ppmo.gov.np", "www.ppmo.gov.np"} and not re.match(r"^/content/\\d+/", urlparse(target).path):
            continue
        document_url = target if _is_document_url(target) else None
        source_page = page_url if document_url else target
        yield title, _organization_from_title(title), _notice_number(title), _deadline(title), source_page, document_url

def _duplicate(db: Session, url: str, notice: str | None, title: str, organization: str) -> bool:
    existing_urls = db.query(Tender.id).filter(Tender.source_url == url).first()
    if existing_urls:
        return True
    if notice:
        # Cross-source notice numbers are the strongest duplicate key.
        if db.query(Tender).filter(Tender.notice_number.ilike(notice)).first():
            return True
    # Conservative fallback only when both title and organization are known.
    if organization and "admin review" not in organization.lower():
        if db.query(Tender).filter(
            Tender.title.ilike(title), Tender.organization_name.ilike(organization)
        ).first():
            return True
    return False


def collect_public_notices(db: Session) -> dict:
    """Fetch allowlisted official pages and insert unseen candidates as pending."""
    discovered = inserted = duplicates = failed = 0
    checked_at = datetime.now(timezone.utc)
    sources = _sources()
    for source_url in sources:
        try:
            response = requests.get(
                source_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                timeout=(8, 20), allow_redirects=True,
            )
            response.raise_for_status()
            if not _allowed(response.url):
                raise ValueError("Redirected outside approved public-source hosts")
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for title, organization, notice, deadline, target, document_url in _candidate_rows(soup, response.url):
                discovered += 1
                if _duplicate(db, target, notice, title, organization):
                    duplicates += 1
                    continue
                db.add(Tender(
                    title=title[:500],
                    organization_name=(organization or "Not identified - admin review required")[:300],
                    notice_number=notice,
                    category=_category(title),
                    description=("Discovered from a public official procurement page. Verify the "
                                 "procuring entity, deadline, eligibility and documents against "
                                 "the original notice before publication."),
                    deadline=deadline,
                    source_name=_source_name(response.url),
                    source_url=target,
                    document_url=document_url,
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
        "message": "Official public-source candidates only; verify each original notice before publication.",
    }
