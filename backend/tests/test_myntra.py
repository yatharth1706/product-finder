import json

import httpx
import pytest

from app.errors import FetchError
from app.http import make_client
from app.marketplaces import myntra
from app.marketplaces.myntra import availability_from_sizes, parse_search_results
from app.schemas import Availability, FailureReason
from tests.conftest import read_fixture
from tests.fakes import PRODUCT


def test_parses_search_results() -> None:
    data = json.loads(read_fixture("myntra/search_nike_air_max_bia.json"))
    candidates = parse_search_results(data)
    assert len(candidates) == 5
    first = candidates[0]
    assert first.brand == "Nike"
    assert first.title == "Nike Air Max Bia Men's Shoes"
    assert first.attributes == {"colour": "Black"}
    assert first.url.startswith("https://www.myntra.com/Casual-Shoes/Nike/")
    assert first.image_url and first.image_url.startswith("https://")
    assert first.availability == Availability.IN_STOCK


def test_stock_from_sizes() -> None:
    assert availability_from_sizes([{"available": False}, {"available": True}]) == (
        Availability.IN_STOCK
    )
    assert availability_from_sizes([{"available": False}]) == Availability.OUT_OF_STOCK
    assert availability_from_sizes([]) == Availability.UNKNOWN


def test_unexpected_response_is_an_error() -> None:
    with pytest.raises(FetchError) as exc:
        parse_search_results({"message": "Unauthorized"})
    assert exc.value.reason == FailureReason.PARSE_ERROR


async def test_maintenance_page_means_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    # Myntra shows cloud servers a "Site Maintenance" page while the site is up.
    page = "<!doctype html><html><head><title>Site Maintenance</title></head></html>"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=page))
    monkeypatch.setattr(
        myntra, "make_client", lambda hosts: make_client(hosts, transport=transport)
    )

    with pytest.raises(FetchError) as exc:
        await myntra.MyntraAdapter().search(PRODUCT)
    assert exc.value.reason == FailureReason.BLOCKED
