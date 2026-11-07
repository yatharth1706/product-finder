import time

import pytest

from app.errors import ExtractionError
from app.job_store import JobStore
from app.orchestrator import CATEGORY_PLATFORMS, SearchOrchestrator, search_marketplace
from app.schemas import (
    Availability,
    Candidate,
    Category,
    FailureReason,
    JobStatus,
    Platform,
    ResultStatus,
)
from tests.fakes import PRODUCT, FakeAdapter, listing


async def test_in_stock_match() -> None:
    adapter = FakeAdapter(
        candidates=[listing()], stock={"https://www.flipkart.com/s25": Availability.IN_STOCK}
    )
    result = await search_marketplace(adapter, PRODUCT)
    assert result.status == ResultStatus.IN_STOCK
    assert result.url == "https://www.flipkart.com/s25"
    assert result.match and result.match.matched


async def test_prefers_in_stock_listing_over_out_of_stock() -> None:
    adapter = FakeAdapter(
        candidates=[
            listing(url="https://f/sold-out", availability=Availability.OUT_OF_STOCK),
            listing(url="https://f/available"),
        ],
        stock={"https://f/available": Availability.IN_STOCK},
    )
    result = await search_marketplace(adapter, PRODUCT)
    assert result.status == ResultStatus.IN_STOCK
    assert result.url == "https://f/available"


async def test_out_of_stock_match() -> None:
    adapter = FakeAdapter(candidates=[listing(availability=Availability.OUT_OF_STOCK)])
    result = await search_marketplace(adapter, PRODUCT)
    assert result.status == ResultStatus.OUT_OF_STOCK
    assert result.url
    assert adapter.details_opened == []


async def test_not_listed_when_no_exact_match() -> None:
    adapter = FakeAdapter(candidates=[listing(storage="512 GB")])
    result = await search_marketplace(adapter, PRODUCT)
    assert result.status == ResultStatus.NOT_LISTED
    assert result.candidates_checked == 1
    assert result.closest_listing
    assert result.closest_listing.reasons == ["Storage mismatch: expected 256 GB, found 512 GB"]


async def test_unknown_availability_is_not_reported_as_in_or_out_of_stock() -> None:
    adapter = FakeAdapter(candidates=[listing()])
    result = await search_marketplace(adapter, PRODUCT)
    assert result.status == ResultStatus.FAILED
    assert result.failure_reason == FailureReason.AVAILABILITY_UNKNOWN
    assert result.url == "https://www.flipkart.com/s25"


async def test_stock_checks_are_bounded() -> None:
    adapter = FakeAdapter(candidates=[listing(url=f"https://f/{i}") for i in range(10)])
    await search_marketplace(adapter, PRODUCT)
    assert len(adapter.details_opened) == 3


async def test_stock_checks_stop_at_the_first_in_stock() -> None:
    adapter = FakeAdapter(
        candidates=[listing(url=f"https://f/{i}") for i in range(5)],
        stock={"https://f/0": Availability.OUT_OF_STOCK, "https://f/1": Availability.IN_STOCK},
    )
    result = await search_marketplace(adapter, PRODUCT)
    assert adapter.details_opened == ["https://f/0", "https://f/1"]
    assert result.status == ResultStatus.IN_STOCK


async def test_pages_of_known_mismatches_are_not_opened() -> None:
    adapter = FakeAdapter(
        candidates=[listing(url="https://f/512", storage="512 GB"), listing(url="https://f/256")]
    )
    await search_marketplace(adapter, PRODUCT)
    assert adapter.details_opened == ["https://f/256"]


async def test_repeated_listings_are_checked_once() -> None:
    adapter = FakeAdapter(candidates=[listing(), listing()])
    result = await search_marketplace(adapter, PRODUCT)
    assert adapter.details_opened == ["https://www.flipkart.com/s25"]
    assert result.candidates_checked == 1


async def test_blocked_marketplace_is_a_failure_not_not_listed() -> None:
    result = await search_marketplace(FakeAdapter(error=FailureReason.BLOCKED), PRODUCT)
    assert result.status == ResultStatus.FAILED
    assert result.failure_reason == FailureReason.BLOCKED


async def test_slow_marketplace_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.orchestrator.settings.marketplace_timeout_seconds", 0.05)
    result = await search_marketplace(FakeAdapter(delay=1), PRODUCT)
    assert result.failure_reason == FailureReason.TIMEOUT


async def test_unexpected_error_is_contained() -> None:
    class Broken(FakeAdapter):
        async def search(self, product):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    result = await search_marketplace(Broken(), PRODUCT)
    assert result.failure_reason == FailureReason.UNEXPECTED


async def fake_extract(url: str):  # type: ignore[no-untyped-def]
    return PRODUCT


async def test_run_completes_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(CATEGORY_PLATFORMS, Category.SMARTPHONE, [Platform.FLIPKART])
    store = JobStore()
    job = store.create(PRODUCT.url)
    adapter = FakeAdapter(candidates=[listing(availability=Availability.OUT_OF_STOCK)])
    orchestrator = SearchOrchestrator(store, {Platform.FLIPKART: adapter}, extract=fake_extract)

    await orchestrator.run(job.search_id, PRODUCT.url)

    saved = store.get(job.search_id)
    assert saved and saved.status == JobStatus.COMPLETED
    assert saved.source_product == PRODUCT
    assert saved.results and saved.results[0].status == ResultStatus.OUT_OF_STOCK
    assert saved.results[0].search_url == "https://flipkart.example/search"
    assert saved.completed_at


async def test_run_fails_job_when_extraction_fails() -> None:
    async def failing_extract(url: str):  # type: ignore[no-untyped-def]
        raise ExtractionError("Unsupported category: Books")

    store = JobStore()
    job = store.create(PRODUCT.url)
    await SearchOrchestrator(store, {}, extract=failing_extract).run(job.search_id, PRODUCT.url)

    saved = store.get(job.search_id)
    assert saved and saved.status == JobStatus.FAILED
    assert saved.error == "Unsupported category: Books"


async def test_marketplaces_run_concurrently_and_fail_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        CATEGORY_PLATFORMS, Category.SMARTPHONE, [Platform.FLIPKART, Platform.CROMA]
    )
    adapters = {
        Platform.FLIPKART: FakeAdapter(
            candidates=[listing(availability=Availability.OUT_OF_STOCK)], delay=0.2
        ),
        Platform.CROMA: FakeAdapter(Platform.CROMA, error=FailureReason.BLOCKED, delay=0.2),
    }
    store = JobStore()
    job = store.create(PRODUCT.url)

    started = time.perf_counter()
    await SearchOrchestrator(store, adapters, extract=fake_extract).run(job.search_id, "u")
    elapsed = time.perf_counter() - started

    saved = store.get(job.search_id)
    assert saved and saved.status == JobStatus.COMPLETED
    statuses = {r.platform: r.status for r in saved.results or []}
    assert statuses == {
        Platform.FLIPKART: ResultStatus.OUT_OF_STOCK,
        Platform.CROMA: ResultStatus.FAILED,
    }
    assert elapsed < 0.35  # both 0.2s searches ran at the same time


async def test_stream_yields_results_in_the_order_marketplaces_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        CATEGORY_PLATFORMS, Category.SMARTPHONE, [Platform.FLIPKART, Platform.CROMA]
    )
    adapters = {
        Platform.FLIPKART: FakeAdapter(error=FailureReason.BLOCKED, delay=0.2),
        Platform.CROMA: FakeAdapter(Platform.CROMA, error=FailureReason.BLOCKED, delay=0),
    }
    store = JobStore()
    job = store.create(PRODUCT.url)
    orchestrator = SearchOrchestrator(store, adapters, extract=fake_extract)

    events = [e async for e in orchestrator.stream(job.search_id, PRODUCT.url)]

    assert [e.type for e in events] == ["product", "result", "result", "completed"]
    assert [e.result.platform for e in events if e.result] == [Platform.CROMA, Platform.FLIPKART]
    saved = store.get(job.search_id)
    assert saved and len(saved.results or []) == 2


SHOE = PRODUCT.model_copy(
    update={
        "title": "Nike Mens Air Max Bia Sneakers",
        "brand": "Nike",
        "model": "Air Max Bia",
        "category": Category.SNEAKER,
        "attributes": {"colour": "White/Black"},
    }
)


def shoe_listing(colour_hint: str | None = None) -> Candidate:
    return Candidate(
        platform=Platform.FLIPKART,
        url="https://www.flipkart.com/air-max-bia",
        title="NIKE Air Max Bia Sneakers For Men",
        brand="NIKE",
        availability=Availability.IN_STOCK,
        colour_hint=colour_hint,
    )


async def test_blocked_product_pages_are_not_reported_as_not_listed() -> None:
    adapter = FakeAdapter(candidates=[shoe_listing()], details_error=FailureReason.BLOCKED)
    result = await search_marketplace(adapter, SHOE)
    assert result.status == ResultStatus.FAILED
    assert result.failure_reason == FailureReason.BLOCKED


async def test_colour_hint_is_used_when_the_page_is_blocked() -> None:
    adapter = FakeAdapter(candidates=[shoe_listing("White")], details_error=FailureReason.BLOCKED)
    result = await search_marketplace(adapter, SHOE)
    assert result.status == ResultStatus.IN_STOCK


async def test_product_pages_are_reused_between_searches() -> None:
    adapter = FakeAdapter(candidates=[listing()])
    await search_marketplace(adapter, PRODUCT)
    await search_marketplace(adapter, PRODUCT)
    assert adapter.details_opened == ["https://www.flipkart.com/s25"]


async def test_listings_in_the_products_colour_are_opened_first() -> None:
    others = [shoe_listing().model_copy(update={"url": f"https://f/other-{i}"}) for i in range(8)]
    hinted = shoe_listing("White").model_copy(update={"url": "https://f/white"})
    adapter = FakeAdapter(candidates=[*others, hinted])
    await search_marketplace(adapter, SHOE)
    assert adapter.details_opened[0] == "https://f/white"


async def test_broader_search_is_tried_when_nothing_matches() -> None:
    class TwoSearches(FakeAdapter):
        async def search(self, product):  # type: ignore[no-untyped-def]
            return [listing()] if product.search_query == "broader" else []

    product = PRODUCT.model_copy(update={"fallback_query": "broader"})
    adapter = TwoSearches(stock={"https://www.flipkart.com/s25": Availability.IN_STOCK})
    result = await search_marketplace(adapter, product)
    assert result.status == ResultStatus.IN_STOCK


async def test_tv_page_is_opened_for_the_full_model_number() -> None:
    tv = PRODUCT.model_copy(
        update={
            "title": "Sony 108 cm (43 inches) BRAVIA 2M2 Series 4K Smart LED Google TV",
            "brand": "Sony",
            "model": "K-43S22M2",
            "category": Category.TELEVISION,
            "attributes": {"screen_size": "43 inch"},
        }
    )
    full_numbers = {"https://c/315862": "K-43S25M2", "https://c/316033": "K-43S22M2"}

    class Croma(FakeAdapter):
        async def get_details(self, candidate):  # type: ignore[no-untyped-def]
            self.details_opened.append(candidate.url)
            return candidate.model_copy(
                update={
                    "model_number": full_numbers[candidate.url],
                    "model_number_shortened": False,
                }
            )

    listings = [
        Candidate(
            platform=Platform.CROMA,
            url=url,
            title="SONY BRAVIA 2 II 109 cm (43 inch) 4K Ultra HD LCD Smart Android TV",
            brand="Sony",
            model_number="BRAVIA2",
            model_number_shortened=True,
            attributes={"screen_size": "43 inch"},
            availability=Availability.IN_STOCK,
        )
        for url in full_numbers
    ]
    result = await search_marketplace(Croma(Platform.CROMA, candidates=listings), tv)
    assert result.status == ResultStatus.IN_STOCK
    assert result.url == "https://c/316033"
    assert result.model_number == "K-43S22M2"
