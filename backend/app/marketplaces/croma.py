from urllib.parse import quote

from app.errors import FetchError
from app.http import fetch, make_client
from app.marketplaces.base import MarketplaceAdapter
from app.schemas import Candidate, FailureReason, Platform, Product

SEARCH_URL = "https://api.croma.com/searchservices/v1/search?currentPage=0&query={query}&fields=FULL&channel=WEB"
ALLOWED_HOSTS = {"croma.com"}


class CromaAdapter(MarketplaceAdapter):
    """Croma's bot protection (Akamai) refuses server requests, which `fetch` reports as blocked.

    The response parser is not written yet: we have no real Croma response to build
    and test it against (see docs/access-check.md). If a request ever gets through,
    we report a parse error rather than guess at the format.
    """

    platform = Platform.CROMA

    async def search(self, product: Product) -> list[Candidate]:
        query = quote(product.search_query)
        async with make_client(ALLOWED_HOSTS) as client:
            await fetch(client, SEARCH_URL.format(query=query))
        raise FetchError(FailureReason.PARSE_ERROR, "Croma response parser not verified yet")
