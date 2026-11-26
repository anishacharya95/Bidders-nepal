from __future__ import annotations

import pytest

from app.collectors.extraction import (
    category_from_text,
    extract_bid_security,
    extract_budget,
    notice_type_from_text,
    parse_deadline,
)
from app.collectors.registry import (
    all_specs,
    local_directory_counts,
    local_government_specs,
)
from app.services.documents import classify_document, documents_from_soup, file_format


def test_local_directory_has_all_753_units():
    counts = local_directory_counts()
    assert counts["total"] == 753
    assert counts["metropolitan"] == 6
    assert counts["sub_metropolitan"] == 11
    assert counts["municipality"] == 276
    assert counts["rural_municipality"] == 460
    specs = local_government_specs()
    assert len(specs) == 753
    by_type = {}
    for spec in specs:
        by_type[spec.source_type] = by_type.get(spec.source_type, 0) + 1
    assert by_type["metropolitan_city"] == 6
    assert by_type["sub_metropolitan_city"] == 11
    assert by_type["municipality"] == 276
    assert by_type["rural_municipality"] == 460
    assert len({spec.slug for spec in specs}) == 753


def test_directory_entries_are_not_marked_connected():
    for spec in local_government_specs():
        assert spec.discovery_status == "unregistered"
        assert spec.website is None
        assert spec.tender_page_url is None


def test_registry_contains_national_sources_and_authorization_records():
    specs = all_specs()
    slugs = {spec.slug for spec in specs}
    assert "ppmo-purchase-notices" in slugs
    assert "nea-prequalification" in slugs
    assert "department-of-roads" in slugs
    assert "bolpatra-egp" in slugs
    assert "bolpatranepal-com" in slugs
    authorized = [spec for spec in specs if spec.requires_authorization]
    assert {spec.slug for spec in authorized} == {"bolpatra-egp", "bolpatranepal-com"}
    assert all(not spec.active for spec in authorized)
    assert len(specs) == 753 + 19


def test_budget_and_security_extraction():
    text = "Estimated cost: NPR 12,500,000.00 Bid security: Rs. 250,000"
    assert extract_budget(text) == 12500000.00
    assert extract_bid_security(text) == 250000.0


def test_notice_type_and_category():
    assert notice_type_from_text("Invitation for Bids for road construction") == "tender_notice"
    assert notice_type_from_text("Amendment notice to tender NEA-01") == "amendment"
    assert notice_type_from_text("Deadline extension for bid submission") == "deadline_extension"
    assert notice_type_from_text("Request for Expression of Interest (EOI)") == "eoi"
    assert category_from_text("Supply of office furniture") == "Goods"
    assert category_from_text("Consultancy service for design") == "Consultancy"


def test_deadline_parsing_variants():
    assert parse_deadline("Submission deadline: 2026-12-15").year == 2026
    assert parse_deadline("Last date 15 December 2026").month == 12
    assert parse_deadline("no date here") is None


def test_documents_are_limited_to_public_government_hosts():
    html = """
    <html><body>
      <a href="/files/bid-document.pdf">Bid document</a>
      <a href="https://ppmo.gov.np/files/boq.xlsx">BOQ</a>
      <a href="https://example.com/files/private.pdf">Private mirror</a>
      <a href="https://ppmo.gov.np/content/123">Notice page</a>
      <a href="https://ppmo.gov.np/files/terms.docx">Terms</a>
    </body></html>
    """
    from bs4 import BeautifulSoup

    docs = documents_from_soup(BeautifulSoup(html, "html.parser"), "https://ppmo.gov.np/notices")
    urls = {doc.url for doc in docs}
    assert "https://ppmo.gov.np/files/bid-document.pdf" in urls
    assert "https://ppmo.gov.np/files/boq.xlsx" in urls
    assert "https://ppmo.gov.np/files/terms.docx" in urls
    assert all("example.com" not in url for url in urls)
    assert all("content/123" not in url for url in urls)
    formats = {doc.url: doc.file_format for doc in docs}
    assert formats["https://ppmo.gov.np/files/boq.xlsx"] == "XLSX"


def test_document_classification():
    assert classify_document("Bill of quantities", "https://ppmo.gov.np/a.pdf") == "boq"
    assert classify_document("Addendum 2", "https://ppmo.gov.np/b.pdf") == "addendum"
    assert classify_document("Bid document", "https://ppmo.gov.np/c.pdf") == "bid_document"
    assert classify_document("Photo", "https://ppmo.gov.np/d.jpg") == "attachment"
    assert file_format("https://ppmo.gov.np/x.PDF?download=1") == "PDF"


def test_http_policy_rejects_non_government_and_http_sources():
    from app.collectors.extraction import allowed_host

    assert allowed_host("https://ppmo.gov.np/notices") is True
    assert allowed_host("https://www.nea.org.np/tender") is True
    assert allowed_host("http://ppmo.gov.np/notices") is False
    assert allowed_host("https://example.com/notices") is False
