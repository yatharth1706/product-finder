"""Real Amazon pages matched against real marketplace pages, saved as fixtures.

These check the whole chain of extraction, parsing and matching for each category,
without the network.
"""

import json

from app.extractors.amazon import parse_product_page
from app.marketplaces import croma, flipkart, myntra
from app.matching.matcher import may_match, rank_matches
from tests.conftest import read_fixture

URL = "https://www.amazon.in/dp/TEST"


def amazon(fixture: str):  # type: ignore[no-untyped-def]
    return parse_product_page(read_fixture(f"amazon/{fixture}"), URL)


def test_phone_finds_only_the_right_storage_variant_on_flipkart() -> None:
    phone = amazon("phone_s25_ultra_in_stock.html")
    listings = flipkart.parse_search_page(read_fixture("flipkart/search_s25_ultra.html"))
    matches = rank_matches(phone, listings)
    assert matches
    assert all("256 GB" in c.title for c, _ in matches)


def test_phone_from_a_different_generation_is_not_listed() -> None:
    phone = amazon("phone_s24_ultra_unavailable.html")
    listings = flipkart.parse_search_page(read_fixture("flipkart/search_s25_ultra.html"))
    assert rank_matches(phone, listings) == []


def test_tv_matches_exact_model_number_on_flipkart() -> None:
    tv = amazon("tv_samsung_mini_led.html")
    assert tv.model == "UA55M2EHAULXL"
    listings = flipkart.parse_search_page(read_fixture("flipkart/search_tv_samsung_55.html"))
    matches = rank_matches(tv, listings)
    assert matches
    assert {c.model_number for c, _ in matches} == {"UA55M2EHAULXL"}


def test_tv_on_croma_matches_shortened_model_number() -> None:
    tv = amazon("tv_samsung_mini_led.html").model_copy(
        update={"brand": "LG", "model": "43NU870BPLA", "attributes": {"screen_size": "43 inch"}}
    )
    listings = croma.parse_search_results(json.loads(read_fixture("croma/search_lg_tv_43.json")))
    matches = rank_matches(tv, listings)
    assert [c.model_number for c, _ in matches] == ["43NU870"]
    assert matches[0][0].title.startswith("LG NU870B 109.22 cm (43 inch)")


def test_tv_with_close_model_numbers_is_not_listed() -> None:
    # Flipkart has the 55" UE83/UE84 and the 75" UE85, but not the 55" UE85.
    tv = amazon("tv_samsung_ue85.html")
    listings = flipkart.parse_search_page(read_fixture("flipkart/search_tv_samsung_55.html"))
    assert rank_matches(tv, listings) == []


def test_sneaker_on_myntra_matches_colour_and_gender() -> None:
    shoe = amazon("sneaker_nike_air_max_bia.html")
    data = json.loads(read_fixture("myntra/search_nike_air_max_bia.json"))
    matches = rank_matches(shoe, myntra.parse_search_results(data))
    assert matches
    for candidate, _ in matches:
        assert candidate.attributes["colour"] == "White"
        assert "Women" not in candidate.title


def test_sneaker_on_flipkart_needs_product_pages_for_colour() -> None:
    shoe = amazon("sneaker_nike_air_max_bia.html")
    listings = flipkart.parse_search_page(read_fixture("flipkart/search_nike_air_max_bia.html"))
    assert rank_matches(shoe, listings) == []  # no colour on search cards
    worth_opening = [c for c in listings if may_match(shoe, c)]
    assert worth_opening
    assert all("Women" not in c.title and "Air Max Bia" in c.title for c in worth_opening)


def test_polo_on_myntra_with_abbreviated_model_name() -> None:
    polo = amazon("polo_puma.html")
    data = json.loads(read_fixture("myntra/search_puma_polo.json"))
    matches = rank_matches(polo, myntra.parse_search_results(data))
    assert [c.title for c, _ in matches] == ["Puma Essential Men's Zippered Placket Polo"]


def test_phone_on_croma_matches_storage_variant() -> None:
    phone = amazon("phone_s25_ultra_in_stock.html")
    listings = croma.parse_search_results(json.loads(read_fixture("croma/search_s25_ultra.json")))
    matches = rank_matches(phone, listings)
    assert matches
    assert all("256GB" in c.title and "S25 Ultra" in c.title for c, _ in matches)


def test_lite_variant_on_croma_is_rejected() -> None:
    phone = amazon("phone_oneplus_nord_ce6.html")
    listings = croma.parse_search_results(json.loads(read_fixture("croma/search_nord_ce6.json")))
    matches = rank_matches(phone, listings)
    assert matches
    assert all("Lite" not in c.title and "256GB" in c.title for c, _ in matches)
