"""JSON notice feeds: parsing, pagination and ingestion into the normal pipeline."""
from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import Session

from app.collectors.base import FetchResult, HttpFetcher
from app.database import SessionLocal
from app.models import Source, Tender

FEED_PAYLOAD = {
    "items": [
        {
            "id": 273,
            "title": "Invitation for Bid: construction of a suspension bridge",
            "notice_number": "IFB-JSON-001/2082",
            "organization_name": "JSON Test Rural Municipality",
            "category": "Works",
            "province": "Koshi",
            "district": "Dhankuta",
            "municipality": "JSON Test Rural Municipality",
            "description": "Construction of a pedestrian suspension bridge including approach paths.",
            "published_date": "2026-11-20T00:00:00Z",
            "deadline": "2030-01-15T12:00:00Z",
            "estimated_budget_npr": 12500000,
            "notice_type": "tender_notice",
            "source_url": "https://example.gov.np/notice/273",
            "documents": [
                {
                    "label": "Bid document",
                    "url": "https://example.gov.np/files/bid-273.pdf",
                    "document_type": "bid_document",
                    "file_format": "PDF",
                }
            ],
        },
        {
            "id": 274,
            "title": "Supply of ambulance for the health post",
            "organization_name": "JSON Test Rural Municipality",
            "category": "Goods",
            "deadline": "2029-12-01",
            "source_url": "https://example.gov.np/notice/274",
            "documents": [],
        },
        {"id": 275, "source_url": "https://example.gov.np/notice/275"},
    ],
    "total": 3,
    "page": 1,
    "page_size": 100,
}


class StubFetcher:
    """Serves canned JSON bodies, keyed by the page query parameter."""

    def __init__(self, pages: dict[int, dict] | dict, status_code: int = 200):
        self.pages = pages if isinstance(pages, dict) and pages and isinstance(next(iter(pages)), int) else {1: pages}
        self.status_code = status_code
        self.requests_made = 0
        self.calls: list[str] = []

    def permitted(self, url: str) -> bool:
        return True

    def get(self, url: str, retries: int = 1, check_robots: bool = True) -> FetchResult:
        self.requests_made += 1
        self.calls.append(url)
        page = 1
        if "page=" in url:
            page = int(url.rsplit("page=", 1)[1].split("&")[0])
        payload = self.pages.get(page, self.pages[max(self.pages)])
        return FetchResult(
            url=url,
            final_url=url,
            status_code=self.status_code,
            text=json.dumps(payload),
            content_type="application/json",
        )


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def json_source(db: Session):
    source = Source(
        slug="json-feed-test-source",
        name="JSON feed test source",
        organization_name="JSON Feed Office",
        source_type="configured",
        level="central",
        official_website="https://feeds.example.org/",
        tender_page_url="https://feeds.example.org/notices.json",
        collector_key="json_api",
        discovery_status="discovered",
        active=True,
        priority=2,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    try:
        yield source
    finally:
        for tender in db.query(Tender).filter(Tender.source_id == source.id).all():
            db.delete(tender)
        db.delete(source)
        db.commit()


def test_parse_json_feed_maps_public_api_shape(json_source):
    from app.collectors.json_api import parse_json_feed

    candidates = parse_json_feed(FEED_PAYLOAD, json_source, "https://feeds.example.org/notices.json")
    # The third item has no title and is not a notice.
    assert len(candidates) == 2

    first = candidates[0]
    assert first.title.startswith("Invitation for Bid")
    assert first.organization_name == "JSON Test Rural Municipality"
    assert first.notice_number == "IFB-JSON-001/2082"
    assert first.category == "Works"
    assert first.deadline is not None and first.deadline.year == 2030
    assert first.deadline.tzinfo is not None
    assert first.published_date is not None and first.published_date.month == 11
    assert first.estimated_budget_npr == 12_500_000
    assert first.url == "https://example.gov.np/notice/273"
    assert first.documents[0].url == "https://example.gov.np/files/bid-273.pdf"
    assert first.documents[0].file_format == "PDF"

    second = candidates[1]
    assert second.deadline is not None and second.deadline.year == 2029
    assert second.notice_type == "tender_notice"


def test_feed_items_accepts_bare_and_wrapped_payloads():
    from app.collectors.json_api import feed_items

    assert feed_items([{"title": "x"}]) == [{"title": "x"}]
    assert feed_items({"data": {"items": [{"title": "x"}]}}) == [{"title": "x"}]
    assert feed_items({"total": 0}) is None


def test_collect_json_source_follows_reported_pages(json_source):
    from app.collectors.json_api import collect_json_source

    pages = {
        1: {"items": FEED_PAYLOAD["items"][:2], "total": 3, "page": 1, "page_size": 2},
        2: {"items": [FEED_PAYLOAD["items"][1], {"title": "Bridge maintenance works notice", "source_url": "https://example.gov.np/notice/300"}], "total": 3, "page": 2, "page_size": 2},
    }
    fetcher = StubFetcher(pages)
    result = collect_json_source(json_source, fetcher)

    assert result.pages_fetched == 2
    assert fetcher.requests_made == 2
    assert "page=2" in fetcher.calls[1]
    # Duplicate across pages is dropped; the new notice on page 2 is kept.
    assert len(result.candidates) == 3
    assert any(candidate.url == "https://example.gov.np/notice/300" for candidate in result.candidates)


def test_json_feed_host_permission_is_explicit():
    assert HttpFetcher(extra_hosts=["feeds.example.org"]).permitted(
        "https://feeds.example.org/notices.json"
    )
    assert not HttpFetcher().permitted("https://feeds.example.org/notices.json")
    # Feeds are still https-only.
    assert not HttpFetcher(extra_hosts=["feeds.example.org"]).permitted(
        "http://feeds.example.org/notices.json"
    )


def test_runner_ingests_json_source_end_to_end(monkeypatch, db, json_source):
    from app.collectors import runner

    payload = {
        "items": [FEED_PAYLOAD["items"][0]],
        "total": 1,
        "page": 1,
        "page_size": 100,
    }
    stub = StubFetcher(payload)
    monkeypatch.setattr(runner, "HttpFetcher", lambda **kwargs: stub)

    result = runner.run_collection(
        db, mode="source", trigger="test", source_ids=[json_source.id], limit=1
    )
    assert result["status"] == "completed", result
    assert result["sources_ok"] == 1
    assert result["inserted"] == 1
    assert result["documents_found"] == 1

    tender = (
        db.query(Tender)
        .filter(Tender.notice_number == "IFB-JSON-001/2082")
        .filter(Tender.source_id == json_source.id)
        .one()
    )
    assert tender.title.startswith("Invitation for Bid")
    assert tender.status == "open"
    assert tender.verification_status == "pending"
    assert tender.documents[0].url == "https://example.gov.np/files/bid-273.pdf"

    second = runner.run_collection(
        db, mode="source", trigger="test", source_ids=[json_source.id], limit=1
    )
    assert second["inserted"] == 0
    assert second["duplicates"] == 1
    assert (
        db.query(Tender)
        .filter(Tender.notice_number == "IFB-JSON-001/2082")
        .filter(Tender.source_id == json_source.id)
        .count()
        == 1
    )
