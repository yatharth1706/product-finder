from abc import ABC, abstractmethod

from app.schemas import Availability, Candidate, Platform, Product


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
    async def check_availability(self, candidate: Candidate) -> Availability:
        """Whether this listing can be bought right now."""
