import pytest

from app.errors import FetchError
from app.marketplaces.reliance_digital import parse_availability, parse_search_page
from app.schemas import Availability, FailureReason
from tests.conftest import read_fixture


def test_parses_search_results() -> None:
    candidates = parse_search_page(read_fixture("reliance_digital/search_nord_ce6.html"))
    assert len(candidates) == 12
    first = candidates[0]
    assert first.title.startswith("OnePlus Nord CE6 5G 256 GB, 8 GB RAM")
    assert first.brand == "One Plus"
    assert first.attributes["ram"] == "8 GB"
    assert first.attributes["storage"] == "256 GB"
    assert first.attributes["colour"] == "Pitch Black"
    assert first.url.startswith("https://www.reliancedigital.in/product/oneplus-nord-ce6")
    assert first.availability == Availability.IN_STOCK


def test_unsellable_listing_is_out_of_stock() -> None:
    candidates = parse_search_page(read_fixture("reliance_digital/search_s24_ultra.html"))
    assert Availability.OUT_OF_STOCK in {c.availability for c in candidates}


def test_product_page_availability() -> None:
    assert parse_availability(read_fixture("reliance_digital/product_in_stock.html")) == (
        Availability.IN_STOCK
    )
    assert parse_availability(read_fixture("reliance_digital/product_out_of_stock.html")) == (
        Availability.OUT_OF_STOCK
    )


def test_page_without_data_is_an_error() -> None:
    with pytest.raises(FetchError) as exc:
        parse_search_page("<html><body>Access Denied</body></html>")
    assert exc.value.reason == FailureReason.PARSE_ERROR


def test_tv_listings_carry_model_number_and_screen_size() -> None:
    candidates = parse_search_page(read_fixture("reliance_digital/search_tv_samsung_55.html"))
    tvs = [c for c in candidates if c.model_number]
    assert tvs
    assert all(c.attributes.get("screen_size", "").endswith(" inch") for c in tvs)
