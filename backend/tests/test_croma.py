import json

import pytest

from app.errors import FetchError
from app.marketplaces.croma import parse_search_results
from app.schemas import Availability, Candidate, FailureReason
from tests.conftest import read_fixture


def results(fixture: str) -> list[Candidate]:
    return parse_search_results(json.loads(read_fixture(f"croma/{fixture}")))


def test_parses_phone_listings() -> None:
    first = results("search_s25_ultra.json")[0]
    assert first.title == "SAMSUNG Galaxy S25 Ultra 5G (12GB RAM, 256GB, Titanium Silverblue)"
    assert first.brand and first.brand.lower() == "samsung"
    assert first.attributes == {"ram": "12 GB", "storage": "256 GB"}
    assert first.url.startswith("https://www.croma.com/samsung-galaxy-s25-ultra")
    assert first.availability == Availability.IN_STOCK


def test_listings_without_stock_locations_are_out_of_stock() -> None:
    by_title = {c.title: c.availability for c in results("search_galaxy_s23.json")}
    assert by_title["SAMSUNG Galaxy S23 5G (8GB RAM, 128GB, Green)"] == Availability.OUT_OF_STOCK
    assert by_title["SAMSUNG Galaxy S23 5G (8GB RAM, 128GB, White)"] == Availability.IN_STOCK


def test_tv_listings_carry_short_model_code_and_screen_size() -> None:
    tvs = {c.title[:20]: c for c in results("search_lg_tv_43.json")}
    nu870 = next(c for c in tvs.values() if c.title.startswith("LG NU870B"))
    assert nu870.model_number == "43NU870"
    assert nu870.attributes["screen_size"] == "43 inch"


def test_unexpected_response_is_an_error() -> None:
    with pytest.raises(FetchError) as exc:
        parse_search_results({"status": "BAD_REQUEST", "message": "Invalid Search Request"})
    assert exc.value.reason == FailureReason.PARSE_ERROR


def test_images_are_requested_small() -> None:
    first = results("search_s25_ultra.json")[0]
    assert first.image_url and first.image_url.endswith("tr=w-200")
