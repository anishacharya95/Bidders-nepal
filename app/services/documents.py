"""Bid document discovery, classification and reachability metadata."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from app.collectors.extraction import allowed_host, canonical_url

DIRECT_FILE_FORMATS = {
    "pdf": "PDF",
    "doc": "DOC",
    "docx": "DOCX",
    "xls": "XLS",
    "xlsx": "XLSX",
    "zip": "ZIP",
    "rar": "RAR",
    "7z": "7Z",
    "csv": "CSV",
    "txt": "TXT",
    "dwg": "DWG",
    "jpg": "JPG",
    "jpeg": "JPG",
    "png": "PNG",
}

DOCUMENT_KINDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("boq", ("boq", "bill of quantity", "bill of quantities", "rate schedule", "बीओक्यू")),
    ("addendum", ("addendum", "addenda", "addendem")),
    ("amendment", ("amendment", "amend", "संशोधन", "संशोधित")),
    ("clarification", ("clarification", "clarifications", "स्पष्टीकरण")),
    ("drawing", ("drawing", "drawings", "design", "नक्सा")),
    ("specification", ("specification", "technical spec", "specs", "विनिर्देश")),
    ("eoi", ("expression of interest", "eoi", "आशयपत्र")),
    ("rfp", ("request for proposal", "rfp")),
    ("rfq", ("request for quotation", "rfq", "quotation", "दरभाउपत्र")),
    ("bid_document", ("bid document", "bidding document", "tender document", "bid doc", "बोलपत्र")),
    ("notice", ("notice", "advertisement", "सूचना")),
)


@dataclass
class DiscoveredDocument:
    url: str
    label: str
    document_type: str
    file_format: str | None
    widget: str = "link"


@dataclass
class DocumentProbe:
    content_type: str | None = None
    size_bytes: int | None = None
    status: str = "unknown"
    http_status: int | None = None


def file_format(url: str) -> str | None:
    path = urlparse(url).path.lower()
    match = re.search(r"\.([a-z0-9]{2,5})$", path)
    if not match:
        return None
    extension = match.group(1)
    return DIRECT_FILE_FORMATS.get(extension, extension.upper())


def is_direct_file(url: str) -> bool:
    return file_format(url) is not None


def classify_document(label: str, url: str) -> str:
    text = f"{label} {unquote(url)}".lower()
    for kind, keywords in DOCUMENT_KINDS:
        if any(keyword in text for keyword in keywords):
            return kind
    return "attachment"


def documents_from_soup(
    soup: BeautifulSoup | Tag,
    page_url: str,
    *,
    source_url: str | None = None,
) -> list[DiscoveredDocument]:
    """Extract only direct public file links; restricted portal links are skipped."""
    found: dict[str, DiscoveredDocument] = {}
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:")):
            continue
        target = canonical_url(urljoin(page_url, href))
        if not target.startswith("https://"):
            continue
        if not is_direct_file(target):
            continue
        if not allowed_host(target):
            # Documents are frequently mirrored on the same approved government
            # host only; unknown CDNs are not claimed as downloadable.
            continue
        label = " ".join(anchor.get_text(" ", strip=True).split())
        if not label:
            label = unquote(urlparse(target).path.rsplit("/", 1)[-1]) or "Document"
        existing = found.get(target)
        if existing and len(existing.label) >= len(label):
            continue
        found[target] = DiscoveredDocument(
            url=target,
            label=label[:500],
            document_type=classify_document(label, target),
            file_format=file_format(target),
        )
    return list(found.values())


def probe_document(fetcher, url: str) -> DocumentProbe:
    """HEAD (or a tiny ranged GET) to record reachability without downloading files."""
    if not allowed_host(url):
        return DocumentProbe(status="link_only")
    try:
        result = fetcher.head(url)
    except Exception:
        return DocumentProbe(status="failed")

    if result is None:
        return DocumentProbe(status="failed")

    content_type = (result.headers or {}).get("content-type", "").split(";")[0].strip() or None
    length = (result.headers or {}).get("content-length")
    size = int(length) if length and length.isdigit() else None
    status_code = result.status_code

    if status_code and 200 <= status_code < 400:
        status = "available"
    elif status_code in {401, 403}:
        status = "restricted"
    elif status_code in {404, 410}:
        status = "missing"
    else:
        status = "failed"

    return DocumentProbe(
        content_type=content_type,
        size_bytes=size,
        status=status,
        http_status=status_code,
    )


def document_published_date(text: str) -> datetime | None:
    from app.collectors.extraction import parse_deadline

    return parse_deadline(text)
