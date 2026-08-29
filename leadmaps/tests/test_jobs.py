"""Search lifecycle, results and CSV export."""

from tests.conftest import job_id_from, upgrade


def run_search(client, keyword="dentists in Manchester", depth="2"):
    response = client.post(
        "/app/search", data={"keyword": keyword, "max_depth": depth, "lang": "en"}
    )
    return response, job_id_from(response)


def test_a_search_completes_and_shows_results(account):
    response, _ = run_search(account)
    assert "completed" in response.text
    assert "40 leads" in response.text


def test_results_appear_in_the_job_list(account):
    run_search(account)
    body = account.get("/app/jobs").text
    assert "dentists in Manchester" in body


def test_csv_export_has_a_header_and_one_row_per_lead(account):
    _, job_id = run_search(account)
    response = account.get(f"/app/jobs/{job_id}/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    lines = response.text.strip().splitlines()
    assert lines[0].startswith("business_name,category,address,phone,website")
    assert len(lines) == 41


def test_csv_filename_is_derived_from_the_keyword(account):
    _, job_id = run_search(account)
    response = account.get(f"/app/jobs/{job_id}/export.csv")
    assert "dentists-in-manchester" in response.headers["content-disposition"]


def test_another_account_cannot_read_your_search(account):
    _, job_id = run_search(account)
    account.post("/logout")
    account.post(
        "/signup", data={"email": "other@example.com", "password": "a-good-long-password"}
    )

    assert account.get(f"/app/jobs/{job_id}").status_code == 404
    assert account.get(f"/app/jobs/{job_id}/export.csv").status_code == 404


def test_identical_searches_are_deterministic_under_the_mock_engine(account):
    upgrade(account, "starter")
    _, first = run_search(account, "bakeries in Oslo", "1")
    _, second = run_search(account, "bakeries in Oslo", "1")

    first_csv = account.get(f"/app/jobs/{first}/export.csv").text
    second_csv = account.get(f"/app/jobs/{second}/export.csv").text
    assert first_csv == second_csv


def test_concurrent_search_limit_is_enforced(account, monkeypatch):
    # Freeze jobs in "running" so they stay open, then exceed the limit.
    from app.engine import EngineJob, MockEngine

    monkeypatch.setattr(
        MockEngine,
        "fetch",
        lambda self, job_id: EngineJob(job_id=job_id, status="running"),
    )
    upgrade(account, "growth")

    for index in range(5):
        account.post("/app/search", data={"keyword": f"gyms in City{index}", "max_depth": "1"})

    response = account.post("/app/search", data={"keyword": "one too many", "max_depth": "1"})
    assert "searches running" in response.text
