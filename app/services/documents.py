"""Bid document discovery, classification and reachability metadata."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote, urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup, Tag

from app.collectors.extraction import allowed_host, canonical_url

DIRECT_FILE_FORMATS = {
    "pdf": "PDF", "doc": "DOC", "docx": "DOCX", "xls": "XLS",
    "xlsx": "XLSX", "zip": "ZIP", "rar": "RAR", "7z": "7Z",
    "csv": "CSV", "txt": "TXT", "dwg": "DWG", "jpg": "JPG",
    "jpeg": "JPG", "png": "PNG",
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

DOWNLOAD_KEYS = {
    "documenturl", "document_url", "attachmenturl", "attachment_url",
    "downloadurl", "download_url", "fileurl", "file_url", "filepath",
    "file_path", "documentpath", "document_path", "attachmentpath",
    "attachment_path", "downloadpath", "download_path",
}
DOWNLOAD_PATH_HINTS = ("/download", "/attachment", "/attachments", "/document",
                       "/documents", "/file", "/files", "/media/")


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


def _extension(value: str) -> str | None:
    parsed = urlparse(value)
    candidates = [parsed.path]
    query = parse_qs(parsed.query)
    for key in ("filename", "fileName", "file", "name", "document"):
        candidates.extend(query.get(key, []))
    for candidate in candidates:
        match = re.search(r"\.([a-z0-9]{2,5})(?:$|[?#])", unquote(candidate).lower())
        if match and match.group(1) in DIRECT_FILE_FORMATS:
            return DIRECT_FILE_FORMATS[match.group(1)]
    return None


def file_format(url: str) -> str | None:
    return _extension(url)


def is_direct_file(url: str) -> bool:
    return file_format(url) is not None


def _is_download_resource(url: str, key_hint: str = "") -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    key = re.sub(r"[^a-z]", "", key_hint.lower())
    if is_direct_file(url):
        return True
    if (
        key in {re.sub(r"[^a-z]", "", item.lower()) for item in DOWNLOAD_KEYS}
        or any(token in key for token in ("download", "document", "attachment", "file"))
    ):
        return True
    if any(hint in path for hint in DOWNLOAD_PATH_HINTS):
        query = parse_qs(parsed.query)
        return bool(query) or path.rstrip("/").endswith(("download", "file", "document", "attachment"))
    return False


def classify_document(label: str, url: str) -> str:
    text = f"{label} {unquote(url)}".lower()
    for kind, keywords in DOCUMENT_KINDS:
        if any(keyword in text for keyword in keywords):
            return kind
    return "attachment"


def _safe_document_url(value: str, page_url: str, key_hint: str = "") -> str | None:
    candidate = value.strip().replace("\\/", "/")
    if not candidate or candidate.startswith(("data:", "blob:", "javascript:", "mailto:")):
        return None
    target = canonical_url(urljoin(page_url, candidate))
    if not target.startswith("https://") or not allowed_host(target):
        return None
    if not _is_download_resource(target, key_hint):
        return None
    return target


def documents_from_soup(
    soup: BeautifulSoup | Tag,
    page_url: str,
    *,
    source_url: str | None = None,
) -> list[DiscoveredDocument]:
    """Find direct public attachments in HTML links, data attributes and embedded JSON.

    The parser deliberately does not guess private API endpoints or turn arbitrary
    project links into documents. It only accepts URLs that look like files or
    explicit download/document/attachment resources on an approved public host.
    """
    found: dict[str, DiscoveredDocument] = {}

    def add(value: str, label: str = "", key_hint: str = "") -> None:
        target = _safe_document_url(value, page_url, key_hint)
        if not target:
            return
        clean_label = " ".join((label or "").split())
        if not clean_label:
            clean_label = unquote(urlparse(target).path.rsplit("/", 1)[-1]) or "Document"
        current = found.get(target)
        if current and len(current.label) >= len(clean_label):
            return
        found[target] = DiscoveredDocument(
            url=target,
            label=clean_label[:500],
            document_type=classify_document(clean_label, target),
            file_format=file_format(target),
        )

    # Ordinary anchor links and common data attributes used by modern portals.
    for anchor in soup.select("a[href], [data-href], [data-url], [data-download-url], [data-file-url]"):
        label = " ".join(anchor.get_text(" ", strip=True).split())
        for attr in ("href", "data-href", "data-url", "data-download-url", "data-file-url"):
            value = anchor.get(attr)
            if value:
                add(str(value), label, attr)

    # Some portals render attachment metadata into JSON rather than anchors.
    # Read only embedded public page data; never manufacture or call API routes.
    scripts = soup.select('script[type="application/json"], script[type="application/ld+json"], script#__NEXT_DATA__')
    for script in scripts[:30]:
        raw = script.string or script.get_text()
        if not raw or len(raw) > 2_000_000:
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue

        def walk(value, parent_key: str = "", inherited_label: str = "") -> None:
            if isinstance(value, dict):
                label = next(
                    (str(value[k]) for k in ("label", "title", "name", "fileName", "filename")
                     if isinstance(value.get(k), (str, int)) and str(value[k]).strip()),
                    inherited_label,
                )
                for key, child in value.items():
                    walk(child, str(key), label)
            elif isinstance(value, list):
                for child in value:
                    walk(child, parent_key, inherited_label)
            elif isinstance(value, str):
                if parent_key.lower() in DOWNLOAD_KEYS or _is_download_resource(value, parent_key):
                    add(value, inherited_label, parent_key)

        walk(payload)

    return list(found.values())


def document_url_fingerprint(url: str) -> str:
    """Stable fingerprint used to de-duplicate document rows for one tender."""
    digest = hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()
    return digest


def probe_document(fetcher, url: str) -> DocumentProbe:
    """HEAD (or a tiny ranged GET) to record reachability without downloading files."""
    if not fetcher.permitted(url):
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
