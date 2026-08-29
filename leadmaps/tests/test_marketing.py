"""The pages a visitor sees before they pay."""

import pytest


@pytest.mark.parametrize(
    "path", ["/", "/pricing", "/docs", "/terms", "/privacy", "/healthz", "/robots.txt"]
)
def test_public_pages_render(client, path):
    assert client.get(path).status_code == 200


def test_landing_shows_every_plan_price(client):
    body = client.get("/").text
    for label in ("Free", "$49", "$149", "$399"):
        assert label in body


def test_pricing_comparison_lists_allowances(client):
    body = client.get("/pricing").text
    assert "25,000" in body
    assert "100,000" in body


def test_sitemap_is_xml(client):
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert "urlset" in response.text


def test_unknown_page_returns_branded_404(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert "does not exist" in response.text
