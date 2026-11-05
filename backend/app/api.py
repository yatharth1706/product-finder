from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from app.config import settings
from app.errors import InvalidUrlError
from app.extractors.amazon import validate_amazon_url
from app.job_store import JobStore
from app.marketplaces.croma import CromaAdapter
from app.marketplaces.flipkart import FlipkartAdapter
from app.marketplaces.myntra import MyntraAdapter
from app.marketplaces.reliance_digital import RelianceDigitalAdapter
from app.orchestrator import SearchOrchestrator
from app.schemas import Platform, SearchJob, SearchRequest

router = APIRouter(prefix="/api/v1")

job_store = JobStore()
orchestrator = SearchOrchestrator(
    store=job_store,
    adapters={
        Platform.FLIPKART: FlipkartAdapter(),
        Platform.CROMA: CromaAdapter(),
        Platform.RELIANCE_DIGITAL: RelianceDigitalAdapter(),
        Platform.MYNTRA: MyntraAdapter(),
    },
)


def get_job_store() -> JobStore:
    return job_store


def get_orchestrator() -> SearchOrchestrator:
    return orchestrator


StoreDep = Annotated[JobStore, Depends(get_job_store)]
OrchestratorDep = Annotated[SearchOrchestrator, Depends(get_orchestrator)]


@router.post("/search", status_code=status.HTTP_202_ACCEPTED)
async def create_search(
    request: SearchRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    store: StoreDep,
    search: OrchestratorDep,
) -> SearchJob:
    try:
        amazon_url = validate_amazon_url(request.amazon_url)
    except InvalidUrlError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    job = store.create(amazon_url)
    if settings.search_mode == "inline":
        await search.run(job.search_id, amazon_url)
        response.status_code = status.HTTP_200_OK
    else:
        background_tasks.add_task(search.run, job.search_id, amazon_url)
    return job


@router.get("/search/{search_id}")
async def get_search(search_id: str, store: StoreDep) -> SearchJob:
    job = store.get(search_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Search not found")
    return job
