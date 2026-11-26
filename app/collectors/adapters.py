"""Source-specific listing parsers."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.collectors.base import HttpFetcher
from app.collectors.extraction import (
    allowed_host,
    canonical_url,
    category_from_text,
    extract_bid_security,
    extract_budget,
    extract_contact,
    is_notice_detail_url,
    looks_like_notice,
    normalise_space,
    notice_number,
    notice_type_from_text,
    organization_from_title,
    parse_deadline,
)
from app.config import settings
from app.models import Source
from app.services.documents import DiscoveredDocument, documents_from_soup, file_format

log = logging.getLogger(__name__)

AMENDMENT_HINTS = ("amendment", "addendum", "addenda", "corrigendum", "संशोधन", "म्याद थप", "extension")


@dataclass
class Candidate:
    title: str
    url: str
    organization_name: str
    notice_number: str | None = None
    category: str = "Other"
    description: str | None = None
    published_date: datetime | None = None
    deadline: datetime | None = None
    bid_opening_date: datetime | None = None
    estimated_budget_npr: float | None = None
    bid_security_npr: float | None = None
    eligibility: str | None = None
    contact_info: str | None = None
    notice_type: str = "tender_notice"
    province: str | None = None
    district: str | None = None
    municipality: str | None = None
    raw_source_id: str | None = None
    documents: list[DiscoveredDocument] = field(default_factory=list)


@dataclass
class SourceCollectionResult:
    source_id: int
    source_name: str
    url: str
    candidates: list[Candidate]
    pages_fetched: int
    http_status: int | None
    duration_ms: int
    requests_made: int


class CollectionError(RuntimeError):
    def __init__(self, message: str, *, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


def _is_amendment(title: str) -> bool:
    lowered = title.lower()
    return any(hint in lowered for hint in AMENDMENT_HINTS)


def _row_text(anchor) -> str:
    for parent_name in ("tr", "li", "article"):
        parent = anchor.find_parent(parent_name)
        if parent is not None:
            return normalise_space(parent.get_text(" ", strip=True))[:600]
    return ""


def _documents_in(element, page_url: str) -> list[DiscoveredDocument]:
    if element is None:
        return []
    return documents_from_soup(element, page_url)


def _candidate_from_generic(anchor, page_url: str, source: Source, row_text: str) -> Candidate | None:
    title = normalise_space(anchor.get_text(" ", strip=True))
    if len(title) < 12 or len(title) > 500:
        return None
    href = (anchor.get("href") or "").strip()
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    target = canonical_url(urljoin(page_url, href))
    if not allowed_host(target):
        return None

    amendment = _is_amendment(title)
    if not looks_like_notice(title) and not (amendment and notice_number(title)):
        return None

    direct_file = file_format(target) is not None
    if not direct_file and not is_notice_detail_url(target):
        return None
    if host := urlparse(target).hostname:
        if host in {"ppmo.gov.np", "www.ppmo.gov.np"} and not re.match(r"^/content/\d+", urlparse(target).path):
            return None

    row = anchor.find_parent(["tr", "li", "article"]) or anchor.parent
    if not row_text:
        row_text = normalise_space(row.get_text(" ", strip=True))[:600] if row else ""

    organization = organization_from_title(title)
    if "not identified" in organization.lower():
        if source.level in {"local", "provincial"}:
            organization = source.organization_name or source.name
        elif source.source_type in {"department", "ministry", "agency", "utility", "central_agency"}:
            organization = source.organization_name or source.name

    documents = _documents_in(row, page_url) if row is not None else []
    if direct_file and not any(doc.url == target for doc in documents):
        documents.append(
            DiscoveredDocument(
                url=target,
                label=title[:500],
                document_type="bid_document",
                file_format=file_format(target),
            )
        )

    text_basis = f"{title} {row_text}"
    return Candidate(
        title=title,
        url=target,
        organization_name=organization[:300],
        notice_number=notice_number(text_basis),
        category=category_from_text(text_basis),
        deadline=parse_deadline(row_text) or parse_deadline(title),
        notice_type="amendment" if amendment else notice_type_from_text(title),
        province=source.province,
        district=source.district,
        municipality=source.municipality,
        raw_source_id=_path_id(target),
        documents=documents,
    )


def _path_id(url: str) -> str | None:
    match = re.search(r"/(?:content|notice|tender|detail)/(\d+)", urlparse(url).path)
    if match:
        return match.group(1)
    tail = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    return tail[:100] if tail else None


def parse_ppmo(soup: BeautifulSoup, page_url: str, source: Source) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        target = canonical_url(urljoin(page_url, (anchor.get("href") or "").strip()))
        path = urlparse(target).path
        if not re.match(r"^/content/\d+", path):
            continue
        title = normalise_space(anchor.get_text(" ", strip=True))
        if len(title) < 10:
            # PPMO listing sometimes wraps the title in a heading inside the row.
            row = anchor.find_parent(["tr", "li", "article", "div"])
            if row is not None:
                heading = row.find(["h1", "h2", "h3", "h4", "strong"])
                title = normalise_space(heading.get_text(" ", strip=True)) if heading else title
        if len(title) < 10 or target in seen:
            continue
        if _is_amendment(title) and not notice_number(title):
            continue
        seen.add(target)
        row = anchor.find_parent(["tr", "li", "article", "div"])
        row_text = normalise_space(row.get_text(" ", strip=True))[:600] if row else ""
        organization = organization_from_title(title)
        candidates.append(
            Candidate(
                title=title[:500],
                url=target,
                organization_name=organization[:300],
                notice_number=notice_number(f"{title} {row_text}"),
                category=category_from_text(f"{title} {row_text}"),
                deadline=parse_deadline(row_text) or parse_deadline(title),
                notice_type="amendment" if _is_amendment(title) else "tender_notice",
                raw_source_id=_path_id(target),
                documents=_documents_in(row, page_url) if row is not None else [],
                province=source.province,
                district=source.district,
            )
        )
    return candidates


def parse_nea(soup: BeautifulSoup, page_url: str, source: Source) -> list[Candidate]:
    candidates: list[Candidate] = []
    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 5:
            continue
        values = [normalise_space(cell.get_text(" ", strip=True)) for cell in cells]
        title = ""
        number = None
        office = ""
        for index, value in enumerate(values):
            if len(value) > 20 and looks_like_notice(value):
                title = value
                if index + 1 < len(values) and re.search(r"[A-Z]{2,}.*\d", values[index + 1]):
                    number = notice_number(values[index + 1])
                office = values[index - 1] if index > 0 and len(values[index - 1]) > 3 else ""
                break
        if not title:
            continue
        row_text = " ".join(values)
        docs = _documents_in(row, page_url)
        candidates.append(
            Candidate(
                title=title[:500],
                url=canonical_url(page_url),
                organization_name=(office or source.organization_name or "Nepal Electricity Authority")[:300],
                notice_number=number or notice_number(row_text),
                category=category_from_text(f"{title} {row_text}"),
                deadline=parse_deadline(row_text),
                notice_type=notice_type_from_text(title),
                raw_source_id=notice_number(row_text),
                documents=docs,
            )
        )
    return candidates


def parse_generic(soup: BeautifulSoup, page_url: str, source: Source) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        row_text = _row_text(anchor)
        candidate = _candidate_from_generic(anchor, page_url, source, row_text)
        if candidate is None or candidate.url in seen:
            continue
        seen.add(candidate.url)
        candidates.append(candidate)
    return candidates


def next_pages(soup: BeautifulSoup, page_url: str) -> list[str]:
    pages: list[str] = []
    for anchor in soup.select("a[href]"):
        text = normalise_space(anchor.get_text(" ", strip=True)).lower()
        rel = (anchor.get("rel") or [])
        if not ("next" in text or "»" in text or "next" in rel or "अर्को" in text):
            continue
        target = urljoin(page_url, (anchor.get("href") or "").strip())
        if urlparse(target).hostname == urlparse(page_url).hostname and allowed_host(target):
            pages.append(target)
    return pages[:2]


def collect_source(source: Source, fetcher: HttpFetcher) -> SourceCollectionResult:
    started = time.monotonic()
    if not source.tender_page_url:
        raise CollectionError("Source has no verified tender page URL")
    if source.requires_authorization:
        raise CollectionError("Source requires authorized access and must not be scraped")

    pages = [source.tender_page_url]
    if source.collector_key == "ppmo":
        base = source.tender_page_url.rstrip("/")
        pages += [f"{base}/?page={number}" for number in range(2, settings.collector_max_pages_per_source + 1)]

    all_candidates: list[Candidate] = []
    seen: set[str] = set()
    pages_fetched = 0
    last_status: int | None = None

    for page_url in pages[: settings.collector_max_pages_per_source]:
        result = fetcher.get(page_url)
        last_status = result.status_code or last_status
        if result.skipped_reason in {"robots_disallowed", "host_not_allowed", "redirect_not_allowed"}:
            raise CollectionError(result.error or "Source is not permitted by the access policy", http_status=last_status)
        if not result.ok:
            if pages_fetched == 0:
                raise CollectionError(
                    result.error or f"HTTP {result.status_code} from source", http_status=last_status
                )
            break
        if not result.is_html:
            raise CollectionError("Source did not return an HTML notice listing", http_status=last_status)

        pages_fetched += 1
        soup = BeautifulSoup(result.text, "html.parser")
        if source.collector_key == "ppmo":
            parsed = parse_ppmo(soup, result.final_url, source)
        elif source.collector_key == "nea":
            parsed = parse_nea(soup, result.final_url, source)
        else:
            parsed = parse_generic(soup, result.final_url, source)

        for candidate in parsed:
            key = candidate.url if candidate.url else f"{candidate.title}|{candidate.organization_name}"
            if key in seen:
                continue
            seen.add(key)
            all_candidates.append(candidate)

        if source.collector_key != "ppmo":
            extra = [url for url in next_pages(soup, result.final_url) if url not in pages]
            pages.extend(extra)
        if len(all_candidates) >= 400:
            break

    return SourceCollectionResult(
        source_id=source.id,
        source_name=source.name,
        url=source.tender_page_url,
        candidates=all_candidates,
        pages_fetched=pages_fetched,
        http_status=last_status,
        duration_ms=int((time.monotonic() - started) * 1000),
        requests_made=fetcher.requests_made,
    )


def _date_near_labels(text: str, labels: tuple[str, ...]) -> datetime | None:
    lowered = text.lower()
    for label in labels:
        index = lowered.find(label)
        if index < 0:
            continue
        window = text[index : index + 220]
        parsed = parse_deadline(window)
        if parsed:
            return parsed
    return None


def _clean_description(text: str | None) -> str | None:
    if not text:
        return None
    value = normalise_space(text)
    if len(value) < 40:
        return None
    return value[:1500]


def enrich_candidate(candidate: Candidate, fetcher: HttpFetcher) -> Candidate:
    """Fetch a detail page once and fill only fields that are still missing."""
    if file_format(candidate.url):
        if not candidate.documents:
            candidate.documents.append(
                DiscoveredDocument(
                    url=candidate.url,
                    label=candidate.title[:500],
                    document_type="bid_document",
                    file_format=file_format(candidate.url),
                )
            )
        return candidate
    if not allowed_host(candidate.url):
        return candidate

    result = fetcher.get(candidate.url, retries=1)
    if not result.ok or not result.is_html:
        return candidate

    soup = BeautifulSoup(result.text, "html.parser")
    page_text = normalise_space(soup.get_text(" ", strip=True))[:12000]

    meta = soup.find("meta", attrs={"name": "description"})
    if not candidate.description:
        description = meta.get("content") if meta else None
        if not description:
            paragraphs = [
                normalise_space(p.get_text(" ", strip=True))
                for p in soup.select("p")
                if len(normalise_space(p.get_text(" ", strip=True))) > 80
            ]
            description = paragraphs[0] if paragraphs else None
        candidate.description = _clean_description(description)

    if not candidate.deadline:
        candidate.deadline = _date_near_labels(
            page_text,
            ("submission deadline", "deadline for submission", "bid submission", "closing date",
             "last date", "बोलपत्र पेश गर्ने", "दरभाउपत्र पेश गर्ने", "म्याद"),
        )
    if not candidate.bid_opening_date:
        candidate.bid_opening_date = _date_near_labels(
            page_text, ("bid opening", "opening of bid", "बोलपत्र खोल्ने")
        )
    if not candidate.published_date:
        candidate.published_date = _date_near_labels(
            page_text, ("published date", "date of publication", "प्रकाशित मिति")
        )
    if not candidate.estimated_budget_npr:
        candidate.estimated_budget_npr = extract_budget(page_text)
    if not candidate.bid_security_npr:
        candidate.bid_security_npr = extract_bid_security(page_text)
    if not candidate.contact_info:
        candidate.contact_info = extract_contact(page_text)
    if not candidate.notice_number:
        candidate.notice_number = notice_number(page_text[:2000])
    if not candidate.eligibility:
        match = re.search(r"eligib\w*[:\-]?\s*(.{20,400})", page_text, re.IGNORECASE)
        if match:
            candidate.eligibility = match.group(1).strip()[:400]
    if "not identified" in candidate.organization_name.lower():
        heading = soup.find(["h1", "h2"])
        if heading:
            candidate.organization_name = normalise_space(heading.get_text(" ", strip=True))[:300]

    known = {doc.url for doc in candidate.documents}
    for doc in documents_from_soup(soup, result.final_url):
        if doc.url not in known:
            candidate.documents.append(doc)
            known.add(doc.url)
    return candidate
