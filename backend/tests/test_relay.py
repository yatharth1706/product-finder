import httpx
import pytest
from fastapi.testclient import TestClient

from app import api
from app.http import make_client
from app.main import app
from app.marketplaces import flipkart
from app.schemas import Availability, Candidate, Platform

PRODUCT_PAGE = "https://www.flipkart.com/nike-air-max-bia-sneakers-men/p/itm72f998cc3c7dc?pid=SHO1"


@pytest.fixture
def relay_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.relay_token", "secret")

    async def fake_read(url: str) -> tuple[str | None, Availability]:
        return "White", Availability.IN_STOCK

    monkeypatch.setattr(api, "read_product_page", fake_read)


def relay(token: str | None, url: str = PRODUCT_PAGE) -> httpx.Response:
    headers = {"X-Relay-Token": token} if token is not None else {}
    return TestClient(app).get(
        "/api/v1/relay/flipkart-product", params={"url": url}, headers=headers
    )


def test_relay_is_off_without_a_configured_token() -> None:
    assert relay("anything").status_code == 403


def test_relay_needs_the_right_token(relay_on: None) -> None:
    assert relay(None).status_code == 403
    assert relay("wrong").status_code == 403
    response = relay("secret")
    assert response.status_code == 200
    assert response.json() == {"colour": "White", "availability": "in_stock"}


@pytest.mark.parametrize(
    "url",
    [
        "https://www.flipkart.com/search?q=nike",
        "https://evil.example/p/itm1",
        "http://169.254.169.254/latest/meta-data/",
        "http://www.flipkart.com/x/p/itm1",
    ],
)
def test_relay_only_reads_flipkart_product_pages(relay_on: None, url: str) -> None:
    assert relay("secret", url).status_code == 400


async def test_adapter_uses_the_relay_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.flipkart_relay_url", "https://relay.example")
    monkeypatch.setattr("app.config.settings.relay_token", "secret")
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"colour": "Black", "availability": "out_of_stock"})

    transport = httpx.MockTransport(answer)
    monkeypatch.setattr(
        flipkart, "make_client", lambda hosts: make_client(hosts, transport=transport)
    )
    listing = Candidate(platform=Platform.FLIPKART, url=PRODUCT_PAGE, title="NIKE Air Max Bia")

    detailed = await flipkart.FlipkartAdapter().get_details(listing)

    assert detailed.attributes["colour"] == "Black"
    assert detailed.availability == Availability.OUT_OF_STOCK
    assert seen[0].url.host == "relay.example"
    assert seen[0].headers["X-Relay-Token"] == "secret"
