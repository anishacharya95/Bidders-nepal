"""Incremental discovery of official local-government websites.

Nothing is assumed: a candidate hostname is only stored after an HTTPS page
responds successfully and the page content mentions the local government name.
Tender pages are only stored if the site itself links to a page whose text looks
like a procurement notice listing.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.collectors.base import HttpFetcher
from app.collectors.extraction import canonical_url, normalise_space
from app.config import settings
from app.models import Source

log = logging.getLogger(__name__)

TENDER_LINK_HINTS = (
    "tender", "tenders", "procurement", "bid", "bids", "notice", "notices",
    "बोलपत्र", "खरिद", "सूचना", "निविदा",
)


def candidate_hosts(source: Source) -> list[str]:
    """Generate plausible official hosts for a local government.

    Nepali local governments use several conventions:
    ``kathmandu.gov.np``, ``lalitpurmun.gov.np``, ``pokharamun.gov.np``,
    ``dharanmun.gov.np``, ``birgunjmun.gov.np``, ``hetaudamun.gov.np``. Earlier
    versions only produced ``<name>mun.gov.np`` (wrong for metropolitan cities
    like Kathmandu) and a malformed dotted variant, which is why no local
    government website was ever verified. Every candidate is still checked for
    an HTTPS response whose content names the unit before it is stored.
    """
    base = source.organization_name or source.name
    base = re.sub(
        r"\b(Metropolitan City|Sub-Metropolitan City|Municipality|Rural Municipality)\b",
        "",
        base,
    )
    words = re.findall(r"[a-z0-9]+", base.lower())
    if not words:
        return []
    compact = "".join(words)
    first = words[0]
    # Common Nepali place-name spellings differ by a trailing vowel.
    variants = {compact, first}
    if compact.endswith("pur"):
        variants.add(compact[:-3])
    stems = sorted(variants, key=len, reverse=True)

    hosts: list[str] = []
    for stem in stems:
        if len(stem) < 4:
            continue
        hosts.extend(
            [
                f"{stem}.gov.np",
                f"{stem}mun.gov.np",
                f"{stem}rmun.gov.np",
                f"{stem}mc.gov.np",
                f"{stem}nagarpalika.gov.np",
            ]
        )
    return list(dict.fromkeys(hosts))[:12]


def _name_matches(source: Source, html: str) -> bool:
    text = normalise_space(BeautifulSoup(html, "html.parser").get_text(" ", strip=True)).lower()
    name_ne = (source.name_ne or "").split(" ")[0]
    english = (source.organization_name or source.name).lower()
    english = re.sub(
        r"\b(metropolitan city|sub-metropolitan city|municipality|rural municipality)\b", "", english
    ).strip()
    if name_ne and len(name_ne) > 1 and name_ne in (text or ""):
        return True
    return bool(english) and english in text


def discover_website(source: Source, fetcher: HttpFetcher) -> dict:
    """Try candidate hostnames for one local government and record the outcome."""
    for host in candidate_hosts(source):
        url = f"https://{host}/"
        result = fetcher.get(url, retries=0)
        if result.skipped_reason in {"robots_disallowed", "host_not_allowed"}:
            continue
        if not result.ok or not result.is_html:
            continue
        if not _name_matches(source, result.text):
            continue
        website = f"https://{(urlparse(result.final_url).hostname or host).lower()}/"
        tender_page = _find_tender_page(result.text, result.final_url)
        return {"website": website, "tender_page_url": tender_page}
    return {}


def _find_tender_page(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(page_url).hostname
    scored: list[tuple[int, str]] = []
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        target = urljoin(page_url, href)
        if urlparse(target).hostname != host:
            continue
        label = f"{anchor.get_text(' ', strip=True)} {href}".lower()
        if not any(hint in label for hint in TENDER_LINK_HINTS):
            continue
        score = 2 if any(hint in href.lower() for hint in ("tender", "procurement", "bid")) else 1
        scored.append((score, canonical_url(target)))
    if not scored:
        return None
    scored.sort(key=lambda item: -item[0])
    return scored[0][1]


def discover_local_governments(
    db: Session,
    fetcher: HttpFetcher | None = None,
    limit: int | None = None,
) -> dict:
    if not settings.local_discovery_enabled:
        return {"enabled": False, "checked": 0, "discovered": 0}
    fetcher = fetcher or HttpFetcher()
    limit = limit or settings.local_discovery_batch
    rows = (
        db.query(Source)
        .filter(Source.source_type.in_(["metropolitan_city", "sub_metropolitan_city", "municipality", "rural_municipality"]))
        .filter(Source.discovery_status.in_(["unregistered", "inaccessible"]))
        .filter(Source.official_website.is_(None))
        .order_by(Source.priority.asc(), Source.id.asc())
        .limit(limit)
        .all()
    )
    checked = discovered = 0
    now = datetime.now(timezone.utc)
    for source in rows:
        checked += 1
        try:
            found = discover_website(source, fetcher)
        except Exception as exc:  # discovery must never stop a run
            log.warning("Website discovery failed for %s: %s", source.name, exc)
            found = {}
        if found.get("website"):
            source.official_website = found["website"]
            source.tender_page_url = found.get("tender_page_url")
            source.discovery_status = "discovered" if found.get("tender_page_url") else "website_found"
            source.last_checked_at = now
            source.last_error = None
            discovered += 1
        else:
            source.discovery_status = "unregistered"
            source.last_checked_at = now
            source.last_error = "No verified HTTPS government website found among candidate domains"
        db.commit()
    return {
        "enabled": True,
        "checked": checked,
        "discovered": discovered,
        "requests": fetcher.requests_made,
        "note": "Only HTTPS sites whose content names the local government are registered.",
    }
