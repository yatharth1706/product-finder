import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from app.config import settings
from app.errors import ExtractionError, FetchError
from app.extractors.amazon import extract_product
from app.job_store import JobStore
from app.marketplaces.base import MarketplaceAdapter
from app.matching.matcher import may_match, rank_matches
from app.schemas import (
    REQUIRED_ATTRIBUTES,
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
    Category.TELEVISION: [Platform.FLIPKART, Platform.CROMA, Platform.RELIANCE_DIGITAL],
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
            candidates = unique_by_url(await adapter.search(product))
            candidates = await add_details(adapter, product, candidates)
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


async def add_details(
    adapter: MarketplaceAdapter, product: Product, candidates: list[Candidate]
) -> list[Candidate]:
    """Open the product pages of the few listings that could still be an exact match
    but lack a required detail or a stock status. Pages are fetched concurrently."""
    worth_opening = [
        i
        for i, candidate in enumerate(candidates)
        if may_match(product, candidate)
        and (
            candidate.availability == Availability.UNKNOWN
            or any(
                not candidate.attributes.get(name) for name in REQUIRED_ATTRIBUTES[product.category]
            )
        )
    ][: settings.max_detail_pages]
    if not worth_opening:
        return candidates

    detailed = await asyncio.gather(
        *(adapter.get_details(candidates[i]) for i in worth_opening), return_exceptions=True
    )
    updated = list(candidates)
    for i, result in zip(worth_opening, detailed, strict=True):
        if isinstance(result, Candidate):
            updated[i] = result
        elif isinstance(result, FetchError):
            logger.warning(
                "%s details failed for %s: %s", adapter.platform, candidates[i].url, result
            )
        else:
            raise result
    return updated


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
        image_url=candidate.image_url,
        match=match_result,
    )
