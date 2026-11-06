from abc import ABC, abstractmethod

from app.schemas import Candidate, Platform, Product


class MarketplaceAdapter(ABC):
    """Talks to one marketplace. Knows nothing about matching.

    Methods raise `FetchError` for technical failures so they are never
    mistaken for "product not listed".
    """

    platform: Platform

    @abstractmethod
    async def search(self, product: Product) -> list[Candidate]:
        """Listings the marketplace returns for this product, best first."""

    @abstractmethod
    def search_page_url(self, product: Product) -> str:
        """The marketplace's own search page for this product, for people to open."""

    async def get_details(self, candidate: Candidate) -> Candidate:
        """The listing with details its search result lacked (colour, stock), if any.

        Marketplaces whose search results are already complete keep this default.
        """
        return candidate
