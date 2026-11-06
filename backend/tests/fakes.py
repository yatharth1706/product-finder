import asyncio

from app.errors import FetchError
from app.marketplaces.base import MarketplaceAdapter
from app.schemas import Availability, Candidate, Category, FailureReason, Platform, Product

PRODUCT = Product(
    url="https://www.amazon.in/dp/B0DSKNQW8F",
    title="Samsung Galaxy S25 Ultra 5G (Titanium Black, 12GB RAM, 256GB Storage)",
    brand="Samsung",
    model="Galaxy S25 Ultra",
    category=Category.SMARTPHONE,
    attributes={"ram": "12 GB", "storage": "256 GB"},
    search_query="Samsung Galaxy S25 Ultra",
)


def listing(
    title: str = "Samsung Galaxy S25 Ultra 5G (Titanium Black, 256 GB)",
    url: str = "https://www.flipkart.com/s25",
    storage: str = "256 GB",
    availability: Availability = Availability.UNKNOWN,
) -> Candidate:
    return Candidate(
        platform=Platform.FLIPKART,
        url=url,
        title=title,
        attributes={"ram": "12 GB", "storage": storage},
        availability=availability,
    )


class FakeAdapter(MarketplaceAdapter):
    def __init__(
        self,
        platform: Platform = Platform.FLIPKART,
        candidates: list[Candidate] | None = None,
        stock: dict[str, Availability] | None = None,
        error: FailureReason | None = None,
        delay: float = 0,
    ) -> None:
        self.platform = platform
        self.candidates = candidates or []
        self.stock = stock or {}
        self.error = error
        self.delay = delay
        self.details_opened: list[str] = []

    async def search(self, product: Product) -> list[Candidate]:
        await asyncio.sleep(self.delay)
        if self.error:
            raise FetchError(self.error)
        return self.candidates

    def search_page_url(self, product: Product) -> str:
        return f"https://{self.platform}.example/search"

    async def get_details(self, candidate: Candidate) -> Candidate:
        self.details_opened.append(candidate.url)
        availability = self.stock.get(candidate.url, Availability.UNKNOWN)
        return candidate.model_copy(update={"availability": availability})
