import json
import re
from typing import Any
from urllib.parse import quote

from app.errors import FetchError
from app.http import fetch, make_client
from app.marketplaces.base import MarketplaceAdapter
from app.matching.normalizer import normalize_screen_size, normalize_size
from app.schemas import Availability, Candidate, FailureReason, Platform, Product

BASE_URL = "https://www.croma.com"
# The search API Croma's own website calls. "query" must end with ":relevance",
# and channelCode is the delivery pincode (Mumbai) used for prices and stock.
SEARCH_API = (
    "https://api.croma.com/searchservices/v1/search"
    "?currentPage=0&query={query}%3Arelevance&fields=FULL&channel=WEB&channelCode=400049"
)
ALLOWED_HOSTS = {"croma.com"}
PAGE_STATE_MARKER = "window.__INITIAL_DATA__="

# "(12GB RAM, 256GB, Titanium Gray)": the size not followed by "RAM" is storage.
RAM_PATTERN = re.compile(r"(\d+(?:\.\d+)?\s*(?:GB|MB|TB))\s*RAM", re.I)
STORAGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?\s*(?:GB|TB))\b(?!\s*RAM)", re.I)
# Short model codes in Croma's summary: "LG LED NANO 43NU870 UHD 4K" -> 43NU870.
MODEL_CODE_PATTERN = re.compile(r"\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{6,}\b")


class CromaAdapter(MarketplaceAdapter):
    """Croma's search API returns name, link and stock per listing in one response.

    Croma's bot protection (Akamai) refuses home connections and some servers; those
    requests are reported as blocked by `fetch`. See docs/access-check.md.
    """

    platform = Platform.CROMA

    def search_page_url(self, product: Product) -> str:
        query = quote(product.search_query)
        return f"{BASE_URL}/searchB?q={query}%3Arelevance&text={query}"

    async def search(self, product: Product) -> list[Candidate]:
        async with make_client(ALLOWED_HOSTS) as client:
            response = await fetch(client, SEARCH_API.format(query=quote(product.search_query)))
        try:
            data = response.json()
        except ValueError as exc:
            raise FetchError(FailureReason.PARSE_ERROR, "Croma search was not JSON") from exc
        return parse_search_results(data)

    async def get_details(self, candidate: Candidate) -> Candidate:
        """Croma's search gives a shortened model number, sometimes not a code at all
        ("BRAVIA2"); the product page has the full one ("K-43S22M2")."""
        if not candidate.model_number_shortened:
            return candidate
        async with make_client(ALLOWED_HOSTS) as client:
            response = await fetch(client, candidate.url)
        model_number = parse_model_number(response.text)
        if not model_number:
            return candidate
        return candidate.model_copy(
            update={"model_number": model_number, "model_number_shortened": False}
        )


def parse_model_number(html: str) -> str | None:
    """The "Model Number" in the product page's embedded data (window.__INITIAL_DATA__)."""
    start = html.find(PAGE_STATE_MARKER)
    if start < 0:
        return None
    # The embedded data is a JavaScript object: `undefined` is not valid JSON.
    text = re.sub(r":undefined\b", ":null", html[start + len(PAGE_STATE_MARKER) :].lstrip())
    try:
        state, _ = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError:
        return None
    return find_feature(state, "Model Number")


def find_feature(data: Any, name: str) -> str | None:
    """The first value of a specification feature called `name`, anywhere in the data."""
    if isinstance(data, dict):
        if data.get("name") == name:
            values = [v.get("value") for v in data.get("featureValues") or [] if v.get("value")]
            if values:
                return values[0]
        children = data.values()
    elif isinstance(data, list):
        children = data
    else:
        return None
    for child in children:
        if found := find_feature(child, name):
            return found
    return None


def parse_search_results(data: dict[str, Any]) -> list[Candidate]:
    if "products" not in data:
        raise FetchError(FailureReason.PARSE_ERROR, "no products field in Croma response")
    return [to_candidate(item) for item in data["products"]]


def to_candidate(item: dict[str, Any]) -> Candidate:
    # "SAMSUNG Galaxy S25 Ultra 5G (12GB RAM, 256GB, Titanium Gray)"
    # "LG NU870B 109.22 cm (43 inch) 2 Star Nano Cell 4K Ultra HD Smart TV ..."
    name = item["name"]
    attributes = {}
    if ram := RAM_PATTERN.search(name):
        attributes["ram"] = normalize_size(ram.group(1))
    if storage := STORAGE_PATTERN.search(name):
        attributes["storage"] = normalize_size(storage.group(1))
    if re.search(r"\binch\b", name, re.I) and (size := normalize_screen_size(name)):
        attributes["screen_size"] = size

    code = MODEL_CODE_PATTERN.search((item.get("summary") or "").upper())
    image = item.get("plpImage")
    return Candidate(
        platform=Platform.CROMA,
        url=BASE_URL + item["url"],
        title=name,
        brand=item.get("manufacturer"),
        model_number=code.group(0) if code else None,
        model_number_shortened=True,
        attributes=attributes,
        image_url=small_image(image),
        availability=availability_from_stock_locations(item.get("stockFlag")),
    )


def small_image(url: object) -> str | None:
    """Croma's image host resizes from the URL (`tr=w-200`); originals are up to 500 KB."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    return f"{url}{'&' if '?' in url else '?'}tr=w-200"


def availability_from_stock_locations(locations: object) -> Availability:
    """`stockFlag` lists the stores and warehouses holding stock; empty means none."""
    if not isinstance(locations, list):
        return Availability.UNKNOWN
    return Availability.IN_STOCK if locations else Availability.OUT_OF_STOCK
