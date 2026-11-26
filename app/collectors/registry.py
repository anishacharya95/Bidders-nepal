"""Source registry: official procurement publishers and all 753 local governments.

The local-government directory is loaded from a bundled dataset of names,
districts and provinces (source and licence recorded in the JSON file). A local
government is only treated as connected once a website/tender page has been
discovered and successfully scanned; directory entries alone are not coverage.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Source

log = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "local_governments.json"

LG_TYPES = {
    "Metropolitan City": "metropolitan_city",
    "Sub-Metropolitan City": "sub_metropolitan_city",
    "Municipality": "municipality",
    "Rural Municipality": "rural_municipality",
}
LG_SOURCE_TYPES = set(LG_TYPES.values())


@dataclass(frozen=True)
class SourceSpec:
    slug: str
    name: str
    name_ne: str | None
    organization_name: str
    source_type: str
    level: str
    province: str | None
    district: str | None
    website: str | None
    tender_page_url: str | None
    collector_key: str
    priority: int
    discovery_status: str = "discovered"
    requires_authorization: bool = False
    active: bool = True
    notes: str | None = None


CENTRAL_SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        "ppmo-purchase-notices", "PPMO purchase notices", "पीपीएमओ खरिद सूचना",
        "Public Procurement Monitoring Office (PPMO)", "central_agency", "central",
        None, None, "https://ppmo.gov.np/", "https://ppmo.gov.np/category/purchase-notice/",
        "ppmo", 1,
        notes="National procurement monitoring office public notice category.",
    ),
    SourceSpec(
        "ppmo-bid-notices", "PPMO bid notices", "पीपीएमओ बोलपत्र सूचना",
        "Public Procurement Monitoring Office (PPMO)", "central_agency", "central",
        None, None, "https://ppmo.gov.np/", "https://ppmo.gov.np/category/bid-notice/",
        "ppmo", 1,
        notes="PPMO bid notice category; individual notices stay pending review.",
    ),
    SourceSpec(
        "nea-prequalification", "Nepal Electricity Authority tenders", "नेपाल विद्युत प्राधिकरण",
        "Nepal Electricity Authority", "utility", "central",
        None, None, "https://www.nea.org.np/", "https://www.nea.org.np/en/tender/prequalification",
        "nea", 1,
        notes="Utility procurement and prequalification listings.",
    ),
    SourceSpec(
        "department-of-roads", "Department of Roads", "सडक विभाग",
        "Department of Roads", "department", "central",
        None, None, "https://www.dor.gov.np/", "https://www.dor.gov.np/dorfcb",
        "generic_html", 1,
        notes="Road and bridge procurement notices.",
    ),
    SourceSpec(
        "department-of-local-infrastructure", "Department of Local Infrastructure", "स्थानीय पूर्वाधार विभाग",
        "Department of Local Infrastructure (DoLI)", "department", "central",
        None, None, "https://www.doli.gov.np/", "https://www.doli.gov.np/",
        "generic_html", 2,
        notes="Local infrastructure programme notices.",
    ),
    SourceSpec(
        "dudbc", "Department of Urban Development & Building Construction", "शहरी विकास तथा भवन निर्माण विभाग",
        "Department of Urban Development and Building Construction (DUDBC)", "department", "central",
        None, None, "https://dudbc.gov.np/", "https://dudbc.gov.np/",
        "generic_html", 2,
    ),
    SourceSpec(
        "dwssm", "Department of Water Supply & Sewerage Management", "खानेपानी तथा ढल व्यवस्थापन विभाग",
        "Department of Water Supply and Sewerage Management (DWSSM)", "department", "central",
        None, None, "https://dwssm.gov.np/", "https://dwssm.gov.np/category/tender-notice/",
        "generic_html", 2,
    ),
    SourceSpec(
        "dwri", "Department of Water Resources & Irrigation", "जलस्रोत तथा सिँचाइ विभाग",
        "Department of Water Resources and Irrigation (DWRI)", "department", "central",
        None, None, "https://dwri.gov.np/", "https://dwri.gov.np/",
        "generic_html", 2,
    ),
    SourceSpec(
        "caan", "Civil Aviation Authority of Nepal", "नेपाल नागरिक उड्डयन प्राधिकरण",
        "Civil Aviation Authority of Nepal (CAAN)", "agency", "central",
        None, None, "https://caanepal.gov.np/", "https://caanepal.gov.np/",
        "generic_html", 2,
        notes="Website reachability is re-checked on every scan.",
    ),
    SourceSpec(
        "mofaga", "Ministry of Federal Affairs & General Administration", "संघीय मामिला तथा सामान्य प्रशासन मन्त्रालय",
        "Ministry of Federal Affairs and General Administration (MoFAGA)", "ministry", "central",
        None, None, "https://www.mofaga.gov.np/", "https://www.mofaga.gov.np/",
        "generic_html", 2,
        notes="Also publishes the national local-government website directory.",
    ),
    SourceSpec(
        "koshi-province", "Koshi Province government", "कोशी प्रदेश",
        "Koshi Province Government", "provincial", "provincial",
        "Koshi", None, "https://koshi.gov.np/", "https://koshi.gov.np/",
        "generic_html", 2,
    ),
    SourceSpec(
        "madhesh-province", "Madhesh Province government", "मधेश प्रदेश",
        "Madhesh Province Government", "provincial", "provincial",
        "Madhesh", None, None, None,
        "generic_html", 3, discovery_status="unregistered",
        notes="Provincial portal URL not yet verified; discovery required.",
    ),
    SourceSpec(
        "bagmati-province", "Bagmati Province government", "बागमती प्रदेश",
        "Bagmati Province Government", "provincial", "provincial",
        "Bagmati", None, None, None,
        "generic_html", 3, discovery_status="unregistered",
        notes="Provincial portal URL not yet verified; discovery required.",
    ),
    SourceSpec(
        "gandaki-province", "Gandaki Province government", "गण्डकी प्रदेश",
        "Gandaki Province Government", "provincial", "provincial",
        "Gandaki", None, None, None,
        "generic_html", 3, discovery_status="unregistered",
        notes="Provincial portal URL not yet verified; discovery required.",
    ),
    SourceSpec(
        "lumbini-province", "Lumbini Province government", "लुम्बिनी प्रदेश",
        "Lumbini Province Government", "provincial", "provincial",
        "Lumbini", None, None, None,
        "generic_html", 3, discovery_status="unregistered",
        notes="Provincial portal URL not yet verified; discovery required.",
    ),
    SourceSpec(
        "karnali-province", "Karnali Province government", "कर्णाली प्रदेश",
        "Karnali Province Government", "provincial", "provincial",
        "Karnali", None, None, None,
        "generic_html", 3, discovery_status="unregistered",
        notes="Provincial portal URL not yet verified; discovery required.",
    ),
    SourceSpec(
        "sudurpashchim-province", "Sudurpashchim Province government", "सुदूरपश्चिम प्रदेश",
        "Sudurpashchim Province Government", "provincial", "provincial",
        "Sudurpashchim", None, None, None,
        "generic_html", 3, discovery_status="unregistered",
        notes="Provincial portal URL not yet verified; discovery required.",
    ),
    SourceSpec(
        "bolpatra-egp", "Nepal e-GP (Bolpatra)", "नेपाल सरकार इ-जीपी",
        "Public Procurement Monitoring Office (PPMO)", "egp_portal", "central",
        None, None, "https://bolpatra.gov.np/", "https://bolpatra.gov.np/projects",
        "bolpatra_egp", 1, discovery_status="discovered",
        requires_authorization=False, active=True,
        notes=(
            "Official public e-GP listing. The portal is a JavaScript app that loads notices "
            "from its own /api endpoints, and robots.txt disallows /api, so no notice is "
            "currently collected from this source without the publisher's permission. "
            "Bidder login and restricted bid actions are never accessed."
        ),
    ),
    SourceSpec(
        "bolpatranepal-com", "Bolpatra Nepal (third-party portal)", "बोलपत्र नेपाल",
        "Bolpatra Nepal (third-party)", "third_party", "central",
        None, None, "https://bolpatranepal.com/", None,
        "manual", 4, discovery_status="requires_authorization",
        requires_authorization=True, active=False,
        notes="Independent commercial portal, not a government publisher. Collection requires written permission.",
    ),
)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return cleaned or "source"


@lru_cache(maxsize=1)
def load_local_governments() -> dict:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def local_government_specs() -> list[SourceSpec]:
    payload = load_local_governments()
    specs: list[SourceSpec] = []
    for index, row in enumerate(payload["local_governments"], start=1):
        source_type = LG_TYPES[row["type"]]
        suffix = {
            "Metropolitan City": "Metropolitan City",
            "Sub-Metropolitan City": "Sub-Metropolitan City",
            "Municipality": "Municipality",
            "Rural Municipality": "Rural Municipality",
        }[row["type"]]
        display = f"{row['name_en']} {suffix}"
        name_ne = f"{row['name_ne'].strip(' ।')} {row['type_ne']}"
        slug = _slug(f"lg-{row['province']}-{row['district']}-{row['name_en']}-{index}")
        priority = 2 if source_type == "metropolitan_city" else 3 if source_type == "sub_metropolitan_city" else 4 if source_type == "municipality" else 5
        specs.append(
            SourceSpec(
                slug=slug,
                name=display,
                name_ne=name_ne,
                organization_name=display,
                source_type=source_type,
                level="local",
                province=row["province"],
                district=row["district"],
                website=None,
                tender_page_url=None,
                collector_key="generic_html",
                priority=priority,
                discovery_status="unregistered",
                active=True,
                notes="Official local government; website discovery pending.",
            )
        )
    return specs


def all_specs() -> list[SourceSpec]:
    return list(CENTRAL_SOURCES) + local_government_specs()


def sync_registry(db: Session) -> dict:
    """Insert missing sources; never overwrite admin-edited URLs or health."""
    specs = all_specs()
    existing = {row.slug: row for row in db.query(Source).all()}
    created = updated = 0
    for spec in specs:
        current = existing.get(spec.slug)
        if current is None:
            db.add(
                Source(
                    slug=spec.slug,
                    name=spec.name,
                    name_ne=spec.name_ne,
                    organization_name=spec.organization_name,
                    source_type=spec.source_type,
                    level=spec.level,
                    province=spec.province,
                    district=spec.district,
                    municipality=spec.name if spec.level == "local" else None,
                    official_website=spec.website,
                    tender_page_url=spec.tender_page_url,
                    collector_key=spec.collector_key,
                    discovery_status=spec.discovery_status,
                    requires_authorization=spec.requires_authorization,
                    active=spec.active,
                    priority=spec.priority,
                    notes=spec.notes,
                )
            )
            created += 1
            continue
        # The official e-GP public projects page was previously registered as
        # inactive/manual. Keep this narrowly scoped migration so existing
        # production rows receive the verified public listing URL and shared
        # collector configuration without changing admin-managed source URLs.
        if spec.slug == "bolpatra-egp":
            current.name = spec.name
            current.organization_name = spec.organization_name
            current.official_website = spec.website
            current.tender_page_url = spec.tender_page_url
            current.collector_key = spec.collector_key
            current.discovery_status = spec.discovery_status
            current.requires_authorization = spec.requires_authorization
            current.active = spec.active
            current.priority = spec.priority
            current.notes = spec.notes
            updated += 1
        elif spec.notes and not current.notes:
            current.notes = spec.notes
            updated += 1
    db.commit()
    return {"total": len(specs), "created": created, "updated": updated}


def register_extra_source(db: Session, url: str) -> Source | None:
    """TENDER_SOURCE_URLS entries become ordinary government sources."""
    from app.collectors.extraction import allowed_host
    from urllib.parse import urlparse

    if not allowed_host(url):
        return None
    host = (urlparse(url).hostname or "").lower().replace("www.", "")
    slug = _slug(f"extra-{host}-{urlparse(url).path}")
    existing = db.query(Source).filter(Source.slug == slug).first()
    if existing:
        return existing
    source = Source(
        slug=slug,
        name=f"{host} notices",
        organization_name=host,
        source_type="configured",
        level="central",
        official_website=f"https://{host}/",
        tender_page_url=url,
        collector_key="generic_html",
        discovery_status="discovered",
        priority=2,
        notes="Added through TENDER_SOURCE_URLS.",
    )
    db.add(source)
    return source


def register_json_source(db: Session, url: str) -> Source | None:
    """TENDER_JSON_SOURCE_URLS entries become explicit JSON feed sources.

    The host is deliberately not checked against the government allowlist here:
    the operator typed the feed into the deployment configuration, and the
    collector only fetches hosts belonging to registered ``json_api`` sources.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        log.warning("Ignoring non-HTTPS JSON feed URL %s", url)
        return None
    host = parsed.hostname.lower().removeprefix("www.")
    slug = _slug(f"json-{host}-{parsed.path}")
    existing = db.query(Source).filter(Source.slug == slug).first()
    if existing:
        return existing
    source = Source(
        slug=slug,
        name=f"{host} JSON feed",
        organization_name=host,
        source_type="configured",
        level="central",
        official_website=f"https://{host}/",
        tender_page_url=url,
        collector_key="json_api",
        discovery_status="discovered",
        priority=2,
        notes="External JSON notice feed added through TENDER_JSON_SOURCE_URLS.",
    )
    db.add(source)
    return source


def local_directory_counts() -> dict:
    payload = load_local_governments()
    return {
        "total": payload["counts"]["total"],
        "metropolitan": payload["counts"]["metropolitan"],
        "sub_metropolitan": payload["counts"]["sub_metropolitan"],
        "municipality": payload["counts"]["municipality"],
        "rural_municipality": payload["counts"]["rural_municipality"],
        "dataset_source": payload["source"],
    }
