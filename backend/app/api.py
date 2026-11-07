import hmac
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from app.config import settings
from app.errors import FetchError, InvalidUrlError
from app.extractors.amazon import validate_amazon_url
from app.job_store import JobStore
from app.marketplaces.croma import CromaAdapter
from app.marketplaces.flipkart import FlipkartAdapter, is_product_url, read_product_page
from app.marketplaces.myntra import MyntraAdapter
from app.orchestrator import SearchOrchestrator
from app.schemas import Platform, SearchEvent, SearchJob, SearchRequest

router = APIRouter(prefix="/api/v1")

job_store = JobStore()
orchestrator = SearchOrchestrator(
    store=job_store,
    adapters={
        Platform.FLIPKART: FlipkartAdapter(),
        Platform.CROMA: CromaAdapter(),
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


@router.post("/search/stream")
async def stream_search(
    request: SearchRequest, store: StoreDep, search: OrchestratorDep
) -> StreamingResponse:
    """The same search, sent as it happens: one JSON event per line (NDJSON).

    The Amazon product arrives first, then each marketplace result as soon as that
    marketplace finishes, so the page can fill in progressively.
    """
    try:
        amazon_url = validate_amazon_url(request.amazon_url)
    except InvalidUrlError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    job = store.create(amazon_url)

    async def events() -> AsyncIterator[str]:
        yield SearchEvent(type="accepted", search_id=job.search_id).model_dump_json() + "\n"
        async for event in search.stream(job.search_id, amazon_url):
            yield event.model_dump_json() + "\n"

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/relay/flipkart-product")
async def relay_flipkart_product(
    url: str, x_relay_token: Annotated[str, Header()] = ""
) -> dict[str, str | None]:
    """Colour and stock of one Flipkart product page, for the other deployment of this
    backend. Only Flipkart product pages, only with the shared token: not an open proxy."""
    if not settings.relay_token or not hmac.compare_digest(x_relay_token, settings.relay_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    if not is_product_url(url):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "only Flipkart product pages")
    try:
        colour, availability = await read_product_page(url)
    except FetchError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, exc.reason.value) from exc
    return {"colour": colour, "availability": availability.value}


@router.get("/search/{search_id}")
async def get_search(search_id: str, store: StoreDep) -> SearchJob:
    job = store.get(search_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Search not found")
    return job
