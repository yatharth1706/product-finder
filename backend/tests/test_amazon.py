import pytest

from app.errors import ExtractionError, InvalidUrlError
from app.extractors.amazon import (
    parse_product_page,
    readable_model_name,
    resolve_category,
    validate_amazon_url,
)
from app.schemas import Category
from tests.conftest import read_fixture

URL = "https://www.amazon.in/dp/TEST"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.amazon.in/dp/B0DSKNQW8F",
        "https://www.amazon.in/Samsung-Galaxy/dp/B0DSKNQW8F/ref=sr_1_1?keywords=s25",
        "https://amazon.com/gp/product/B0DSKNQW8F",
        "https://amzn.in/d/abc123",
        "amazon.in/dp/B0F7X5FC43",
        "www.amazon.in/dp/B0F7X5FC43",
    ],
)
def test_accepts_amazon_product_urls(url: str) -> None:
    assert validate_amazon_url(url).startswith("https://")


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "https://www.flipkart.com/dp/B0DSKNQW8F",
        "https://amazon.in.evil.com/dp/B0DSKNQW8F",
        "https://www.amazon.in/gp/bestsellers",
        "ftp://www.amazon.in/dp/B0DSKNQW8F",
        "flipkart.com/dp/B0DSKNQW8F",
        "http://169.254.169.254/dp/B0DSKNQW8F",
    ],
)
def test_rejects_other_urls(url: str) -> None:
    with pytest.raises(InvalidUrlError):
        validate_amazon_url(url)


@pytest.mark.parametrize(
    ("fixture", "brand", "model", "ram", "storage"),
    [
        ("phone_s25_ultra_in_stock.html", "Samsung", "Galaxy S25 Ultra", "12 GB", "256 GB"),
        ("phone_s24_ultra_unavailable.html", "Samsung", "Galaxy S24 Ultra", "12 GB", "256 GB"),
        ("phone_redmi_turbo_5.html", "Redmi", "Turbo 5", "8 GB", "256 GB"),
        ("phone_oneplus_nord_ce6.html", "OnePlus", "Nord CE6", "8 GB", "256 GB"),
    ],
)
def test_parses_smartphone_pages(
    fixture: str, brand: str, model: str, ram: str, storage: str
) -> None:
    product = parse_product_page(read_fixture(f"amazon/{fixture}"), URL)
    assert product.category == Category.SMARTPHONE
    assert (product.brand, product.model) == (brand, model)
    assert (product.attributes["ram"], product.attributes["storage"]) == (ram, storage)
    assert product.attributes.get("colour")  # used to rank matches in the same colour first
    assert product.image_url and product.image_url.startswith("https://")


@pytest.mark.parametrize(
    ("fixture", "category", "model", "attributes", "query"),
    [
        (
            "tv_samsung_ue85.html",
            Category.TELEVISION,
            "UA55UE85AHULXL",
            {"screen_size": "55 inch"},
            "Samsung 55 inch (138cm) Crystal UHD 4K Vision AI 2026 Smart TV",
        ),
        (
            "sneaker_nike_air_max_bia.html",
            Category.SNEAKER,
            "Air Max Bia",
            {"colour": "WHITE/BLACK-WOLF GREY"},
            "Nike Air Max Bia",
        ),
        (
            "sneaker_adidas_drogo.html",
            Category.SNEAKER,
            "Drogo M",
            {"colour": "CGRANI/GRESIX"},
            "adidas Drogo M",
        ),
        (
            "polo_puma.html",
            Category.CLOTHING,
            "ESS Zippered Placket Polo",
            {"colour": "Desert Dust"},
            "PUMA ESS Zippered Placket Polo",
        ),
    ],
)
def test_parses_other_categories(
    fixture: str, category: Category, model: str, attributes: dict[str, str], query: str
) -> None:
    product = parse_product_page(read_fixture(f"amazon/{fixture}"), URL)
    assert product.category == category
    assert product.model == model
    assert product.attributes == attributes
    assert product.search_query == query


def test_unsupported_category() -> None:
    with pytest.raises(ExtractionError, match="Unsupported category"):
        parse_product_page(read_fixture("amazon/book.html"), URL)


def test_captcha_page() -> None:
    html = '<form action="/errors/validateCaptcha"><input name="field-keywords"></form>'
    with pytest.raises(ExtractionError, match="CAPTCHA"):
        parse_product_page(html, URL)


def test_page_without_product() -> None:
    with pytest.raises(ExtractionError, match="Could not read"):
        parse_product_page("<html><body>Page not found</body></html>", URL)


def test_missing_storage_is_reported() -> None:
    # Remove the storage size from the title and from the spec table.
    html = read_fixture("amazon/phone_s25_ultra_in_stock.html").replace("256", "")
    with pytest.raises(ExtractionError, match="storage"):
        parse_product_page(html, URL)


def test_product_image_is_requested_small() -> None:
    product = parse_product_page(read_fixture("amazon/phone_s25_ultra_in_stock.html"), URL)
    assert product.image_url and product.image_url.endswith("._SL300_.jpg")


def test_iphone_category_from_the_spec_table() -> None:
    specs = {"operating system": "iOS", "generic name": "iPhone"}
    assert resolve_category([], "iPhone 18 Pro (512 GB) - Silver", specs) == Category.SMARTPHONE


@pytest.mark.parametrize(
    ("name", "title", "expected"),
    [
        ("M9166c-black-9", "Converse Unisex Chuck Taylor All Star Sneakers", ""),
        ("IU1397", "adidas x Manchester United 24/25 Home Jersey", ""),
        ("704917_SMU_1_1999_Teamliga Jersey", "teamLIGA Men's Regular Fit Football Jersey", ""),
        ("ESS Logo Polo M", "Puma Men's Solid Slim Fit Cotton Essential Polo", "ESS Logo Polo"),
        ("Drogo M", "adidas Men Drogo M Running Shoe", "Drogo M"),
        ("Revolution 8", "Nike Mens Revolution 8 Running Shoes", "Revolution 8"),
    ],
)
def test_stock_codes_and_sizes_are_not_model_names(name: str, title: str, expected: str) -> None:
    assert readable_model_name(name, title) == expected


def test_clothing_fallback_search_drops_numbers() -> None:
    from app.extractors.amazon import build_fallback_query

    query = "adidas Manchester United 24/25 Home Jersey"
    assert build_fallback_query(Category.CLOTHING, query) == "adidas Manchester United Home Jersey"
    assert build_fallback_query(Category.CLOTHING, "Puma teamLIGA Jersey") is None
    assert build_fallback_query(Category.SMARTPHONE, "Samsung Galaxy S25 Ultra") is None
