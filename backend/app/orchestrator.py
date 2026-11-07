import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable

from app.config import settings
from app.errors import ExtractionError, FetchError
from app.extractors.amazon import extract_product
from app.job_store import JobStore
from app.marketplaces.base import MarketplaceAdapter
from app.matching.matcher import closest_miss, may_match, rank_matches
from app.schemas import (
    REQUIRED_ATTRIBUTES,
    Availability,
    Candidate,
    Category,
    ClosestListing,
    FailureReason,
    MarketplaceResult,
    MatchResult,
    Platform,
    Product,
    ResultStatus,
    SearchEvent,
)

logger = logging.getLogger(__name__)

CATEGORY_PLATFORMS: dict[Category, list[Platform]] = {
    Category.SMARTPHONE: [Platform.FLIPKART, Platform.CROMA],
    Category.TELEVISION: [Platform.FLIPKART, Platform.CROMA],
    Category.SNEAKER: [Platform.FLIPKART, Platform.MYNTRA],
    Category.CLOTHING: [Platform.FLIPKART, Platform.MYNTRA],
}


class SearchOrchestrator:
    """Runs one search: Amazon product -> every marketplace of its category -> results."""

    def __init__(
        self,
        store: JobStore,
        adapters: dict[Platform, MarketplaceAdapter],
        extract: Callable[[str], Awaitable[Product]] = extract_product,
    ) -> None:
        self.store = store
        self.adapters = adapters
        self.extract = extract

    async def run(self, search_id: str, amazon_url: str) -> None:
        """Run a search to the end, recording every step in the job store."""
        async for _ in self.stream(search_id, amazon_url):
            pass

    async def stream(self, search_id: str, amazon_url: str) -> AsyncIterator[SearchEvent]:
        """Yield each step as soon as it is known: the Amazon product, then one result
        per marketplace in the order they finish. The job store is kept up to date."""
        self.store.mark_processing(search_id)
        started = time.perf_counter()
        try:
            product = await self.extract(amazon_url)
        except ExtractionError as exc:
            logger.info("search=%s extraction failed: %s", search_id, exc)
            self.store.fail(search_id, str(exc))
            yield SearchEvent(type="failed", search_id=search_id, error=str(exc))
            return
        except Exception:
            logger.exception("search=%s unexpected extraction error", search_id)
            error = "Something went wrong while reading the Amazon product"
            self.store.fail(search_id, error)
            yield SearchEvent(type="failed", search_id=search_id, error=error)
            return

        logger.info(
            "search=%s extracted category=%s brand=%s model=%s in %.1fs",
            search_id, product.category, product.brand, product.model,
            time.perf_counter() - started,
        )  # fmt: skip
        self.store.save_source_product(search_id, product)
        platforms = CATEGORY_PLATFORMS.get(product.category, [])
        yield SearchEvent(type="product", search_id=search_id, product=product, platforms=platforms)

        tasks = [
            asyncio.create_task(search_marketplace(self.adapters[p], product, search_id))
            for p in platforms
        ]
        try:
            for finished in asyncio.as_completed(tasks):
                result = await finished
                result.search_url = self.adapters[result.platform].search_page_url(product)
                self.store.add_result(search_id, result)
                yield SearchEvent(type="result", search_id=search_id, result=result)
        finally:
            # A client that disconnects mid-stream should not leave searches running.
            for task in tasks:
                task.cancel()

        self.store.complete(search_id)
        logger.info("search=%s completed in %.1fs", search_id, time.perf_counter() - started)
        yield SearchEvent(type="completed", search_id=search_id)


async def search_marketplace(
    adapter: MarketplaceAdapter, product: Product, search_id: str = ""
) -> MarketplaceResult:
    """Never raises: every failure becomes a `failed` result for this marketplace only."""
    platform = adapter.platform
    started = time.perf_counter()
    try:
        async with asyncio.timeout(settings.marketplace_timeout_seconds):
            candidates = unique_by_url(await adapter.search(product))
            candidates = await add_details(adapter, product, candidates)
            matches = rank_matches(product, candidates)
            logger.info(
                "search=%s %s candidates=%d exact=%d",
                search_id, platform, len(candidates), len(matches),
            )  # fmt: skip
            if not matches:
                return not_listed(platform, product, candidates)
            result = pick_by_availability(matches)
            result.candidates_checked = len(candidates)
            return result
    except TimeoutError:
        reason = FailureReason.TIMEOUT
    except FetchError as exc:
        logger.warning("search=%s %s failed: %s", search_id, platform, exc)
        reason = exc.reason
    except Exception:
        logger.exception("search=%s %s unexpected error", search_id, platform)
        reason = FailureReason.UNEXPECTED
    finally:
        logger.info("search=%s %s took %.1fs", search_id, platform, time.perf_counter() - started)
    return MarketplaceResult(platform=platform, status=ResultStatus.FAILED, failure_reason=reason)


def unique_by_url(candidates: list[Candidate]) -> list[Candidate]:
    """Marketplaces repeat listings (sponsored and organic); keep the first of each."""
    seen: set[str] = set()
    unique = []
    for candidate in candidates:
        if candidate.url not in seen:
            seen.add(candidate.url)
            unique.append(candidate)
    return unique


# Product pages opened at once, and stock checks per marketplace. Stores rate-limit
# bursts (Flipkart answers 429), so keep both small.
DETAIL_CONCURRENCY = 3
STOCK_CHECKS = 3


async def add_details(
    adapter: MarketplaceAdapter, product: Product, candidates: list[Candidate]
) -> list[Candidate]:
    """Open product pages only where they can change the answer.

    If some listings already match exactly (phones and TVs: the search card has every
    detail), only their stock is unknown: open them one at a time, best first, and stop
    at the first one in stock. Otherwise (shoes: colour is only on the product page),
    open the listings that could still match, a few at a time.
    """
    updated = list(candidates)
    position = {candidate.url: i for i, candidate in enumerate(candidates)}

    exact = [candidate for candidate, _ in rank_matches(product, candidates)]
    if exact:
        if any(c.availability == Availability.IN_STOCK for c in exact):
            return updated
        unknown = [c for c in exact if c.availability == Availability.UNKNOWN]
        for candidate in unknown[:STOCK_CHECKS]:
            detailed = await get_details_or_keep(adapter, candidate)
            updated[position[candidate.url]] = detailed
            if detailed.availability == Availability.IN_STOCK:
                break
        return updated

    worth_opening = [
        c
        for c in candidates
        if may_match(product, c)
        and (
            c.availability == Availability.UNKNOWN
            or any(not c.attributes.get(name) for name in REQUIRED_ATTRIBUTES[product.category])
        )
    ][: settings.max_detail_pages]
    limit = asyncio.Semaphore(DETAIL_CONCURRENCY)

    async def open_page(candidate: Candidate) -> Candidate:
        async with limit:
            return await get_details_or_keep(adapter, candidate)

    for detailed in await asyncio.gather(*(open_page(c) for c in worth_opening)):
        updated[position[detailed.url]] = detailed
    return updated


async def get_details_or_keep(adapter: MarketplaceAdapter, candidate: Candidate) -> Candidate:
    """A product page that fails to load leaves the listing as it was."""
    try:
        return await adapter.get_details(candidate)
    except FetchError as exc:
        logger.warning("%s details failed for %s: %s", adapter.platform, candidate.url, exc)
        return candidate


def not_listed(
    platform: Platform, product: Product, candidates: list[Candidate]
) -> MarketplaceResult:
    """No exact match; keep the closest listing and why it was rejected, to explain it."""
    result = MarketplaceResult(
        platform=platform,
        status=ResultStatus.NOT_LISTED,
        candidates_checked=len(candidates),
    )
    if closest := closest_miss(product, candidates):
        listing, match_result = closest
        result.closest_listing = ClosestListing(
            title=listing.title, url=listing.url, reasons=match_result.reasons
        )
    return result


def pick_by_availability(matches: list[tuple[Candidate, MatchResult]]) -> MarketplaceResult:
    """Among exact matches, prefer one that is in stock, then one that is out of stock.

    Stock is only confirmed by a positive signal; a listing that says neither stays unknown.
    """
    for wanted, status in (
        (Availability.IN_STOCK, ResultStatus.IN_STOCK),
        (Availability.OUT_OF_STOCK, ResultStatus.OUT_OF_STOCK),
    ):
        for candidate, match_result in matches:
            if candidate.availability == wanted:
                return build_result(status, candidate, match_result)

    best, best_match = matches[0]
    result = build_result(ResultStatus.FAILED, best, best_match)
    result.failure_reason = FailureReason.AVAILABILITY_UNKNOWN
    return result


def build_result(
    status: ResultStatus, candidate: Candidate, match_result: MatchResult
) -> MarketplaceResult:
    return MarketplaceResult(
        platform=candidate.platform,
        status=status,
        title=candidate.title,
        url=candidate.url,
        model_number=candidate.model_number,
        image_url=candidate.image_url,
        match=match_result,
    )
