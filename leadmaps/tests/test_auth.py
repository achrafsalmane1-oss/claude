"""Signup, login, session handling."""


def test_signup_creates_account_and_signs_in(client):
    response = client.post(
        "/signup",
        data={"email": "New@Example.com", "password": "a-good-long-password"},
    )
    assert response.status_code == 200
    assert response.url.path == "/app"
    assert "New search" in response.text


def test_signup_rejects_short_password(client):
    response = client.post(
        "/signup", data={"email": "a@example.com", "password": "short"}
    )
    assert "at least 10 characters" in response.text


def test_signup_rejects_duplicate_email(client):
    data = {"email": "dupe@example.com", "password": "a-good-long-password"}
    client.post("/signup", data=data)
    client.post("/logout")
    response = client.post("/signup", data=data)
    assert "already exists" in response.text


def test_email_is_normalised_to_lowercase(client):
    client.post(
        "/signup", data={"email": "MiXeD@Example.com", "password": "a-good-long-password"}
    )
    client.post("/logout")
    response = client.post(
        "/login", data={"email": "mixed@example.com", "password": "a-good-long-password"}
    )
    assert response.url.path == "/app"


def test_login_with_wrong_password_is_refused(client):
    client.post(
        "/signup", data={"email": "u@example.com", "password": "a-good-long-password"}
    )
    client.post("/logout")
    response = client.post(
        "/login", data={"email": "u@example.com", "password": "wrong-password-here"}
    )
    assert "do not match" in response.text


def test_unknown_email_gives_the_same_message_as_a_wrong_password(client):
    response = client.post(
        "/login", data={"email": "ghost@example.com", "password": "a-good-long-password"}
    )
    assert "do not match" in response.text


def test_dashboard_requires_a_session(client):
    response = client.get("/app")
    assert response.url.path == "/login"


def test_logout_clears_the_session(account):
    account.post("/logout")
    response = account.get("/app")
    assert response.url.path == "/login"


def test_signup_honours_a_chosen_plan_by_sending_to_billing(client):
    response = client.post(
        "/signup",
        data={
            "email": "buyer@example.com",
            "password": "a-good-long-password",
            "plan": "growth",
        },
    )
    assert response.url.path == "/app/billing"


def test_next_parameter_cannot_redirect_off_site(client):
    client.post(
        "/signup", data={"email": "n@example.com", "password": "a-good-long-password"}
    )
    client.post("/logout")
    response = client.post(
        "/login",
        data={
            "email": "n@example.com",
            "password": "a-good-long-password",
            "next": "https://evil.example.net/phish",
        },
    )
    assert response.url.path == "/app"
