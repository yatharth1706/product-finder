import asyncio

import httpx

from app.config import settings
from app.errors import FetchError
from app.schemas import FailureReason

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

BLOCKED_STATUS_CODES = {401, 403, 429, 503}


def host_allowed(host: str, allowed_hosts: set[str]) -> bool:
    return any(host == allowed or host.endswith("." + allowed) for allowed in allowed_hosts)


def make_client(
    allowed_hosts: set[str], transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    """An HTTP client that refuses to contact any host outside `allowed_hosts`.

    The check runs on every request, including redirects, so a redirect cannot
    send us to an internal address.
    """

    async def check_host(request: httpx.Request) -> None:
        if not host_allowed(request.url.host, allowed_hosts):
            raise FetchError(FailureReason.BLOCKED, f"host not allowed: {request.url.host}")

    return httpx.AsyncClient(
        headers=BROWSER_HEADERS,
        follow_redirects=True,
        max_redirects=5,
        timeout=settings.request_timeout_seconds,
        event_hooks={"request": [check_host]},
        transport=transport,
    )


# One retry after "429 Too Many Requests", waiting as the store asks (capped).
MAX_RETRY_WAIT_SECONDS = 3.0


async def fetch(client: httpx.AsyncClient, url: str, retry: bool = True) -> httpx.Response:
    try:
        response = await client.get(url)
    except httpx.TimeoutException as exc:
        raise FetchError(FailureReason.TIMEOUT, url) from exc
    except httpx.HTTPError as exc:
        raise FetchError(FailureReason.UNEXPECTED, f"{type(exc).__name__} for {url}") from exc

    if response.status_code == 429 and retry:
        try:
            wait = float(response.headers.get("retry-after", 1))
        except ValueError:
            wait = 1.0
        await asyncio.sleep(min(wait, MAX_RETRY_WAIT_SECONDS))
        return await fetch(client, url, retry=False)
    if response.status_code >= 400:
        snippet = " ".join(response.text[:200].split())
        detail = f"HTTP {response.status_code} for {url}: {snippet}"
        if response.status_code in BLOCKED_STATUS_CODES or is_bot_protection_page(response):
            raise FetchError(FailureReason.BLOCKED, detail)
        raise FetchError(FailureReason.UNEXPECTED, detail)
    return response


def is_bot_protection_page(response: httpx.Response) -> bool:
    """Akamai, used by several stores, refuses with its own 'Access Denied' page."""
    return response.headers.get("server", "").startswith("AkamaiGHost") or (
        "Access Denied" in response.text and "edgesuite.net" in response.text
    )
