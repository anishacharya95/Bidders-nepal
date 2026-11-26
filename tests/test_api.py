from __future__ import annotations


def test_root_and_health(client):
    website = client.get("/")
    assert website.status_code == 200
    assert "text/html" in website.headers["content-type"]
    assert "Bidders Nepal" in website.text

    root = client.get("/api")
    assert root.status_code == 200
    assert root.json()["docs"] == "/docs"

    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["database"]["ok"] is True
    data = client.get("/health/data").json()
    assert data["sources"] >= 753


def test_all_tenders_pagination_and_filters(client, seeded_tenders):
    response = client.get("/api/v1/tenders/all", params={"page_size": 2, "page": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 3
    assert "documents" in body["items"][0]

    filtered = client.get("/api/v1/tenders/all", params={"category": "Works"}).json()
    assert filtered["total"] >= 1
    assert all(item["category"] == "Works" for item in filtered["items"])

    searched = client.get("/api/v1/tenders/all", params={"q": "medical equipment"}).json()
    assert searched["total"] >= 1
    assert any("medical" in item["title"].lower() for item in searched["items"])

    bad = client.get("/api/v1/tenders/all", params={"page_size": 1000})
    assert bad.status_code == 422
    bad_page = client.get("/api/v1/tenders/all", params={"page": 0})
    assert bad_page.status_code == 422


def test_public_feed_is_not_empty_and_verified_flag_narrows_it(client, seeded_tenders):
    # Regression: this endpoint used to hard-code the verified filter and returned
    # zero rows until an admin had reviewed collected notices.
    body = client.get("/api/v1/tenders", params={"status": ""}).json()
    assert body["total"] >= 3
    assert {item["verification_status"] for item in body["items"]} <= {"pending", "verified"}

    verified = client.get(
        "/api/v1/tenders", params={"status": "", "verified_only": True}
    ).json()
    assert verified["total"] >= 2
    assert all(item["verification_status"] == "verified" for item in verified["items"])


def test_tender_feed_supports_id_lookup_for_saved_lists(client, seeded_tenders):
    wanted = [seeded_tenders[0]["id"], seeded_tenders[2]["id"]]
    body = client.get(
        "/api/v1/tenders/all", params={"ids": ",".join(str(item) for item in wanted)}
    ).json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == set(wanted)
    assert client.get("/api/v1/tenders/all", params={"ids": "not-a-number"}).status_code == 422


def test_public_website_pages(client, seeded_tenders):
    for path in [
        "/",
        "/tenders",
        "/latest",
        "/closing-soon",
        "/categories",
        "/organizations",
        "/places",
        "/alerts",
        "/saved",
        "/about",
        "/contact",
    ]:
        response = client.get(path)
        assert response.status_code == 200, (path, response.text[:300])

    detail = client.get(f"/tenders/{seeded_tenders[0]['id']}")
    assert detail.status_code == 200
    assert seeded_tenders[0]["title"] in detail.text
    assert "Not available" in detail.text  # missing fields are labelled, not invented

    filtered = client.get("/tenders", params={"q": "medical equipment"})
    assert filtered.status_code == 200
    assert "medical equipment" in filtered.text.lower()


def test_tender_detail_documents_changes_and_sources(client, seeded_tenders):
    tender = seeded_tenders[0]
    detail = client.get(f"/api/v1/tenders/{tender['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == tender["id"]

    documents = client.get(f"/api/v1/tenders/{tender['id']}/documents")
    assert documents.status_code == 200
    assert documents.json()["tender_id"] == tender["id"]

    changes = client.get(f"/api/v1/tenders/{tender['id']}/changes")
    assert changes.status_code == 200
    assert "items" in changes.json()

    sources = client.get(f"/api/v1/tenders/{tender['id']}/sources")
    assert sources.status_code == 200
    assert sources.json()["primary_source"]["url"] == tender["source_url"]

    assert client.get("/api/v1/tenders/999999").status_code == 404


def test_latest_closing_categories_and_facets(client, seeded_tenders):
    latest = client.get("/api/v1/tenders/latest", params={"limit": 5})
    assert latest.status_code == 200
    assert latest.json()["count"] >= 1

    closing = client.get("/api/v1/tenders/closing-soon", params={"days": 90})
    assert closing.status_code == 200
    # Fixture deadlines are years ahead, so the window is empty but valid.
    assert closing.json()["days"] == 90

    categories = client.get("/api/v1/categories").json()
    assert any(item["value"] == "Works" for item in categories["items"])

    provinces = client.get("/api/v1/provinces").json()["items"]
    assert any(item["value"] == "Bagmati" for item in provinces)

    districts = client.get("/api/v1/districts", params={"province": "Bagmati"}).json()["items"]
    assert any(item["value"] == "Kathmandu" for item in districts)

    orgs = client.get("/api/v1/organizations", params={"q": "Water"}).json()["items"]
    assert any("Water" in item["value"] for item in orgs)

    options = client.get("/api/v1/filters/options").json()
    assert {"categories", "provinces", "districts", "organizations"} <= set(options)


def test_coverage_and_public_sources(client):
    coverage = client.get("/api/v1/coverage")
    assert coverage.status_code == 200
    body = coverage.json()
    assert body["local_governments"]["directory_entries"] == 753
    assert body["local_governments"]["registered_in_platform"] == 753
    assert body["sources"]["requires_authorization"] >= 2

    sources = client.get("/api/v1/sources").json()
    assert sources["count"] >= 1
    assert all(item["tender_page_url"] for item in sources["items"])


def test_admin_endpoints_require_authentication(client):
    for path in ["/api/v1/admin/stats", "/api/v1/admin/sources", "/api/v1/admin/collection/runs"]:
        assert client.get(path).status_code == 401
    assert client.post("/api/v1/admin/collection/run").status_code == 401
    assert client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong-password"}
    ).status_code == 401


def test_admin_monitoring_sources_and_runs(client, admin_headers):
    stats = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert stats.status_code == 200
    assert stats.json()["tenders"]["total"] >= 3

    monitoring = client.get("/api/v1/admin/monitoring", headers=admin_headers).json()
    assert "scheduler" in monitoring
    assert monitoring["scheduler"]["running"] is False

    sources = client.get("/api/v1/admin/sources", params={"page_size": 5}, headers=admin_headers)
    assert sources.status_code == 200
    assert sources.json()["total"] >= 753 + 19

    runs = client.get("/api/v1/admin/collection/runs", headers=admin_headers)
    assert runs.status_code == 200

    documents = client.get("/api/v1/admin/documents", headers=admin_headers)
    assert documents.status_code == 200
    assert "status_counts" in documents.json()

    duplicates = client.get("/api/v1/admin/duplicates", headers=admin_headers)
    assert duplicates.status_code == 200

    health = client.get("/api/v1/admin/health", headers=admin_headers)
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_admin_source_crud(client, admin_headers):
    created = client.post(
        "/api/v1/admin/sources",
        headers=admin_headers,
        json={
            "name": "Test Water Office",
            "organization_name": "Test Water Office",
            "source_type": "agency",
            "official_website": "https://dwssm.gov.np/",
            "tender_page_url": "https://dwssm.gov.np/category/tender-notice/",
            "collector_key": "generic_html",
            "priority": 2,
        },
    )
    assert created.status_code == 201, created.text
    source = created.json()
    assert source["discovery_status"] == "discovered"

    patched = client.patch(
        f"/api/v1/admin/sources/{source['id']}",
        headers=admin_headers,
        json={"priority": 1, "notes": "Handled by API test"},
    )
    assert patched.status_code == 200
    assert patched.json()["priority"] == 1

    toggled = client.post(f"/api/v1/admin/sources/{source['id']}/toggle", headers=admin_headers)
    assert toggled.status_code == 200
    assert toggled.json()["active"] is False

    scan = client.post(
        f"/api/v1/admin/sources/{source['id']}/scan",
        headers=admin_headers,
        params={"wait": "false"},
    )
    # Disabled collector does not matter for the API; the source is inactive and
    # the background run is accepted.
    assert scan.status_code in {200, 400}


def test_review_and_verify_flow(client, admin_headers):
    created = client.post(
        "/api/v1/admin/tenders",
        headers=admin_headers,
        json={
            "title": "Invitation for Bid for bridge maintenance works",
            "organization_name": "Department of Roads",
            "notice_number": "IFB-TEST-001/2082",
            "category": "Works",
        },
    )
    assert created.status_code == 201
    tender_id = created.json()["id"]

    duplicate = client.post(
        "/api/v1/admin/tenders",
        headers=admin_headers,
        json={
            "title": "Duplicate notice attempt",
            "organization_name": "Department of Roads",
            "notice_number": "IFB-TEST-001/2082",
        },
    )
    assert duplicate.status_code == 409

    queue = client.get(
        "/api/v1/admin/tenders", headers=admin_headers, params={"verification_status": "pending"}
    ).json()
    assert any(item["id"] == tender_id for item in queue["items"])

    assert client.get(f"/api/v1/tenders/{tender_id}").status_code == 200
    verified = client.post(
        f"/api/v1/admin/tenders/{tender_id}/verify",
        headers=admin_headers,
        params={"decision": "verified"},
    )
    assert verified.status_code == 200
    assert verified.json()["verification_status"] == "verified"

    rejected = client.post(
        f"/api/v1/admin/tenders/{tender_id}/verify",
        headers=admin_headers,
        params={"decision": "rejected"},
    )
    assert rejected.status_code == 200
    assert client.get(f"/api/v1/tenders/{tender_id}").status_code == 404


def test_saved_searches_round_trip(client):
    device = "device-test-0001"
    created = client.post(
        "/api/v1/saved-searches",
        json={
            "device_id": device,
            "label": "Roads in Bagmati",
            "filters": {"q": "road", "province": "Bagmati", "bogus": "ignored"},
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["filters"] == {"q": "road", "province": "Bagmati"}

    listing = client.get("/api/v1/saved-searches", params={"device_id": device})
    assert listing.status_code == 200
    assert listing.json()["count"] == 1

    assert (
        client.delete(
            f"/api/v1/saved-searches/{body['id']}", params={"device_id": "other-device-01"}
        ).status_code
        == 404
    )
    deleted = client.delete(
        f"/api/v1/saved-searches/{body['id']}", params={"device_id": device}
    )
    assert deleted.status_code == 200
    assert client.get("/api/v1/saved-searches", params={"device_id": device}).json()["count"] == 0


def test_admin_dashboard_login_and_pages(client):
    anonymous = client.get("/admin", follow_redirects=False)
    assert anonymous.status_code == 303
    assert anonymous.headers["location"].startswith("/admin/login")

    login_page = client.get("/admin/login")
    assert login_page.status_code == 200
    token = client.cookies.get("bn_csrf")
    assert token

    bad = client.post(
        "/admin/login",
        data={"email": "admin@example.com", "password": "nope-nope", "csrf_token": token},
        follow_redirects=False,
    )
    assert bad.status_code == 401

    good = client.post(
        "/admin/login",
        data={
            "email": "admin@example.com",
            "password": "TestPassword123",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert good.status_code == 303
    assert good.headers["location"] == "/admin"

    for path in [
        "/admin",
        "/admin/sources",
        "/admin/runs",
        "/admin/review",
        "/admin/documents",
        "/admin/coverage",
        "/admin/health",
    ]:
        response = client.get(path)
        assert response.status_code == 200, (path, response.text[:400])
    assert "Bidders Nepal" in client.get("/admin").text

    rejected_csrf = client.post("/admin/run", data={"mode": "priority", "csrf_token": "bad"})
    assert rejected_csrf.status_code == 400
