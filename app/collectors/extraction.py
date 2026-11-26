"""Tender text extraction helpers.

Everything here is deliberately conservative: when a field cannot be read with
confidence the function returns None so the API exposes a null instead of an
invented value.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

NOTICE_PHRASES = (
    "invitation for bid", "invitation for bids", "invitation for electronic",
    "invitation for e-bid", "invitation for e-bids", "inviting tender",
    "inviting quotation", "request for proposal", "request for expression",
    "sealed quotation", "sealed bid", "tender notice", "bid notice",
    "procurement of", "supply of", "construction of", "e-bid",
    "bid document", "bidding document", "bid docs", "tender document",
    "expression of interest", "prequalification", "request for quotation",
    "बोलपत्र आह्वान", "बोलपत्रको आह्वान", "बोलपत्र-आह्वान",
    "बोलपत्र आब्हान", "बोलपत्र आव्हान", "दरभाउपत्र आह्वान",
    "दरभाउपत्रको आह्वान", "सिलबन्दी दरभाउपत्र", "आशयपत्र (eoi) आह्वान",
    "eoi सम्बन्धी सूचना", "बोलपत्र कागजात", "बोलपत्र दस्तावेज",
    "बोलपत्र", "दरभाउपत्र", "लिलाम", "आशयपत्र", "निविदा",
    "खरिद सूचना", "खरिद सम्बन्धी सूचना", "ठेक्का",
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
    "ठेक्का स्वीकृत", "सम्पर्क", "contact us", "about us",
)

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def normalise_space(value: str | None) -> str:
    return " ".join((value or "").split())


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return urlunparse(
        (parsed.scheme.lower(), host, parsed.path.rstrip("/") or "/", parsed.params, parsed.query, "")
    )


APPROVED_EXTRA_HOSTS = {
    "nea.org.np",
    "caanepal.gov.np",
    "bolpatra.gov.np",
    "ppmo.gov.np",
    "mofaga.gov.np",
    "nepal.gov.np",
}


def allowed_host(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return False
    if host.startswith("www."):
        host = host[4:]
    return (
        host.endswith(".gov.np")
        or host == "gov.np"
        or host in APPROVED_EXTRA_HOSTS
        or host.endswith(".gov.np.np")
    )


def looks_like_notice(text: str, path: str | None = None) -> bool:
    title = normalise_space(text).lower()
    if not title:
        return False
    if path and re.search(r"/(contact|about|privacy|login|register|search)(/|$)", path, re.I):
        return False
    if any(phrase in title for phrase in NON_TENDER_PHRASES):
        # "amendment"/"addendum" titles are collected as notice types elsewhere,
        # but they are not new tender listings on an index page.
        return False
    return any(phrase in title for phrase in NOTICE_PHRASES)


def is_notice_detail_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if not path or path == "":
        return False
    if host in {"ppmo.gov.np", "www.ppmo.gov.np"}:
        return bool(re.match(r"^/content/\d+", path))
    if re.search(r"^/(category|page|tag|search|author)(/|$)", path, re.I):
        return False
    if re.search(r"(our-team|team-detail|staff|employee|contact|about-us|gallery)(/|$)", path, re.I):
        return False
    return path.count("/") >= 1


def organization_from_title(text: str) -> str:
    title = normalise_space(text)
    match = re.match(
        r"^(?:श्री\s*)?(.+?)(?:को|का)\s+(?=(?:पुनः\s*)?(?:बोलपत्र|दरभाउपत्र|आशयपत्र|eoi|निविदा))",
        title,
        re.IGNORECASE,
    )
    if not match:
        return "Not identified - admin review required"
    organization = match.group(1).strip(" ,।-")
    return organization if 3 <= len(organization) <= 300 else "Not identified - admin review required"


def notice_number(text: str) -> str | None:
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


def category_from_text(text: str) -> str:
    value = (text or "").lower()
    if any(x in value for x in ("consultancy", "consultant", "expression of interest", "eoi", "परामर्श", "आशयपत्र")):
        return "Consultancy"
    if any(x in value for x in ("goods", "supply", "procurement of", "purchase", "आपूर्ति", "सामग्री")):
        return "Goods"
    if any(x in value for x in ("construction", "road", "building", "bridge", "works", "निर्माण", "सडक", "भवन")):
        return "Works"
    if any(x in value for x in ("service", "maintenance", "cleaning", "सेवा")):
        return "Services"
    return "Other"


def notice_type_from_text(text: str) -> str:
    value = (text or "").lower()
    if any(x in value for x in ("cancellation", "cancelled", "रद्द")):
        return "cancellation"
    if any(x in value for x in ("deadline extension", "extension of bid", "extension of the tender", "म्याद थप")):
        return "deadline_extension"
    if any(x in value for x in ("amendment", "addendum", "संशोधित", "addenda")):
        return "amendment"
    if any(x in value for x in ("award", "letter of intent", "contract award", "ठेक्का स्वीकृत")):
        return "award"
    if any(x in value for x in ("bid opening", "बोलपत्र खोलेको")):
        return "bid_opening"
    if any(x in value for x in ("expression of interest", "eoi", "आशयपत्र")):
        return "eoi"
    if any(x in value for x in ("request for proposal", "rfp")):
        return "rfp"
    if any(x in value for x in ("request for quotation", "rfq", "quotation", "दरभाउपत्र")):
        return "rfq"
    if "prequalification" in value or "pq" in value.split():
        return "prequalification"
    return "tender_notice"


def parse_deadline(text: str) -> datetime | None:
    patterns = (
        r"\b(20\d{2}-\d{2}-\d{2})\b",
        r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2})\b",
        r"\b([A-Za-z]{3,9}\s+\d{1,2},?\s+20\d{2})\b",
        r"\b(\d{1,2}/\d{1,2}/20\d{2})\b",
    )
    formats = (
        "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%B %d %Y",
        "%b %d, %Y", "%b %d %Y", "%d/%m/%Y",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        raw = re.sub(r"\s+", " ", match.group(1)).replace(",", "")
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", text or "")
    if match:
        try:
            return datetime(
                int(match.group(1)), int(match.group(2)), int(match.group(3)),
                int(match.group(4)), int(match.group(5)), tzinfo=timezone.utc,
            )
        except ValueError:
            return None
    return None


def parse_number(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_budget(text: str) -> float | None:
    match = re.search(
        r"(?:estimated\s+(?:cost|amount|budget)|bid\s+security|cost\s+estimate)[^\d]{0,40}"
        r"(?:NPR|Rs\.?|रु\.?)?\s*([\d][\d,.\s]{2,20})",
        text or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    return parse_number(match.group(1))


def extract_bid_security(text: str) -> float | None:
    match = re.search(
        r"bid\s+security[^\d]{0,40}(?:NPR|Rs\.?)?\s*([\d][\d,.\s]{2,20})",
        text or "",
        re.IGNORECASE,
    )
    return parse_number(match.group(1)) if match else None


def extract_contact(text: str) -> str | None:
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text or "")
    phone = re.search(r"(?:\+977[-\s]?)?0?\d{1,3}[-\s]\d{6,8}", text or "")
    parts = [value for value in (email.group(0) if email else None, phone.group(0) if phone else None) if value]
    return " | ".join(parts) if parts else None


def extract_organization_from_page(title: str, heading: str | None, source_name: str) -> str:
    for candidate in (heading, title):
        value = normalise_space(candidate)
        if not value:
            continue
        extracted = organization_from_title(value)
        if "not identified" not in extracted.lower():
            return extracted
    return source_name or "Not identified - admin review required"


CATEGORY_LABELS = ["Works", "Goods", "Consultancy", "Services", "Other"]
