import asyncio
import json
import re
from typing import Any
from urllib.parse import quote

from app.errors import FetchError
from app.http import fetch, make_client
from app.marketplaces.base import MarketplaceAdapter
from app.matching.normalizer import normalize_screen_size, normalize_size
from app.schemas import Availability, Candidate, FailureReason, Platform, Product

BASE_URL = "https://www.reliancedigital.in"
ALLOWED_HOSTS = {"reliancedigital.in"}
STATE_MARKER = "window.__INITIAL_STATE__="
# 12 listings per page; two pages give about the same depth as one Flipkart page.
PAGES = 2


class RelianceDigitalAdapter(MarketplaceAdapter):
    """Reliance Digital renders its pages on the server and embeds the data as JSON."""

    platform = Platform.RELIANCE_DIGITAL

    async def search(self, product: Product) -> list[Candidate]:
        query = quote(product.search_query)
        async with make_client(ALLOWED_HOSTS) as client:
            responses = await asyncio.gather(
                *(
                    fetch(client, f"{BASE_URL}/products?q={query}&page_no={page}")
                    for page in range(1, PAGES + 1)
                )
            )
        return [c for response in responses for c in parse_search_page(response.text)]

    async def get_details(self, candidate: Candidate) -> Candidate:
        # Search results already carry stock; only open the page if they did not.
        if candidate.availability != Availability.UNKNOWN:
            return candidate
        async with make_client(ALLOWED_HOSTS) as client:
            response = await fetch(client, candidate.url)
        return candidate.model_copy(update={"availability": parse_availability(response.text)})


def read_page_state(html: str) -> dict[str, Any]:
    start = html.find(STATE_MARKER)
    if start < 0:
        raise FetchError(FailureReason.PARSE_ERROR, "no page data on Reliance Digital page")
    try:
        state, _ = json.JSONDecoder().raw_decode(html, start + len(STATE_MARKER))
    except json.JSONDecodeError as exc:
        raise FetchError(
            FailureReason.PARSE_ERROR, "unreadable Reliance Digital page data"
        ) from exc
    return state


def parse_search_page(html: str) -> list[Candidate]:
    listing = read_page_state(html).get("productListingPage", {}).get("productlists", {})
    return [to_candidate(item) for item in listing.get("items") or []]


def to_candidate(item: dict[str, Any]) -> Candidate:
    name = item["name"]
    specs = item.get("attributes", {})
    attributes = {}
    # "OnePlus Nord CE6 5G 256 GB, 8 GB RAM, Pitch Black, Mobile Phone"
    ram = re.search(r"(\d+(?:\.\d+)?\s*(?:GB|MB))\s*RAM", name, re.I)
    if ram:
        attributes["ram"] = normalize_size(ram.group(1))
    if storage := normalize_size(specs.get("internal-storage") or ""):
        attributes["storage"] = storage
    if specs.get("colour"):
        attributes["colour"] = specs["colour"]
    # "138 cm - 55 inch"
    if screen_size := normalize_screen_size(specs.get("screen_size_diagonal") or ""):
        attributes["screen_size"] = screen_size

    media = item.get("medias") or []
    return Candidate(
        platform=Platform.RELIANCE_DIGITAL,
        url=f"{BASE_URL}/product/{item['slug']}",
        title=name,
        brand=(item.get("brand") or {}).get("name"),
        model_number=specs.get("model-name"),
        attributes=attributes,
        image_url=media[0].get("url") if media else None,
        availability=availability_from_sellable(item.get("sellable")),
    )


def parse_availability(html: str) -> Availability:
    meta = read_page_state(html).get("productDetailsPage", {}).get("product_meta", {})
    return availability_from_sellable(meta.get("sellable"))


def availability_from_sellable(sellable: object) -> Availability:
    # `sellable` is false exactly when the stock quantity is 0.
    if sellable is True:
        return Availability.IN_STOCK
    if sellable is False:
        return Availability.OUT_OF_STOCK
    return Availability.UNKNOWN
