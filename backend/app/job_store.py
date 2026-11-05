import uuid
from datetime import UTC, datetime

from app.schemas import JobStatus, MarketplaceResult, Product, SearchJob


class JobStore:
    """Keeps search jobs in memory. Jobs are lost when the process restarts."""

    def __init__(self) -> None:
        self._jobs: dict[str, SearchJob] = {}

    def create(self, source_url: str) -> SearchJob:
        job = SearchJob(
            search_id=str(uuid.uuid4()),
            status=JobStatus.PENDING,
            source_url=source_url,
            created_at=datetime.now(UTC),
        )
        self._jobs[job.search_id] = job
        return job

    def get(self, search_id: str) -> SearchJob | None:
        return self._jobs.get(search_id)

    def mark_processing(self, search_id: str) -> None:
        self._jobs[search_id].status = JobStatus.PROCESSING

    def save_source_product(self, search_id: str, product: Product) -> None:
        self._jobs[search_id].source_product = product

    def complete(self, search_id: str, results: list[MarketplaceResult]) -> None:
        job = self._jobs[search_id]
        job.results = results
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(UTC)

    def fail(self, search_id: str, error: str) -> None:
        job = self._jobs[search_id]
        job.error = error
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(UTC)
