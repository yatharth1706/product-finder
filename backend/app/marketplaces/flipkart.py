import re
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

from app.errors import FetchError
from app.http import fetch, make_client
from app.marketplaces.base import MarketplaceAdapter
from app.matching.normalizer import normalize_size
from app.schemas import Availability, Candidate, FailureReason, Platform, Product

BASE_URL = "https://www.flipkart.com"
ALLOWED_HOSTS = {"flipkart.com"}

IN_STOCK_MARKERS = ("buy now", "add to cart")
OUT_OF_STOCK_MARKERS = ("notify me", "sold out", "currently unavailable", "coming soon")


class FlipkartAdapter(MarketplaceAdapter):
    platform = Platform.FLIPKART

    async def search(self, product: Product) -> list[Candidate]:
        query = f"{product.brand} {product.model}"
        async with make_client(ALLOWED_HOSTS) as client:
            response = await fetch(client, f"{BASE_URL}/search?q={quote_plus(query)}")
        return parse_search_page(response.text)

    async def check_availability(self, candidate: Candidate) -> Availability:
        async with make_client(ALLOWED_HOSTS) as client:
            response = await fetch(client, candidate.url)
        return parse_availability(response.text)


def parse_search_page(html: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div[data-id]")
    if not cards:
        if "no results found" in soup.get_text(" ").lower():
            return []
        # Neither listings nor a "no results" message: the page is not what we expect.
        raise FetchError(FailureReason.PARSE_ERROR, "no listings on Flipkart search page")

    candidates = []
    for card in cards:
        link = card.select_one("a[href*='/p/']")
        image = card.select_one("img[alt]")
        if not link or not image:
            continue
        specs = " | ".join(li.get_text(" ", strip=True) for li in card.select("li"))
        candidates.append(
            Candidate(
                platform=Platform.FLIPKART,
                url=clean_product_url(link["href"]),
                title=image["alt"],
                attributes=parse_phone_specs(specs),
                image_url=image.get("src"),
                availability=(
                    Availability.OUT_OF_STOCK
                    if "currently unavailable" in card.get_text(" ").lower()
                    else Availability.UNKNOWN
                ),
            )
        )
    return candidates


def clean_product_url(href: str) -> str:
    """Drop Flipkart's tracking parameters, keeping the product id (pid) that picks the variant."""
    parts = urlsplit(urljoin(BASE_URL, href))
    pid = parse_qs(parts.query).get("pid")
    query = f"?{urlencode({'pid': pid[0]})}" if pid else ""
    return f"{BASE_URL}{parts.path}{query}"


def parse_phone_specs(specs: str) -> dict[str, str]:
    """'12 GB RAM | 256 GB ROM | Expandable Upto 1 TB' -> {'ram': '12 GB', 'storage': '256 GB'}."""
    attributes = {}
    ram = re.search(r"(\d+(?:\.\d+)?\s*(?:GB|MB|TB))\s*RAM", specs, re.I)
    storage = re.search(r"(\d+(?:\.\d+)?\s*(?:GB|MB|TB))\s*ROM", specs, re.I)
    if ram:
        attributes["ram"] = normalize_size(ram.group(1))
    if storage:
        attributes["storage"] = normalize_size(storage.group(1))
    return attributes


def parse_availability(html: str) -> Availability:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True).lower()
    # Out-of-stock wins: a sold-out page can still show "Add to cart" for other sellers' items.
    if any(marker in text for marker in OUT_OF_STOCK_MARKERS):
        return Availability.OUT_OF_STOCK
    if any(marker in text for marker in IN_STOCK_MARKERS):
        return Availability.IN_STOCK
    return Availability.UNKNOWN
