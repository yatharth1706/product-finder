import json
import re
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import settings
from app.errors import FetchError
from app.http import fetch, make_client
from app.marketplaces.base import MarketplaceAdapter
from app.matching.normalizer import colour_families, normalize_screen_size, normalize_size
from app.schemas import Availability, Candidate, Category, FailureReason, Platform, Product

BASE_URL = "https://www.flipkart.com"
ALLOWED_HOSTS = {"flipkart.com"}

# Used only when a product page has no schema.org data.
IN_STOCK_MARKERS = ("buy now", "add to cart")
OUT_OF_STOCK_MARKERS = ("notify me", "sold out", "currently unavailable", "coming soon")

# Search cards say this instead of a buyable price when a product cannot be bought.
CARD_UNAVAILABLE_MARKERS = ("currently unavailable", "coming soon", "sold out", "out of stock")

# Our basic colours -> the names of Flipkart's colour filter.
COLOUR_FILTER_NAMES = {"multi": "Multicolor"}


class FlipkartAdapter(MarketplaceAdapter):
    platform = Platform.FLIPKART

    def search_page_url(self, product: Product) -> str:
        return f"{BASE_URL}/search?q={quote_plus(search_text(product))}"

    async def search(self, product: Product) -> list[Candidate]:
        async with make_client(ALLOWED_HOSTS) as client:
            response = await fetch(client, self.search_page_url(product))
            candidates = parse_search_page(response.text)
            # Shoe and clothing cards show no colour. The same search with Flipkart's
            # colour filter tells which listings come in the product's main colour, in
            # case their product pages cannot be opened (Flipkart rate-limits them).
            colour = colour_filter_name(product)
            if colour and candidates:
                try:
                    filtered = await fetch(
                        client, f"{self.search_page_url(product)}{colour_filter(colour)}"
                    )
                    in_colour = parse_search_page(filtered.text)
                except FetchError:
                    in_colour = []
                hinted = {c.url for c in in_colour}
                candidates = [
                    c.model_copy(update={"colour_hint": colour}) if c.url in hinted else c
                    for c in candidates
                ]
                # Flipkart's results change between requests, so listings that only the
                # colour-filtered search returned are candidates too.
                seen = {c.url for c in candidates}
                candidates += [
                    c.model_copy(update={"colour_hint": colour})
                    for c in in_colour
                    if c.url not in seen
                ]
        return candidates

    async def get_details(self, candidate: Candidate) -> Candidate:
        if settings.flipkart_relay_url and settings.relay_token:
            colour, availability = await details_from_relay(candidate.url)
        else:
            colour, availability = await read_product_page(candidate.url)
        attributes = candidate.attributes | ({"colour": colour} if colour else {})
        return candidate.model_copy(update={"attributes": attributes, "availability": availability})


async def read_product_page(url: str) -> tuple[str | None, Availability]:
    """Colour and stock from a Flipkart product page (rate-limited from shared cloud IPs)."""
    if not is_product_url(url):
        raise FetchError(FailureReason.UNEXPECTED, f"not a Flipkart product page: {url}")
    async with make_client(ALLOWED_HOSTS) as client:
        response = await fetch(client, url)
    return parse_product_page(response.text)


async def details_from_relay(url: str) -> tuple[str | None, Availability]:
    """Ask the relay backend (on its own address) to read the product page for us."""
    relay = urlsplit(settings.flipkart_relay_url)
    async with make_client({relay.hostname or ""}) as client:
        try:
            response = await client.get(
                f"{settings.flipkart_relay_url.rstrip('/')}/api/v1/relay/flipkart-product",
                params={"url": url},
                headers={"X-Relay-Token": settings.relay_token},
            )
        except httpx.TimeoutException as exc:
            raise FetchError(FailureReason.TIMEOUT, "Flipkart relay timed out") from exc
        except httpx.HTTPError as exc:
            raise FetchError(FailureReason.UNEXPECTED, f"Flipkart relay: {exc}") from exc
    if response.status_code != 200:
        reason = response.json().get("detail", "unexpected") if response.content else "unexpected"
        known = {r.value for r in FailureReason}
        raise FetchError(
            FailureReason(reason) if reason in known else FailureReason.UNEXPECTED,
            f"Flipkart relay answered {response.status_code}",
        )
    data = response.json()
    return data.get("colour"), Availability(data.get("availability", "unknown"))


def is_product_url(url: str) -> bool:
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and (parts.hostname or "") in ("flipkart.com", "www.flipkart.com")
        and "/p/" in parts.path
    )


def search_text(product: Product) -> str:
    """Flipkart's results for a phone name mix RAM and storage variants and change between
    requests; naming them ("Samsung Galaxy M36 8 GB RAM 128 GB") puts the right one first."""
    if product.category != Category.SMARTPHONE:
        return product.search_query
    ram, storage = product.attributes.get("ram"), product.attributes.get("storage")
    parts = [product.search_query, f"{ram} RAM" if ram else "", storage or ""]
    return " ".join(part for part in parts if part)


def colour_filter_name(product: Product) -> str | None:
    """Flipkart's colour filter name for the product's main colour ("White"), if any."""
    if product.category not in (Category.SNEAKER, Category.CLOTHING):
        return None
    families = colour_families(product.attributes.get("colour", ""))
    if not families:
        return None
    return COLOUR_FILTER_NAMES.get(families[0], families[0].capitalize())


def colour_filter(colour: str) -> str:
    return f"&p%5B%5D=facets.color%255B%255D%3D{quote_plus(colour)}"


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
        availability=card_availability(card.get_text(" ")),
    )


def card_availability(text: str) -> Availability:
    """A card that can't be bought says so ("Currently unavailable"); one that can shows
    a price. Reading this from the search card saves opening the product page."""
    text = text.lower()
    if any(marker in text for marker in CARD_UNAVAILABLE_MARKERS):
        return Availability.OUT_OF_STOCK
    if "₹" in text:
        return Availability.IN_STOCK
    return Availability.UNKNOWN


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
