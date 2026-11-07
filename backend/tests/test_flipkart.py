import pytest

from app.errors import FetchError
from app.marketplaces.flipkart import card_availability, parse_product_page, parse_search_page
from app.schemas import Availability, Category, FailureReason
from tests.conftest import read_fixture


def test_parses_phone_search_results() -> None:
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
    # "Currently unavailable" cards are out of stock; cards with a price are in stock.
    assert by_availability == {Availability.OUT_OF_STOCK, Availability.IN_STOCK}


def test_card_availability() -> None:
    assert card_availability("Samsung Galaxy | ₹79,999") == Availability.IN_STOCK
    assert card_availability("Currently unavailable | ₹79,999") == Availability.OUT_OF_STOCK
    assert card_availability("Coming Soon") == Availability.OUT_OF_STOCK
    assert card_availability("Samsung Galaxy") == Availability.UNKNOWN


def test_ram_variants_are_kept_apart() -> None:
    candidates = parse_search_page(read_fixture("flipkart/search_redmi_turbo_5.html"))
    assert {c.attributes["ram"] for c in candidates if "Turbo 5" in c.title} == {"8 GB", "12 GB"}


def test_tv_cards_carry_model_number_and_screen_size() -> None:
    candidates = parse_search_page(read_fixture("flipkart/search_tv_samsung_55.html"))
    first = candidates[0]
    assert first.model_number == "UA55UE83AHULXL"
    assert first.attributes["screen_size"] == "55 inch"


def test_fashion_cards_carry_brand_and_title() -> None:
    candidates = parse_search_page(read_fixture("flipkart/search_nike_air_max_bia.html"))
    first = candidates[0]
    assert first.brand == "NIKE"
    assert first.title == "NIKE Air Max Bia Sneakers For Men"
    assert "colour" not in first.attributes  # only on the product page


def test_no_results_page() -> None:
    assert parse_search_page("<div>Sorry, no results found!</div>") == []


def test_unexpected_page_is_an_error_not_an_empty_result() -> None:
    with pytest.raises(FetchError) as exc:
        parse_search_page("<html><body>Please verify you are a human</body></html>")
    assert exc.value.reason == FailureReason.PARSE_ERROR


@pytest.mark.parametrize(
    ("fixture", "colour", "availability"),
    [
        ("product_in_stock.html", "Titanium Black", Availability.IN_STOCK),
        ("product_out_of_stock.html", "Titanium White Silver", Availability.OUT_OF_STOCK),
        (
            "product_sneaker_in_stock.html",
            "WHITE/EMERALD GREEN-GUM MED BROWN",
            Availability.IN_STOCK,
        ),
        ("product_polo_out_of_stock.html", "Blazing Blue-Black", Availability.OUT_OF_STOCK),
    ],
)
def test_product_page(fixture: str, colour: str, availability: Availability) -> None:
    assert parse_product_page(read_fixture(f"flipkart/{fixture}")) == (colour, availability)


def test_product_page_without_schema_data_falls_back_to_page_text() -> None:
    assert parse_product_page("<button>Notify Me</button>") == (None, Availability.OUT_OF_STOCK)
    assert parse_product_page("<button>Buy Now</button>") == (None, Availability.IN_STOCK)
    assert parse_product_page("<p>Samsung phone</p>") == (None, Availability.UNKNOWN)


def test_colour_filter_only_for_shoes_and_clothes() -> None:
    from app.marketplaces.flipkart import colour_filter_name
    from tests.fakes import PRODUCT

    shoe = PRODUCT.model_copy(
        update={"category": Category.SNEAKER, "attributes": {"colour": "WHITE/BLACK-WOLF GREY"}}
    )
    assert colour_filter_name(shoe) == "White"
    assert colour_filter_name(shoe.model_copy(update={"attributes": {"colour": "Shimmer"}})) is None
    assert colour_filter_name(PRODUCT) is None


def test_phone_searches_name_ram_and_storage() -> None:
    from app.marketplaces.flipkart import search_text
    from tests.fakes import PRODUCT

    assert search_text(PRODUCT) == "Samsung Galaxy S25 Ultra 12 GB RAM 256 GB"
    tv = PRODUCT.model_copy(
        update={"category": Category.TELEVISION, "search_query": "LG 43 inch TV"}
    )
    assert search_text(tv) == "LG 43 inch TV"


async def test_colour_filtered_search_adds_hints_and_listings(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import httpx

    from app.http import make_client
    from app.marketplaces import flipkart
    from tests.fakes import PRODUCT

    main_page = read_fixture("flipkart/search_puma_polo.html")
    filtered_page = read_fixture("flipkart/search_nike_air_max_bia.html")

    def answer(request: httpx.Request) -> httpx.Response:
        filtered = "facets.color" in str(request.url)
        return httpx.Response(200, text=filtered_page if filtered else main_page)

    transport = httpx.MockTransport(answer)
    monkeypatch.setattr(
        flipkart, "make_client", lambda hosts: make_client(hosts, transport=transport)
    )
    shoe = PRODUCT.model_copy(
        update={"category": Category.SNEAKER, "attributes": {"colour": "White"}}
    )

    candidates = await flipkart.FlipkartAdapter().search(shoe)

    hinted = [c for c in candidates if c.colour_hint == "White"]
    filtered_urls = {c.url for c in parse_search_page(filtered_page)}
    assert hinted and {c.url for c in hinted} == filtered_urls
    assert any("PUMA" in c.title and c.colour_hint is None for c in candidates)
