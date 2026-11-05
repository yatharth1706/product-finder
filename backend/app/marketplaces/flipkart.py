import json
import re
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from app.errors import FetchError
from app.http import fetch, make_client
from app.marketplaces.base import MarketplaceAdapter
from app.matching.normalizer import normalize_screen_size, normalize_size
from app.schemas import Availability, Candidate, FailureReason, Platform, Product

BASE_URL = "https://www.flipkart.com"
ALLOWED_HOSTS = {"flipkart.com"}

# Used only when a product page has no schema.org data.
IN_STOCK_MARKERS = ("buy now", "add to cart")
OUT_OF_STOCK_MARKERS = ("notify me", "sold out", "currently unavailable", "coming soon")


class FlipkartAdapter(MarketplaceAdapter):
    platform = Platform.FLIPKART

    async def search(self, product: Product) -> list[Candidate]:
        async with make_client(ALLOWED_HOSTS) as client:
            response = await fetch(
                client, f"{BASE_URL}/search?q={quote_plus(product.search_query)}"
            )
        return parse_search_page(response.text)

    async def get_details(self, candidate: Candidate) -> Candidate:
        async with make_client(ALLOWED_HOSTS) as client:
            response = await fetch(client, candidate.url)
        colour, availability = parse_product_page(response.text)
        attributes = candidate.attributes | ({"colour": colour} if colour else {})
        return candidate.model_copy(update={"attributes": attributes, "availability": availability})


def parse_search_page(html: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div[data-id]")
    if not cards:
        if "no results found" in soup.get_text(" ").lower():
            return []
        # Neither listings nor a "no results" message: the page is not what we expect.
        raise FetchError(FailureReason.PARSE_ERROR, "no listings on Flipkart search page")
    return [candidate for card in cards if (candidate := parse_card(card))]


def parse_card(card: Tag) -> Candidate | None:
    """Electronics cards carry the title in the image alt text and specs in a list.
    Fashion cards carry a brand line and a titled link instead."""
    link = card.select_one("a[href*='/p/']")
    if not link:
        return None

    titled_link = card.select_one("a[title]")
    image = card.select_one("img")
    if titled_link:
        brand_line = titled_link.find_previous_sibling("div")
        brand = brand_line.get_text(" ", strip=True) if brand_line else None
        title = f"{brand} {titled_link['title']}" if brand else titled_link["title"]
    elif image and image.get("alt"):
        brand, title = None, image["alt"]
    else:
        return None

    specs = " | ".join(li.get_text(" ", strip=True) for li in card.select("li"))
    return Candidate(
        platform=Platform.FLIPKART,
        url=clean_product_url(link["href"]),
        title=title,
        brand=brand,
        model_number=parse_model_id(specs),
        attributes=parse_card_attributes(title, specs),
        image_url=image.get("src") if image else None,
        availability=(
            Availability.OUT_OF_STOCK
            if "currently unavailable" in card.get_text(" ").lower()
            else Availability.UNKNOWN
        ),
    )


def clean_product_url(href: str) -> str:
    """Drop Flipkart's tracking parameters, keeping the product id (pid) that picks the variant."""
    parts = urlsplit(urljoin(BASE_URL, href))
    pid = parse_qs(parts.query).get("pid")
    query = f"?{urlencode({'pid': pid[0]})}" if pid else ""
    return f"{BASE_URL}{parts.path}{query}"


def parse_card_attributes(title: str, specs: str) -> dict[str, str]:
    """'12 GB RAM | 256 GB ROM' for phones; '... 138 cm (55 inch) ...' in TV titles."""
    attributes = {}
    ram = re.search(r"(\d+(?:\.\d+)?\s*(?:GB|MB|TB))\s*RAM", specs, re.I)
    storage = re.search(r"(\d+(?:\.\d+)?\s*(?:GB|MB|TB))\s*ROM", specs, re.I)
    if ram:
        attributes["ram"] = normalize_size(ram.group(1))
    if storage:
        attributes["storage"] = normalize_size(storage.group(1))
    if re.search(r"\binch\b", title, re.I) and (size := normalize_screen_size(title)):
        attributes["screen_size"] = size
    return attributes


def parse_model_id(specs: str) -> str | None:
    """TV cards list 'Model ID: UA55UE83AHULXL'."""
    match = re.search(r"Model ID:\s*([A-Z0-9-]+)", specs, re.I)
    return match.group(1) if match else None


def parse_product_page(html: str) -> tuple[str | None, Availability]:
    """Colour and stock from the page's schema.org Product data, with a text fallback."""
    soup = BeautifulSoup(html, "html.parser")
    product = read_schema_product(soup)
    if product:
        offers = product.get("offers")
        offer = offers[0] if isinstance(offers, list) and offers else offers or {}
        availability = str(offer.get("availability", ""))
        if availability.endswith("/InStock"):
            return product.get("color"), Availability.IN_STOCK
        if availability.endswith(("/OutOfStock", "/SoldOut", "/Discontinued")):
            return product.get("color"), Availability.OUT_OF_STOCK
        return product.get("color"), parse_availability_text(soup)
    return None, parse_availability_text(soup)


def read_schema_product(soup: BeautifulSoup) -> dict | None:
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "Product":
                return item
    return None


def parse_availability_text(soup: BeautifulSoup) -> Availability:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True).lower()
    # Out-of-stock wins: a sold-out page can still show "Add to cart" for other items.
    if any(marker in text for marker in OUT_OF_STOCK_MARKERS):
        return Availability.OUT_OF_STOCK
    if any(marker in text for marker in IN_STOCK_MARKERS):
        return Availability.IN_STOCK
    return Availability.UNKNOWN
