"""Safe CSV/XLSX tender import with flexible column names and duplicate checks."""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, time, timezone
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AuditLog, Tender, TenderDocument, User
from app.services.classification import apply_classification

MAX_ROWS = 10000
ALIASES = {
    "title": {"title", "tender title", "notice title", "project title", "project / public entity", "project/public entity", "project public entity", "project name", "project work title", "project/work title", "name of project", "work name", "procurement title", "description of procurement"},
    "organization_name": {"organization_name", "organization", "organization name", "organization / procuring entity", "organization/procuring entity", "procuring entity", "procuring entity name", "procuring public entity", "public entity", "public entity name", "procuring agency", "purchaser", "employer", "office", "agency", "buyer", "location", "procuring location"},
    "notice_number": {"notice_number", "notice no", "notice number", "ifb no", "ifb number", "ifb/reoi/eoi/pq no", "bid number", "contract no", "contract number", "reference no", "reference number"},
    "category": {"category", "procurement category", "type"},
    "province": {"province", "state"},
    "district": {"district"},
    "municipality": {"municipality", "local level", "local government"},
    "description": {"description", "details", "scope"},
    "published_date": {"published date", "published date bs", "publication date", "date published", "publish date", "text xs"},
    "deadline": {"deadline", "submission deadline", "last date", "closing date", "bid submission deadline"},
    "bid_opening_date": {"bid opening date", "opening date"},
    "estimated_budget_npr": {"estimated budget", "estimated amount", "cost estimate", "estimated cost", "budget npr"},
    "bid_security_npr": {"bid security", "bid security amount"},
    "source_name": {"source", "source name", "publisher"},
    "source_url": {"source url", "notice url", "tender url", "project link", "link", "url"},
    "document_url": {"document url", "bid document url", "download url", "document link", "bid document"},
    "contact_info": {"contact", "contact info", "email", "phone"},
    "eligibility": {"eligibility", "eligible bidders"},
}

def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()

LOOKUP = {_key(alias): field for field, aliases in ALIASES.items() for alias in aliases}

def _cell_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    raw = str(value).strip()
    if not raw:
        return None
    # The Bolpatra export includes Bikram Sambat dates as display text.
    # Keep those fields blank rather than rejecting the entire tender row.
    if re.search(r"\bBS\b", raw, flags=re.IGNORECASE):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    raw = re.sub(r"\s+AD$", "", raw, flags=re.IGNORECASE).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Keep importing the tender when a portal date is displayed only in Bikram Sambat text.\n    # Unparseable date text is left blank rather than rejecting the entire row.\n    return None

def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.]", "", str(value))
    return float(cleaned) if cleaned else None

def parse_spreadsheet(raw: bytes, filename: str) -> list[dict]:
    lower = (filename or "").lower()
    if lower.endswith(".csv"):
        text = raw.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    elif lower.endswith(".xlsx"):
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        workbook.close()
    else:
        raise ValueError("Please upload an .xlsx or .csv file.")
    if not rows:
        raise ValueError("The spreadsheet is empty.")
    # Bolpatra exports may have a report title or blank rows above the headers.
    header_index = None
    mapped = []
    for candidate_index, candidate in enumerate(rows[:10]):
        candidate_headers = [_key(value) for value in candidate]
        candidate_mapping = [LOOKUP.get(header) for header in candidate_headers]
        if "title" in candidate_mapping and "organization_name" in candidate_mapping:
            header_index = candidate_index
            mapped = candidate_mapping
            break
    if header_index is None:
        raise ValueError("Could not identify the header row. Include Project/Work Title and Procuring Entity/Public Entity (or Tender Title and Organization).")
    result = []
    for line_number, cells in enumerate(rows[header_index + 1:], start=header_index + 2):
        if not any(value not in (None, "") for value in cells):
            continue
        item = {}
        for index, field in enumerate(mapped):
            if field and index < len(cells) and cells[index] not in (None, ""):
                item[field] = cells[index]
        item["_row"] = line_number
        result.append(item)
        if len(result) > MAX_ROWS:
            raise ValueError(f"Maximum {MAX_ROWS:,} rows per upload.")
    return result

def import_tender_rows(db: Session, admin: User, rows: list[dict]) -> dict:
    added = skipped = updated = 0
    errors = []
    for item in rows:
        row_number = item.get("_row", "?")
        title = str(item.get("title") or "").strip()
        organization = str(item.get("organization_name") or "").strip()
        # Bolpatra export has a combined procuring-entity/location column.
        # Keep its full value and infer district only from a final comma segment.
        if not item.get("district") and organization:
            location_parts = [part.strip() for part in organization.split(",") if part.strip()]
            if len(location_parts) >= 3:
                item["district"] = location_parts[-1]
        if len(title) < 5 or len(organization) < 2:
            skipped += 1
            errors.append({"row": row_number, "reason": "Missing or invalid title/organization"})
            continue
        notice = str(item.get("notice_number") or "").strip() or None
        source_url = str(item.get("source_url") or "").strip() or None
        query = db.query(Tender)
        existing = None
        if notice:
            existing = query.filter(func.lower(Tender.notice_number) == notice.lower()).first()
        if not existing and source_url:
            existing = query.filter(Tender.source_url == source_url).first()
        if not existing:
            existing = query.filter(
                func.lower(Tender.title) == title.lower(),
                func.lower(Tender.organization_name) == organization.lower(),
            ).first()
        try:
            dates = {key: _cell_date(item.get(key)) for key in ("published_date", "deadline", "bid_opening_date")}
            numbers = {key: _number(item.get(key)) for key in ("estimated_budget_npr", "bid_security_npr")}
            if existing:
                # Only fill blanks; imports never overwrite reviewed/manual data.
                for key, value in {**dates, **numbers}.items():
                    if getattr(existing, key) is None and value is not None:
                        setattr(existing, key, value)
                if not existing.document_url and item.get("document_url"):
                    existing.document_url = str(item["document_url"]).strip()[:1500]
                if not existing.description and item.get("description"):
                    existing.description = str(item["description"]).strip()[:10000]
                updated += 1
                continue
            tender = Tender(
                title=title[:500],
                organization_name=organization[:300],
                notice_number=notice[:150] if notice else None,
                category=str(item.get("category") or "Other").strip().title()[:40],
                province=str(item.get("province") or "").strip()[:100] or None,
                district=str(item.get("district") or "").strip()[:100] or None,
                municipality=str(item.get("municipality") or "").strip()[:120] or None,
                description=str(item.get("description") or "").strip()[:10000] or None,
                published_date=dates["published_date"],
                deadline=dates["deadline"],
                bid_opening_date=dates["bid_opening_date"],
                estimated_budget_npr=numbers["estimated_budget_npr"],
                bid_security_npr=numbers["bid_security_npr"],
                eligibility=str(item.get("eligibility") or "").strip()[:5000] or None,
                contact_info=str(item.get("contact_info") or "").strip()[:1000] or None,
                source_name=str(item.get("source_name") or "Excel/CSV import").strip()[:200],
                source_url=source_url[:1500] if source_url else None,
                document_url=str(item.get("document_url") or "").strip()[:1500] or None,
                created_by=admin.id,
                verification_status="pending",
                status="open",
            )
            apply_classification(tender)
            db.add(tender)
            db.flush()
            if tender.document_url:
                db.add(TenderDocument(
                    tender_id=tender.id,
                    label="Bid document",
                    url=tender.document_url,
                    document_type="bid_document",
                    source_url=tender.source_url,
                    is_public=True,
                ))
            added += 1
        except (TypeError, ValueError) as exc:
            skipped += 1
            errors.append({"row": row_number, "reason": str(exc)[:200]})
    db.add(AuditLog(
        actor_user_id=admin.id,
        action="spreadsheet_import",
        details=f"added={added}; updated={updated}; skipped={skipped}",
    ))
    db.commit()
    return {
        "success": True,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:100],
        "message": "Imported tenders are pending admin verification. Existing records are not overwritten.",
    }
