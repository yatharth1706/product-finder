from typing import Any
from urllib.parse import quote

from app.errors import FetchError
from app.http import fetch, make_client
from app.marketplaces.base import MarketplaceAdapter
from app.schemas import Availability, Candidate, FailureReason, Platform, Product

BASE_URL = "https://www.myntra.com"
SEARCH_URL = BASE_URL + "/gateway/v2/search/{query}?rows=50"
ALLOWED_HOSTS = {"myntra.com"}


class MyntraAdapter(MarketplaceAdapter):
    """Myntra's search API returns brand, colour and stock per size in one response,
    so no product pages are needed."""

    platform = Platform.MYNTRA

    async def search(self, product: Product) -> list[Candidate]:
        async with make_client(ALLOWED_HOSTS) as client:
            # The search API answers 401 until the homepage has set session cookies,
            # just as it would for a browser.
            await fetch(client, BASE_URL + "/")
            response = await fetch(client, SEARCH_URL.format(query=quote(product.search_query)))
        try:
            data = response.json()
        except ValueError as exc:
            raise FetchError(FailureReason.PARSE_ERROR, "Myntra search was not JSON") from exc
        return parse_search_results(data)


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
        image_url=(item.get("searchImage") or "").replace("http://", "https://") or None,
        availability=availability_from_sizes(item.get("inventoryInfo") or []),
    )


def availability_from_sizes(sizes: list[dict[str, Any]]) -> Availability:
    """In stock if any size can be bought; out of stock only if every listed size is sold out."""
    if not sizes:
        return Availability.UNKNOWN
    if any(size.get("available") for size in sizes):
        return Availability.IN_STOCK
    return Availability.OUT_OF_STOCK
