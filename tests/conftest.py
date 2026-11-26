"""Test configuration.

Environment is set before importing the application so the engine, scheduler and
admin seeding all use an isolated SQLite database. No outbound network calls are
made by the tests: the collector is disabled and HTTP probes are off.
"""
from __future__ import annotations

import os
import pathlib

os.environ["DATABASE_URL"] = "sqlite:///./test_bidders.db"
os.environ["JWT_SECRET"] = "test-secret-key-not-for-production"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "TestPassword123"
os.environ["ENABLE_TENDER_COLLECTOR"] = "false"
os.environ["TENDER_PROBE_DOCUMENTS"] = "false"
os.environ["TENDER_LOCAL_DISCOVERY"] = "false"
os.environ["TENDER_DETAIL_FETCH_LIMIT"] = "0"
os.environ["ADMIN_COOKIE_SECURE"] = "false"

DB_PATH = pathlib.Path("test_bidders.db")
if DB_PATH.exists():
    DB_PATH.unlink()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    if DB_PATH.exists():
        DB_PATH.unlink()


@pytest.fixture(scope="session")
def admin_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "TestPassword123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def seeded_tenders(client, admin_headers):
    created = []
    payloads = [
        {
            "title": "Construction of rural road in Kanchanpur",
            "organization_name": "Krishnapur Municipality",
            "category": "Works",
            "province": "Sudurpashchim",
            "district": "Kanchanpur",
            "municipality": "Krishnapur Municipality",
            "deadline": "2030-01-15T12:00:00+00:00",
            "source_name": "Krishnapur Municipality",
            "source_url": "https://krishnapurmun.gov.np/tender/1",
        },
        {
            "title": "Supply of medical equipment for district hospital",
            "organization_name": "District Health Office",
            "category": "Goods",
            "province": "Bagmati",
            "district": "Kathmandu",
            "deadline": "2029-12-20T12:00:00+00:00",
            "source_name": "PPMO purchase notices",
            "source_url": "https://ppmo.gov.np/content/99001/medical-equipment",
        },
        {
            "title": "Consultancy for water supply feasibility study",
            "organization_name": "Department of Water Supply",
            "category": "Consultancy",
            "province": "Gandaki",
            "district": "Kaski",
            "deadline": "2029-11-30T12:00:00+00:00",
            "source_name": "Department of Water Supply",
            "source_url": "https://dwssm.gov.np/notice/feasibility",
        },
    ]
    for payload in payloads:
        response = client.post("/api/v1/admin/tenders", json=payload, headers=admin_headers)
        assert response.status_code == 201, response.text
        created.append(response.json())
    # Verify the first two so the strict feed has data.
    for tender in created[:2]:
        response = client.post(
            f"/api/v1/admin/tenders/{tender['id']}/verify?decision=verified",
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
    return created
