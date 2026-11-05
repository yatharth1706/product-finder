import httpx
import pytest

from app.errors import FetchError
from app.http import fetch, make_client
from app.schemas import FailureReason


def client_for(handler) -> httpx.AsyncClient:  # type: ignore[no-untyped-def]
    return make_client({"croma.com"}, transport=httpx.MockTransport(handler))


async def test_ok_response() -> None:
    async with client_for(lambda request: httpx.Response(200, text="ok")) as client:
        assert (await fetch(client, "https://api.croma.com/x")).text == "ok"


@pytest.mark.parametrize("status", [401, 403, 429, 503])
async def test_bot_protection_is_reported_as_blocked(status: int) -> None:
    async with client_for(lambda request: httpx.Response(status)) as client:
        with pytest.raises(FetchError) as exc:
            await fetch(client, "https://api.croma.com/x")
    assert exc.value.reason == FailureReason.BLOCKED


async def test_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    async with client_for(handler) as client:
        with pytest.raises(FetchError) as exc:
            await fetch(client, "https://api.croma.com/x")
    assert exc.value.reason == FailureReason.TIMEOUT


async def test_redirect_to_other_host_is_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.croma.com":
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest"})
        return httpx.Response(200, text="metadata")

    async with client_for(handler) as client:
        with pytest.raises(FetchError, match="host not allowed"):
            await fetch(client, "https://api.croma.com/x")
