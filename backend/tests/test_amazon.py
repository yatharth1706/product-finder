import pytest

from app.errors import ExtractionError, InvalidUrlError
from app.extractors.amazon import parse_product_page, validate_amazon_url
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
    ],
)
def test_accepts_amazon_product_urls(url: str) -> None:
    assert validate_amazon_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "https://www.flipkart.com/dp/B0DSKNQW8F",
        "https://amazon.in.evil.com/dp/B0DSKNQW8F",
        "https://www.amazon.in/gp/bestsellers",
        "ftp://www.amazon.in/dp/B0DSKNQW8F",
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
    assert product.attributes == {"ram": ram, "storage": storage}
    assert product.image_url and product.image_url.startswith("https://")


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
    html = read_fixture("amazon/phone_s25_ultra_in_stock.html").replace("256GB Storage", "")
    html = html.replace("256GB", "")
    with pytest.raises(ExtractionError, match="storage"):
        parse_product_page(html, URL)
