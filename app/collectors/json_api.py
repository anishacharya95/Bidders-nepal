"""JSON feed collector.

Some publishers expose their notices as a JSON API instead of an HTML listing,
and an operator may also point the platform at a curated feed served elsewhere
(for example the public Bidders Nepal feed). This module turns such a payload
into the same ``Candidate`` objects the HTML adapters produce, so duplicate
detection, change tracking, document discovery and admin review work unchanged.

Only feeds an administrator explicitly registered (``collector_key="json_api"``)
or listed in ``TENDER_JSON_SOURCE_URLS`` are fetched: the normal government-host
policy still applies to every other source.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from app.config import settings

from app.collectors.extraction import (
    category_from_text,
    normalise_space,
    notice_type_from_text,
    organization_from_title,
    parse_deadline,
)
from app.models import Source
from app.services.documents import DiscoveredDocument, file_format

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from app.collectors.adapters import Candidate, SourceCollectionResult
    from app.collectors.base import HttpFetcher

log_prefix = "json_api"

#: Payload keys that may hold the notice list, in order of preference.
LIST_KEYS = ("items", "results", "data", "tenders", "records", "notices", "docs")

#: A single feed never contributes more than this many notices in one scan.
MAX_ITEMS = 500

TITLE_KEYS = ("title", "notice_title", "tender_title", "subject", "name")
URL_KEYS = (
    "source_url", "notice_url", "detail_url", "url", "link", "href", "document_url",
)
ORG_KEYS = (
    "organization_name", "organization", "organisation", "buyer_name", "buyer",
    "agency", "department", "office", "entity", "publisher",
)
NUMBER_KEYS = (
    "notice_number", "notice_no", "reference_number", "reference_no", "ref_no",
    "tender_number", "bid_number",
)
CATEGORY_KEYS = ("category", "procurement_category")
PROVINCE_KEYS = ("province", "state", "province_name")
DISTRICT_KEYS = ("district", "district_name")
MUNICIPALITY_KEYS = ("municipality", "local_government", "palika")
DESCRIPTION_KEYS = ("description", "summary", "details", "remarks", "scope")
PUBLISHED_KEYS = ("published_date", "published_at", "publication_date", "published")
DEADLINE_KEYS = (
    "deadline", "closing_date", "submission_deadline", "bid_submission_deadline",
    "close_date", "deadline_date",
)
OPENING_KEYS = ("bid_opening_date", "opening_date", "bid_open_date")
BUDGET_KEYS = ("estimated_budget_npr", "estimated_budget", "budget", "estimated_amount")
SECURITY_KEYS = ("bid_security_npr", "bid_security", "bid_bond", "security_amount")
ELIGIBILITY_KEYS = ("eligibility", "eligibility_criteria")
CONTACT_KEYS = ("contact_info", "contact", "contact_details", "contact_person")

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _first(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (dict, list)):
            continue
        return value
    return None


def _text(item: dict[str, Any], keys: tuple[str, ...], limit: int = 500) -> str | None:
    value = _first(item, keys)
    if value is None:
        # Nested objects such as {"organization": {"name": "..."}} are common.
        for key in keys:
            nested = item.get(key)
            if isinstance(nested, dict):
                inner = _text(nested, ("name", "title", "label"), limit)
                if inner:
                    return inner
        return None
    return normalise_space(str(value))[:limit] or None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    match = _NUMBER_RE.search(str(value).replace(",", ""))
    if not match:
        return None
    try:
        parsed = float(match.group(0))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _date(value: Any) -> datetime | None:
    """Accept ISO-8601 timestamps and the free-text dates used on government pages."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = normalise_space(str(value))
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return parse_deadline(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _documents(item: dict[str, Any], feed_url: str) -> list[DiscoveredDocument]:
    raw = item.get("documents") or item.get("attachments") or item.get("files")
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raw = []
    items = list(raw)
    single = item.get("document_url") or item.get("file_url")
    if isinstance(single, str) and single.strip():
        items.append({"url": single})

    documents: list[DiscoveredDocument] = []
    seen: set[str] = set()
    for entry in items:
        if isinstance(entry, str):
            entry = {"url": entry}
        if not isinstance(entry, dict):
            continue
        link = _text(entry, ("url", "link", "href", "file_url", "download_url", "source_url"), 1500)
        if not link:
            continue
        absolute = urljoin(feed_url, link).strip()
        if urlparse(absolute).scheme not in {"http", "https"} or absolute in seen:
            continue
        seen.add(absolute)
        label = _text(entry, ("label", "title", "name", "filename", "file_name"), 500) or "Bid document"
        kind = _text(entry, ("document_type", "type", "kind"), 40) or "bid_document"
        fmt = _text(entry, ("file_format", "format", "extension"), 20) or file_format(absolute)
        documents.append(
            DiscoveredDocument(
                url=absolute,
                label=label,
                document_type=kind.lower().strip().replace(" ", "_")[:40],
                file_format=fmt.upper()[:20] if fmt else file_format(absolute),
            )
        )
    return documents


def feed_items(payload: Any) -> list[Any] | None:
    """Find the notice list inside a payload, however the feed wraps it."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    for key in LIST_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = feed_items(value)
            if nested:
                return nested
    return None


def _candidate_from_item(
    item: Any, source: Source, feed_url: str
) -> "Candidate | None":
    from app.collectors.adapters import Candidate

    if not isinstance(item, dict):
        return None

    title = _text(item, TITLE_KEYS, 500)
    if not title or len(title) < 5:
        return None

    link = _text(item, URL_KEYS, 1500)
    url = urljoin(feed_url, link) if link else feed_url
    if urlparse(url).scheme not in {"http", "https"}:
        url = feed_url

    organization = _text(item, ORG_KEYS, 300) or organization_from_title(title)
    if "not identified" in organization.lower():
        organization = source.organization_name or source.name

    notice_type = (_text(item, ("notice_type",), 40) or notice_type_from_text(title)).lower()
    description = _text(item, DESCRIPTION_KEYS, 1500)

    return Candidate(
        title=title,
        url=url,
        organization_name=organization[:300],
        notice_number=_text(item, NUMBER_KEYS, 150),
        category=_text(item, CATEGORY_KEYS, 40) or category_from_text(title),
        description=description if description and len(description) >= 20 else None,
        published_date=_date(_first(item, PUBLISHED_KEYS)),
        deadline=_date(_first(item, DEADLINE_KEYS)),
        bid_opening_date=_date(_first(item, OPENING_KEYS)),
        estimated_budget_npr=_number(_first(item, BUDGET_KEYS)),
        bid_security_npr=_number(_first(item, SECURITY_KEYS)),
        eligibility=_text(item, ELIGIBILITY_KEYS, 400),
        contact_info=_text(item, CONTACT_KEYS, 500),
        notice_type=notice_type,
        province=_text(item, PROVINCE_KEYS, 100) or source.province,
        district=_text(item, DISTRICT_KEYS, 100) or source.district,
        municipality=_text(item, MUNICIPALITY_KEYS, 120)
        or (source.municipality if source.level == "local" else None),
        raw_source_id=_text(item, ("raw_source_id", "notice_id", "id"), 200),
        documents=_documents(item, feed_url),
    )


def parse_json_feed(payload: Any, source: Source, feed_url: str) -> list["Candidate"]:
    from app.collectors.adapters import CollectionError

    items = feed_items(payload)
    if items is None:
        raise CollectionError("JSON feed did not contain a recognised list of notices")

    candidates: list["Candidate"] = []
    seen: set[str] = set()
    for item in items[:MAX_ITEMS]:
        candidate = _candidate_from_item(item, source, feed_url)
        if candidate is None:
            continue
        key = candidate.url or f"{candidate.title}|{candidate.organization_name}"
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


def _page_url(url: str, page: int) -> str:
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "page"]
    query.append(("page", str(page)))
    return urlunparse(parsed._replace(query=urlencode(query)))


def _pagination(payload: Any) -> tuple[int, int] | None:
    """Read ``total``/``page_size`` when the feed reports its page count."""
    if not isinstance(payload, dict):
        return None
    total = payload.get("total")
    size = payload.get("page_size") or payload.get("per_page") or payload.get("limit")
    if not isinstance(total, int) or total <= 0 or not isinstance(size, int) or size <= 0:
        return None
    return total, size


def collect_json_source(source: Source, fetcher: "HttpFetcher") -> "SourceCollectionResult":
    from app.collectors.adapters import CollectionError, SourceCollectionResult

    started = time.monotonic()
    assert source.tender_page_url  # guarded by the caller
    max_pages = max(1, settings.collector_max_pages_per_source)
    url: str | None = source.tender_page_url
    candidates: list["Candidate"] = []
    seen: set[str] = set()
    pagination: tuple[int, int] | None = None
    pages_fetched = 0
    last_status: int | None = None

    while url and pages_fetched < max_pages:
        result = fetcher.get(url, retries=1)
        last_status = result.status_code or last_status
        if result.skipped_reason in {"robots_disallowed", "host_not_allowed", "redirect_not_allowed"}:
            raise CollectionError(
                result.error or "Feed is not permitted by the access policy",
                http_status=last_status,
            )
        if not result.ok:
            if pages_fetched:
                break
            raise CollectionError(
                result.error or f"HTTP {result.status_code} from feed",
                http_status=last_status,
            )

        body = (result.text or "").strip()
        if not body:
            if pages_fetched:
                break
            raise CollectionError("JSON feed returned an empty response", http_status=last_status)
        try:
            payload = json.loads(body)
        except ValueError as exc:
            if pages_fetched:
                break
            raise CollectionError(
                f"JSON feed did not return valid JSON: {exc}"[:300],
                http_status=last_status,
            ) from exc

        pages_fetched += 1
        for candidate in parse_json_feed(payload, source, result.final_url or url):
            key = candidate.url or f"{candidate.title}|{candidate.organization_name}"
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)

        if pagination is None:
            pagination = _pagination(payload)
        if not pagination:
            break
        total, size = pagination
        if pages_fetched * size >= total or len(candidates) >= MAX_ITEMS:
            break
        url = _page_url(source.tender_page_url, pages_fetched + 1)

    return SourceCollectionResult(
        source_id=source.id,
        source_name=source.name,
        url=source.tender_page_url,
        candidates=candidates,
        pages_fetched=pages_fetched,
        http_status=last_status,
        duration_ms=int((time.monotonic() - started) * 1000),
        requests_made=fetcher.requests_made,
    )
