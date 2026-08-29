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


# --- Internal / unlimited accounts -----------------------------------------


def make_admin(client, email="admin@example.com"):
    """Create an unlimited admin via the CLI, then sign in as them."""
    from app.cli import main

    main(["create-admin", "--email", email, "--password", "a-good-long-password"])
    client.post("/logout")
    client.post("/login", data={"email": email, "password": "a-good-long-password"})
    return client


def test_cli_creates_an_unlimited_admin(client):
    admin = make_admin(client)
    body = admin.get("/app").text
    assert "Unlimited" in body
    assert "leads left" not in body


def test_an_unlimited_account_is_never_exhausted(client):
    admin = make_admin(client)
    # Far beyond any paid plan's monthly allowance.
    for index in range(6):
        response = admin.post(
            "/app/search", data={"keyword": f"gyms in City{index}", "max_depth": "50"}
        )
        assert "used all" not in response.text

    # Six 50-page searches is 6,000 leads — far past every paid allowance.
    body = admin.get("/app").text
    assert "6,000" in body
    assert "no cap on this account" in body


def test_an_unlimited_account_bypasses_every_feature_gate(client):
    admin = make_admin(client)
    # Depth beyond Scale, plus email enrichment, in one search.
    response = admin.post(
        "/app/search",
        data={"keyword": "cafes in Leeds", "max_depth": "60", "extract_emails": "1"},
    )
    assert "up to" not in response.text
    assert "@" in response.text

    # And the API, which the free plan cannot touch.
    keys_page = admin.post("/app/api-keys", data={"name": "internal"})
    assert "not included" not in keys_page.text


def test_the_internal_plan_is_not_for_sale(client):
    # It must not appear on the pricing page or the plan switcher.
    assert "Internal" not in client.get("/pricing").text
    admin = make_admin(client)
    assert "Choose Internal" not in admin.get("/app/billing").text


def test_cli_promotes_an_existing_user_rather_than_failing(account):
    from app.cli import main

    main(["create-admin", "--email", "owner@example.com", "--password", "a-new-long-password"])

    account.post("/logout")
    response = account.post(
        "/login", data={"email": "owner@example.com", "password": "a-new-long-password"}
    )
    assert response.url.path == "/app"
    assert "Unlimited" in response.text


def test_cli_set_plan_moves_an_account(account):
    from app.cli import main

    main(["set-plan", "--email", "owner@example.com", "--plan", "scale"])
    assert "100,000" in account.get("/app/billing").text
