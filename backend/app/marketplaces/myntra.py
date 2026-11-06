import json
import re
from typing import Any
from urllib.parse import quote

from app.errors import FetchError
from app.http import fetch, make_client
from app.marketplaces.base import MarketplaceAdapter
from app.schemas import Availability, Candidate, Category, FailureReason, Platform, Product

BASE_URL = "https://www.myntra.com"
ALLOWED_HOSTS = {"myntra.com"}
STATE_MARKER = "window.__myx = "


class MyntraAdapter(MarketplaceAdapter):
    """Myntra's search page embeds its results as JSON (brand, colour, stock per size),
    so one request per search is enough and no product pages are needed."""

    platform = Platform.MYNTRA

    def search_page_url(self, product: Product) -> str:
        # Same format as Myntra's own search box: /campus-rustle-shoes?rawQuery=...
        query = search_text(product)
        slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        return f"{BASE_URL}/{slug}?rawQuery={quote(query)}"

    async def search(self, product: Product) -> list[Candidate]:
        async with make_client(ALLOWED_HOSTS) as client:
            response = await fetch(client, self.search_page_url(product))
        return parse_search_page(response.text)


def search_text(product: Product) -> str:
    """Myntra's search needs the product type: "Campus Rustle" finds other Campus
    shoes, "Campus Rustle Shoes" finds the Rustle. (Flipkart does worse with it,
    so this stays here rather than in the shared query.)"""
    query = product.search_query
    if product.category == Category.SNEAKER and not re.search(
        r"\b(shoes?|sneakers?)\b", query, re.I
    ):
        query += " Shoes"
    return query


def parse_search_page(html: str) -> list[Candidate]:
    start = html.find(STATE_MARKER)
    if start < 0:
        snippet = " ".join(html[:200].split())
        # Myntra answers refused clients with a fake "Site Maintenance" page
        # while the site works fine for everyone else.
        reason = (
            FailureReason.BLOCKED if "maintenance" in snippet.lower() else FailureReason.PARSE_ERROR
        )
        raise FetchError(reason, f"no search data on Myntra page: {snippet}")
    try:
        state, _ = json.JSONDecoder().raw_decode(html, start + len(STATE_MARKER))
        results = state["searchData"]["results"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise FetchError(FailureReason.PARSE_ERROR, "unreadable Myntra page data") from exc
    return parse_search_results(results)


def parse_search_results(data: dict[str, Any]) -> list[Candidate]:
    if "products" not in data:
        raise FetchError(FailureReason.PARSE_ERROR, "no products field in Myntra response")
    return [to_candidate(item) for item in data["products"]]


def to_candidate(item: dict[str, Any]) -> Candidate:
    colour = item.get("primaryColour")
    return Candidate(
        platform=Platform.MYNTRA,
        url=f"{BASE_URL}/{item['landingPageUrl']}",
        title=item["productName"],
        brand=item.get("brand"),
        attributes={"colour": colour} if colour else {},
        image_url=small_image(item.get("searchImage")),
        availability=availability_from_sizes(item.get("inventoryInfo") or []),
    )


def small_image(url: str | None) -> str | None:
    """Myntra resizes from the URL path: assets.myntassets.com/h_240,q_90,w_180/assets/..."""
    if not url:
        return None
    url = url.replace("http://", "https://", 1)
    return url.replace(
        "https://assets.myntassets.com/assets/",
        "https://assets.myntassets.com/h_240,q_90,w_180/assets/",
        1,
    )


def availability_from_sizes(sizes: list[dict[str, Any]]) -> Availability:
    """In stock if any size can be bought; out of stock only if every listed size is sold out."""
    if not sizes:
        return Availability.UNKNOWN
    if any(size.get("available") for size in sizes):
        return Availability.IN_STOCK
    return Availability.OUT_OF_STOCK
