"""Plan limits — the rules that make the product chargeable."""

from tests.conftest import upgrade


def leads_left(client) -> int:
    import re

    body = client.get("/app").text
    return int(re.search(r"([\d,]+) leads left", body).group(1).replace(",", ""))


def test_free_plan_starts_with_its_full_allowance(account):
    assert leads_left(account) == 100


def test_a_search_consumes_exactly_the_leads_it_returns(account):
    account.post("/app/search", data={"keyword": "cafes in Leeds", "max_depth": "2"})
    assert leads_left(account) == 60


def test_allowance_is_never_overshot(account):
    # Free plan: 100 leads, 40 per two-page search. The third search must be
    # trimmed to the 20 leads that remain rather than delivering another 40.
    for index in range(3):
        account.post(
            "/app/search", data={"keyword": f"cafes in City{index}", "max_depth": "2"}
        )
    assert leads_left(account) == 0


def test_search_is_refused_once_the_allowance_is_gone(account):
    for index in range(3):
        account.post(
            "/app/search", data={"keyword": f"cafes in City{index}", "max_depth": "2"}
        )
    response = account.post("/app/search", data={"keyword": "one more", "max_depth": "1"})
    assert "used all" in response.text


def test_depth_beyond_the_plan_is_refused(account):
    response = account.post(
        "/app/search", data={"keyword": "cafes in Leeds", "max_depth": "25"}
    )
    assert "up to 2 pages" in response.text


def test_upgrading_raises_the_depth_limit(account):
    upgrade(account, "growth")
    response = account.post(
        "/app/search", data={"keyword": "cafes in Leeds", "max_depth": "25"}
    )
    assert "up to" not in response.text
    assert "500 leads" in response.text


def test_email_enrichment_is_gated_below_growth(account):
    upgrade(account, "starter")
    response = account.post(
        "/app/search",
        data={"keyword": "cafes in Leeds", "max_depth": "1", "extract_emails": "1"},
    )
    assert "Email enrichment is not included" in response.text


def test_email_enrichment_runs_on_growth(account):
    upgrade(account, "growth")
    response = account.post(
        "/app/search",
        data={"keyword": "cafes in Leeds", "max_depth": "1", "extract_emails": "1"},
    )
    assert "@" in response.text
    assert "example.com" in response.text


def test_an_empty_keyword_is_refused(account):
    response = account.post("/app/search", data={"keyword": "   ", "max_depth": "1"})
    assert "Enter what you want to search for" in response.text


def test_a_failed_engine_submission_is_not_charged(account, monkeypatch):
    from app.engine import EngineError, MockEngine

    def explode(self, spec):
        raise EngineError("engine down")

    monkeypatch.setattr(MockEngine, "submit", explode)
    response = account.post("/app/search", data={"keyword": "cafes", "max_depth": "2"})
    assert "unavailable" in response.text
    assert leads_left(account) == 100
