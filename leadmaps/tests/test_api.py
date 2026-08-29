"""The customer-facing REST API."""

import pytest

from tests.conftest import mint_key, upgrade


@pytest.fixture()
def api(account):
    upgrade(account, "growth")
    key = mint_key(account)
    account.headers.update({"X-API-Key": key})
    return account


def test_api_key_is_required(account):
    assert account.get("/api/v1/usage").status_code == 401


def test_an_invalid_key_is_refused(account):
    response = account.get("/api/v1/usage", headers={"X-API-Key": "lm_live_nope"})
    assert response.status_code == 401


def test_keys_cannot_be_minted_below_starter(account):
    response = account.post("/app/api-keys", data={"name": "prod"})
    assert "not included in the Trial plan" in response.text


def test_a_revoked_key_stops_working(api):
    import re

    body = api.get("/app/api-keys").text
    key_id = re.search(r"/app/api-keys/([0-9a-f]{32})/revoke", body).group(1)
    api.post(f"/app/api-keys/{key_id}/revoke")

    assert api.get("/api/v1/usage").status_code == 401


def test_usage_reports_the_plan_and_allowance(api):
    payload = api.get("/api/v1/usage").json()
    assert payload == {
        "plan": "growth",
        "period": payload["period"],
        "included": 25000,
        "used": 0,
        "remaining": 25000,
    }


def test_creating_a_search_returns_202_and_an_id(api):
    response = api.post("/api/v1/searches", json={"keyword": "vets in Bristol", "max_depth": 2})
    assert response.status_code == 202
    body = response.json()
    assert body["id"]
    assert body["keyword"] == "vets in Bristol"
    assert body["source"] == "api"


def test_results_are_returned_once_complete(api):
    search_id = api.post(
        "/api/v1/searches", json={"keyword": "vets in Bristol", "max_depth": 2}
    ).json()["id"]

    body = api.get(f"/api/v1/searches/{search_id}").json()
    assert body["status"] == "completed"
    assert body["result_count"] == 40
    assert len(body["results"]) == 40
    assert body["results"][0]["title"]
    assert body["results"][0]["phone"]


def test_results_can_be_omitted(api):
    search_id = api.post("/api/v1/searches", json={"keyword": "vets", "max_depth": 1}).json()["id"]
    body = api.get(f"/api/v1/searches/{search_id}?include_results=false").json()
    assert body["results"] is None


def test_csv_endpoint_returns_a_downloadable_file(api):
    search_id = api.post("/api/v1/searches", json={"keyword": "vets", "max_depth": 1}).json()["id"]
    response = api.get(f"/api/v1/searches/{search_id}/results.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert len(response.text.strip().splitlines()) == 21


def test_listing_is_paginated_newest_first(api):
    for index in range(3):
        api.post("/api/v1/searches", json={"keyword": f"shops in City{index}", "max_depth": 1})

    body = api.get("/api/v1/searches?limit=2").json()
    assert len(body["searches"]) == 2
    assert body["has_more"] is True
    assert body["searches"][0]["keyword"] == "shops in City2"


def test_a_search_can_be_deleted(api):
    search_id = api.post("/api/v1/searches", json={"keyword": "vets", "max_depth": 1}).json()["id"]
    assert api.delete(f"/api/v1/searches/{search_id}").status_code == 204
    assert api.get(f"/api/v1/searches/{search_id}").status_code == 404


def test_another_accounts_search_is_not_visible(api, client):
    search_id = api.post("/api/v1/searches", json={"keyword": "vets", "max_depth": 1}).json()["id"]

    api.post("/logout")
    api.headers.pop("X-API-Key")
    api.post("/signup", data={"email": "rival@example.com", "password": "a-good-long-password"})
    upgrade(api, "growth")
    rival_key = mint_key(api)

    response = api.get(f"/api/v1/searches/{search_id}", headers={"X-API-Key": rival_key})
    assert response.status_code == 404


def test_an_empty_keyword_is_rejected(api):
    assert api.post("/api/v1/searches", json={"keyword": ""}).status_code == 422


def test_depth_beyond_the_plan_returns_403(api):
    response = api.post("/api/v1/searches", json={"keyword": "vets", "max_depth": 90})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "upgrade_required"


def test_exhausted_allowance_returns_402(account):
    upgrade(account, "starter")
    key = mint_key(account)
    headers = {"X-API-Key": key}

    # Starter allows 10 pages (200 leads) per search and 5,000 per month.
    for _ in range(25):
        account.post(
            "/api/v1/searches", headers=headers, json={"keyword": "cafes", "max_depth": 10}
        )
        # Vary the keyword so the mock engine does not dedupe by seed.

    response = account.post(
        "/api/v1/searches", headers=headers, json={"keyword": "cafes", "max_depth": 10}
    )
    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "quota_exceeded"


def test_api_is_forbidden_on_a_plan_without_it(account):
    upgrade(account, "starter")
    key = mint_key(account)
    upgrade(account, "free")

    response = account.post(
        "/api/v1/searches", headers={"X-API-Key": key}, json={"keyword": "cafes"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "upgrade_required"


def test_engine_outage_returns_503(api, monkeypatch):
    from app.engine import EngineError, MockEngine

    def explode(self, spec):
        raise EngineError("engine down")

    monkeypatch.setattr(MockEngine, "submit", explode)
    response = api.post("/api/v1/searches", json={"keyword": "vets", "max_depth": 1})
    assert response.status_code == 503


def test_openapi_schema_is_served(client):
    schema = client.get("/api/openapi.json").json()
    assert "/api/v1/searches" in schema["paths"]
