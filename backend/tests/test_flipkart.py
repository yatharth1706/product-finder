import pytest

from app.errors import FetchError
from app.marketplaces.flipkart import parse_availability, parse_search_page
from app.schemas import Availability, FailureReason
from tests.conftest import read_fixture


def test_parses_search_results() -> None:
    candidates = parse_search_page(read_fixture("flipkart/search_s25_ultra.html"))
    assert len(candidates) == 24
    first = candidates[0]
    assert first.title == "Samsung Galaxy S25 Ultra 5G (Titanium Black, 256 GB)"
    assert first.attributes == {"ram": "12 GB", "storage": "256 GB"}
    assert first.url.startswith("https://www.flipkart.com/samsung-galaxy-s25-ultra")
    assert "?pid=" in first.url and "&" not in first.url
    assert first.image_url


def test_search_card_marks_out_of_stock() -> None:
    candidates = parse_search_page(read_fixture("flipkart/search_s25_ultra.html"))
    by_availability = {c.availability for c in candidates}
    assert Availability.OUT_OF_STOCK in by_availability
    assert Availability.UNKNOWN in by_availability


def test_ram_variants_are_kept_apart() -> None:
    candidates = parse_search_page(read_fixture("flipkart/search_redmi_turbo_5.html"))
    assert {c.attributes["ram"] for c in candidates if "Turbo 5" in c.title} == {"8 GB", "12 GB"}


def test_no_results_page() -> None:
    assert parse_search_page("<div>Sorry, no results found!</div>") == []


def test_unexpected_page_is_an_error_not_an_empty_result() -> None:
    with pytest.raises(FetchError) as exc:
        parse_search_page("<html><body>Please verify you are a human</body></html>")
    assert exc.value.reason == FailureReason.PARSE_ERROR


def test_availability() -> None:
    assert parse_availability(read_fixture("flipkart/product_in_stock.html")) == (
        Availability.IN_STOCK
    )
    assert parse_availability(read_fixture("flipkart/product_out_of_stock.html")) == (
        Availability.OUT_OF_STOCK
    )
    assert parse_availability("<html><body>Samsung phone</body></html>") == Availability.UNKNOWN
