import time

import pytest

from app.errors import ExtractionError
from app.job_store import JobStore
from app.orchestrator import CATEGORY_PLATFORMS, SearchOrchestrator, search_marketplace
from app.schemas import Availability, Category, FailureReason, JobStatus, Platform, ResultStatus
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
    assert adapter.availability_checks == []


async def test_not_listed_when_no_exact_match() -> None:
    adapter = FakeAdapter(candidates=[listing(storage="512 GB")])
    result = await search_marketplace(adapter, PRODUCT)
    assert result.status == ResultStatus.NOT_LISTED
    assert result.candidates_checked == 1


async def test_unknown_availability_is_not_reported_as_in_or_out_of_stock() -> None:
    adapter = FakeAdapter(candidates=[listing()])
    result = await search_marketplace(adapter, PRODUCT)
    assert result.status == ResultStatus.FAILED
    assert result.failure_reason == FailureReason.AVAILABILITY_UNKNOWN
    assert result.url == "https://www.flipkart.com/s25"


async def test_availability_checks_are_bounded() -> None:
    adapter = FakeAdapter(candidates=[listing(url=f"https://f/{i}") for i in range(10)])
    await search_marketplace(adapter, PRODUCT)
    assert len(adapter.availability_checks) == 3


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
