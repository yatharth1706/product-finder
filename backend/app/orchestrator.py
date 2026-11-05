import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from app.config import settings
from app.errors import ExtractionError, FetchError
from app.extractors.amazon import extract_product
from app.job_store import JobStore
from app.marketplaces.base import MarketplaceAdapter
from app.matching.matcher import rank_matches
from app.schemas import (
    Availability,
    Candidate,
    Category,
    FailureReason,
    MarketplaceResult,
    MatchResult,
    Platform,
    Product,
    ResultStatus,
)

logger = logging.getLogger(__name__)

CATEGORY_PLATFORMS: dict[Category, list[Platform]] = {
    Category.SMARTPHONE: [Platform.FLIPKART, Platform.CROMA, Platform.RELIANCE_DIGITAL],
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
        self.store.mark_processing(search_id)
        started = time.perf_counter()
        try:
            product = await self.extract(amazon_url)
        except ExtractionError as exc:
            logger.info("search=%s extraction failed: %s", search_id, exc)
            self.store.fail(search_id, str(exc))
            return
        except Exception:
            logger.exception("search=%s unexpected extraction error", search_id)
            self.store.fail(search_id, "Something went wrong while reading the Amazon product")
            return

        logger.info(
            "search=%s extracted category=%s brand=%s model=%s in %.1fs",
            search_id, product.category, product.brand, product.model,
            time.perf_counter() - started,
        )  # fmt: skip
        self.store.save_source_product(search_id, product)

        platforms = CATEGORY_PLATFORMS.get(product.category, [])
        results = await asyncio.gather(
            *(search_marketplace(self.adapters[p], product, search_id) for p in platforms)
        )
        self.store.complete(search_id, list(results))
        logger.info("search=%s completed in %.1fs", search_id, time.perf_counter() - started)


async def search_marketplace(
    adapter: MarketplaceAdapter, product: Product, search_id: str = ""
) -> MarketplaceResult:
    """Never raises: every failure becomes a `failed` result for this marketplace only."""
    platform = adapter.platform
    started = time.perf_counter()
    try:
        async with asyncio.timeout(settings.marketplace_timeout_seconds):
            candidates = await adapter.search(product)
            matches = rank_matches(product, candidates)
            logger.info(
                "search=%s %s candidates=%d exact=%d",
                search_id, platform, len(candidates), len(matches),
            )  # fmt: skip
            if not matches:
                return MarketplaceResult(
                    platform=platform,
                    status=ResultStatus.NOT_LISTED,
                    candidates_checked=len(candidates),
                )
            result = await pick_by_availability(adapter, matches)
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


async def pick_by_availability(
    adapter: MarketplaceAdapter, matches: list[tuple[Candidate, MatchResult]]
) -> MarketplaceResult:
    """Among exact matches, prefer one that is in stock, then one that is out of stock.

    Stock is only confirmed by a positive signal; a page that says neither stays unknown.
    """
    out_of_stock: tuple[Candidate, MatchResult] | None = None
    pages_opened = 0
    for candidate, match_result in matches:
        availability = candidate.availability
        if availability == Availability.UNKNOWN:
            if pages_opened >= settings.max_availability_checks:
                continue
            pages_opened += 1
            try:
                availability = await adapter.check_availability(candidate)
            except FetchError as exc:
                logger.warning("%s availability check failed: %s", adapter.platform, exc)
                continue

        if availability == Availability.IN_STOCK:
            return build_result(ResultStatus.IN_STOCK, candidate, match_result)
        if availability == Availability.OUT_OF_STOCK and out_of_stock is None:
            out_of_stock = (candidate, match_result)

    if out_of_stock:
        return build_result(ResultStatus.OUT_OF_STOCK, *out_of_stock)
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
        image_url=candidate.image_url,
        match=match_result,
    )
