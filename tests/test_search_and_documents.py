from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.classification import (
    department_for,
    ministry_for,
    procurement_type_for,
)
from app.services.document_proxy import base_url_problem, host_is_public, is_previewable


def test_derived_facets_are_conservative():
    assert procurement_type_for("Works") == "Works"
    assert procurement_type_for("Goods") == "Goods"
    assert procurement_type_for("Consultancy") == "Consulting Services"
    assert procurement_type_for("Services") == "Non-consulting Services"
    assert procurement_type_for("Other") is None
    assert procurement_type_for("Other", "Non-consulting Services for audit") == "Non-consulting Services"
    # Nothing is invented when the entity name does not name a ministry.
    assert ministry_for("Ministry of Physical Infrastructure and Transport") is not None
    assert ministry_for("Krishnapur Municipality") is None
    assert department_for("Department of Roads") == "Department of Roads"
    assert department_for("Ministry of Finance") is None
    assert department_for("Krishnapur Municipality") is None


def test_search_endpoint_filters_and_sorting(client, seeded_tenders):
    body = client.get("/api/v1/search", params={"q": "road"}).json()
    assert body["total"] >= 1
    assert all("road" in item["title"].lower() for item in body["items"])
    assert body["applied_filters"]["q"] == "road"
    assert "pages" in body

    works = client.get("/api/v1/search", params={"procurement_type": "Works"}).json()
    assert works["total"] >= 1
    assert all(item["procurement_type"] == "Works" for item in works["items"])

    consultancy = client.get(
        "/api/v1/search", params={"procurement_type": "Consulting Services"}
    ).json()
    assert consultancy["total"] >= 1
    assert all(item["category"] == "Consultancy" for item in consultancy["items"])

    # Multiple filters at once.
    combined = client.get(
        "/api/v1/search",
        params={
            "procurement_type": "Works",
            "district": "Kanchanpur",
            "province": "Sudurpashchim",
            "has_documents": False,
            "status": "active",
        },
    ).json()
    assert combined["total"] >= 1
    assert all(
        item["district"] == "Kanchanpur" and item["category"] == "Works"
        for item in combined["items"]
    )

    # Notice number / source filters.
    notice = seeded_tenders[1]["notice_number"]
    if notice:
        by_number = client.get("/api/v1/search", params={"notice_number": notice}).json()
        assert any(item["id"] == seeded_tenders[1]["id"] for item in by_number["items"])

    by_source = client.get("/api/v1/search", params={"source": "PPMO"}).json()
    assert by_source["total"] >= 1

    sorted_by_org = client.get("/api/v1/search", params={"sort": "organization"}).json()
    names = [item["organization_name"] for item in sorted_by_org["items"]]
    assert names == sorted(names, key=str.lower)

    facets = client.get("/api/v1/search", params={"facets": True}).json()
    assert "facets" in facets and "procurement_types" in facets["facets"]

    options = client.get("/api/v1/filters/options").json()
    assert {"procurement_types", "sources", "ministries", "sort_options"} <= set(options)


def test_expired_and_open_status_filters(client, admin_headers, seeded_tenders):
    created = client.post(
        "/api/v1/admin/tenders",
        json={
            "title": "Expired maintenance contract for Bagmati bridge",
            "organization_name": "Ministry of Physical Infrastructure",
            "category": "Works",
            "province": "Bagmati",
            "district": "Lalitpur",
            "deadline": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
            "source_name": "Ministry of Physical Infrastructure",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    tender_id = created.json()["id"]

    expired = client.get("/api/v1/search", params={"status": "expired", "page_size": 100}).json()
    assert any(item["id"] == tender_id for item in expired["items"])

    active = client.get("/api/v1/search", params={"status": "active", "page_size": 100}).json()
    assert all(item["id"] != tender_id for item in active["items"])

    ministry = client.get(
        "/api/v1/search", params={"ministry": "Ministry of Physical Infrastructure"}
    ).json()
    assert any(item["id"] == tender_id for item in ministry["items"])


def _add_document(tender_id: int, url: str, document_type: str = "bid_document", fmt: str = "PDF"):
    from app.database import SessionLocal
    from app.models import TenderDocument

    with SessionLocal() as db:
        row = TenderDocument(
            tender_id=tender_id,
            label="Bidding document",
            url=url,
            document_type=document_type,
            file_format=fmt,
            download_status="unverified",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def test_document_listing_detail_and_viewer(client, seeded_tenders):
    tender_id = seeded_tenders[0]["id"]
    document_id = _add_document(tender_id, "https://ppmo.gov.np/uploads/bid-document.pdf")

    listing = client.get(f"/api/v1/tenders/{tender_id}/documents").json()
    assert listing["count"] >= 1
    item = next(doc for doc in listing["items"] if doc["id"] == document_id)
    assert item["preview_url"].endswith(f"/api/v1/documents/{document_id}/preview")
    assert item["viewer_url"].endswith(f"/api/v1/documents/{document_id}/viewer")
    assert item["availability"] == "unverified"

    detail = client.get(f"/api/v1/documents/{document_id}").json()
    assert detail["tender_id"] == tender_id
    assert detail["previewable"] is True
    assert detail["original_url"] == "https://ppmo.gov.np/uploads/bid-document.pdf"

    status_body = client.get(f"/api/v1/documents/{document_id}/status").json()
    assert status_body["availability"] == "unverified"
    assert status_body["checked_count"] in (0, None) or status_body["checked_count"] >= 0

    viewer = client.get(f"/api/v1/documents/{document_id}/viewer")
    assert viewer.status_code == 200
    assert "text/html" in viewer.headers["content-type"]
    assert "pdfjs" in viewer.text

    recent = client.get("/api/v1/documents").json()
    assert any(doc["id"] == document_id for doc in recent["items"])

    missing = client.get("/api/v1/documents/999999")
    assert missing.status_code == 404


def test_document_stream_rejects_unsafe_and_unapproved_urls(client, seeded_tenders):
    tender_id = seeded_tenders[0]["id"]
    # A loopback URL must never be fetched by the streaming proxy (SSRF guard).
    unsafe_id = _add_document(tender_id, "https://127.0.0.1/internal.pdf")
    preview = client.get(f"/api/v1/documents/{unsafe_id}/preview")
    assert preview.status_code == 409
    assert "approved public source" in preview.json()["detail"]

    check = client.post(f"/api/v1/documents/{unsafe_id}/check").json()
    assert check["availability"] == "restricted"
    assert check["is_available"] is False

    download = client.get(f"/api/v1/documents/{unsafe_id}/download")
    assert download.status_code == 409

    # Plain HTTP is refused as well.
    plain_id = _add_document(tender_id, "http://ppmo.gov.np/bid.pdf")
    assert client.get(f"/api/v1/documents/{plain_id}/preview").status_code == 409

    # Non-PDF formats are not sent to the PDF viewer.
    docx_id = _add_document(tender_id, "https://ppmo.gov.np/bid.docx", fmt="DOCX")
    assert client.get(f"/api/v1/documents/{docx_id}/viewer").status_code == 415


def test_proxy_url_guards():
    assert base_url_problem("http://example.com/a.pdf") is not None
    assert base_url_problem("https://user:pass@example.com/a.pdf") is not None
    assert base_url_problem("https://example.com:22/a.pdf") is not None
    assert base_url_problem("https://example.com/a.pdf") is None
    assert host_is_public("127.0.0.1")[0] is False
    assert host_is_public("10.0.0.5")[0] is False
    assert is_previewable("application/pdf", "PDF") is True
    assert is_previewable("application/vnd.ms-excel", "XLS") is False
