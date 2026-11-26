from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import CollectionRun, Source, SourceScan, Tender, TenderDocument


class FakeFetcher:
    def __init__(self):
        self.requests_made = 0


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _ppmo_source(db: Session) -> Source:
    return db.query(Source).filter(Source.slug == "ppmo-purchase-notices").one()


def test_runner_stores_candidates_and_deduplicates(monkeypatch, db):
    from app.collectors import runner
    from app.collectors.adapters import Candidate, SourceCollectionResult
    from app.services.documents import DiscoveredDocument

    source = _ppmo_source(db)
    source.active = True
    db.commit()

    deadline = datetime.now(timezone.utc) + timedelta(days=20)
    candidate = Candidate(
        title="Invitation for Bid: construction of test road section",
        url="https://ppmo.gov.np/content/990123/runner-test-notice",
        organization_name="Runner Test Office",
        notice_number="IFB-RUNNER-001/2082",
        category="Works",
        deadline=deadline,
        documents=[
            DiscoveredDocument(
                url="https://ppmo.gov.np/files/runner-test.pdf",
                label="Bid document",
                document_type="bid_document",
                file_format="PDF",
            )
        ],
    )

    def fake_collect(source_arg, fetcher):
        return SourceCollectionResult(
            source_id=source_arg.id,
            source_name=source_arg.name,
            url=source_arg.tender_page_url,
            candidates=[candidate],
            pages_fetched=1,
            http_status=200,
            duration_ms=5,
            requests_made=1,
        )

    monkeypatch.setattr(runner, "collect_source", fake_collect)
    monkeypatch.setattr(runner, "enrich_candidate", lambda candidate, fetcher: candidate)

    result = runner.run_collection(
        db, mode="source", trigger="test", source_ids=[source.id], limit=1
    )
    assert result["status"] == "completed"
    assert result["inserted"] == 1
    assert result["documents_found"] == 1

    tender = (
        db.query(Tender)
        .filter(Tender.notice_number == "IFB-RUNNER-001/2082")
        .one()
    )
    assert tender.status == "open"
    assert tender.verification_status == "pending"
    assert tender.documents[0].download_status == "unverified"
    assert tender.source_id == source.id

    run = db.get(CollectionRun, result["run_id"])
    assert run is not None and run.sources_ok == 1
    scan = db.query(SourceScan).filter(SourceScan.run_id == run.id).one()
    assert scan.status == "ok"

    # The exact same notice on a second scan is linked, not duplicated.
    before = db.query(Tender).filter(Tender.notice_number == "IFB-RUNNER-001/2082").count()
    result2 = runner.run_collection(
        db, mode="source", trigger="test", source_ids=[source.id], limit=1
    )
    after = db.query(Tender).filter(Tender.notice_number == "IFB-RUNNER-001/2082").count()
    assert before == after == 1
    assert result2["duplicates"] >= 1


def test_runner_records_failures_without_crashing(monkeypatch, db):
    from app.collectors import runner
    from app.collectors.adapters import CollectionError

    source = db.query(Source).filter(Source.slug == "department-of-roads").one()
    source.active = True
    source.consecutive_failures = 0
    db.commit()

    def failing_collect(source_arg, fetcher):
        raise CollectionError("HTTP 503 from source", http_status=503)

    monkeypatch.setattr(runner, "collect_source", failing_collect)
    result = runner.run_collection(
        db, mode="source", trigger="test", source_ids=[source.id], limit=1
    )
    assert result["status"] == "failed"
    assert result["sources_failed"] == 1
    assert result["errors"]

    db.expire_all()
    refreshed = db.query(Source).filter(Source.id == source.id).one()
    assert refreshed.consecutive_failures >= 1
    assert "503" in (refreshed.last_error or "")
    assert refreshed.discovery_status == "inaccessible"

    failed_scan = (
        db.query(SourceScan)
        .filter(SourceScan.run_id == result["run_id"])
        .filter(SourceScan.status == "error")
        .one()
    )
    assert "503" in (failed_scan.error or "")
    db.query(Source).filter(Source.id == source.id).update(
        {Source.consecutive_failures: 0, Source.discovery_status: "discovered"}
    )
    db.commit()


def test_duplicate_detection_is_conservative(db):
    from app.services.duplicates import find_duplicate

    deadline = datetime(2031, 5, 20, 12, tzinfo=timezone.utc)
    original = Tender(
        title="Supply and delivery of office furniture for municipality",
        organization_name="Dedupe Test Municipality",
        notice_number="GOODS-DEDUPE-01/2082",
        category="Goods",
        deadline=deadline,
        published_date=datetime(2031, 5, 1, tzinfo=timezone.utc),
        source_name="Dedupe Test Municipality",
        source_url="https://dedupetestmun.gov.np/tender/1",
        status="open",
        verification_status="verified",
    )
    db.add(original)
    db.commit()
    db.refresh(original)

    same_url = find_duplicate(
        db,
        source_url="https://dedupetestmun.gov.np/tender/1?utm_source=facebook",
        notice_number=None,
        title="Completely different wording",
        organization_name="Another office",
    )
    assert same_url is not None and same_url.reason == "canonical_source_url"

    same_number = find_duplicate(
        db,
        source_url="https://other.gov.np/notice/xyz",
        notice_number="GOODS-DEDUPE-01/2082",
        title="Supply and delivery of office furniture",
        organization_name="Dedupe Test Municipality",
    )
    assert same_number is not None and same_number.reason == "notice_number"

    different_org_similar_title = find_duplicate(
        db,
        source_url="https://another.gov.np/notice/abc",
        notice_number=None,
        title="Supply and delivery of office furniture for municipality",
        organization_name="Different Municipality",
        deadline=deadline,
        published_date=datetime(2031, 5, 1, tzinfo=timezone.utc),
    )
    assert different_org_similar_title is None

    similar_with_other_deadline = find_duplicate(
        db,
        source_url="https://another.gov.np/notice/def",
        notice_number=None,
        title="Supply and delivery of office furniture for municipality",
        organization_name="Dedupe Test Municipality",
        deadline=datetime(2032, 9, 2, tzinfo=timezone.utc),
        published_date=datetime(2032, 8, 2, tzinfo=timezone.utc),
    )
    assert similar_with_other_deadline is None


def test_duplicate_groups_surface_notice_numbers(db):
    from app.services.duplicates import search_duplicate_groups

    for index in (1, 2):
        db.add(
            Tender(
                title=f"Bridge works notice copy {index}",
                organization_name="Group Test Office",
                notice_number="GROUP-TEST-77/2082",
                source_name=f"Source {index}",
                                    source_url=f"https://group{index}.gov.np/notice",
                verification_status="pending",
                status="open",
            )
        )
    db.commit()
    groups = search_duplicate_groups(db)
    assert any(group["notice_number"] == "GROUP-TEST-77/2082" and len(group["tenders"]) == 2 for group in groups)
