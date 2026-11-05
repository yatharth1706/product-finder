from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api import get_job_store, get_orchestrator
from app.job_store import JobStore
from app.main import app
from app.orchestrator import SearchOrchestrator
from app.schemas import Availability, Platform
from tests.fakes import PRODUCT, FakeAdapter, listing


@pytest.fixture
def client() -> Iterator[TestClient]:
    async def fake_extract(url: str):  # type: ignore[no-untyped-def]
        return PRODUCT

    store = JobStore()
    adapter = FakeAdapter(candidates=[listing(availability=Availability.OUT_OF_STOCK)])
    orchestrator = SearchOrchestrator(store, {Platform.FLIPKART: adapter}, extract=fake_extract)
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_search_lifecycle(client: TestClient) -> None:
    response = client.post("/api/v1/search", json={"amazon_url": PRODUCT.url})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"

    # TestClient runs background tasks before returning, so the job is already done.
    job = client.get(f"/api/v1/search/{body['search_id']}").json()
    assert job["status"] == "completed"
    assert job["source_product"]["model"] == "Galaxy S25 Ultra"
    assert job["results"][0]["platform"] == "flipkart"
    assert job["results"][0]["status"] == "out_of_stock"


def test_rejects_non_amazon_url(client: TestClient) -> None:
    response = client.post("/api/v1/search", json={"amazon_url": "https://example.com/dp/X"})
    assert response.status_code == 400


def test_unknown_search_id(client: TestClient) -> None:
    assert client.get("/api/v1/search/does-not-exist").status_code == 404
