"""Check whether each marketplace answers plain HTTP requests from this machine.

Run from any host you plan to deploy to:  uv run python scripts/access_check.py
Datacenter IPs are blocked far more often than home connections.
"""

import asyncio

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

CHECKS = {
    "amazon": ("https://www.amazon.in/dp/B0CS5XW6TN", "productTitle"),
    "flipkart": ("https://www.flipkart.com/search?q=samsung+galaxy+s24", "/p/itm"),
    "croma": (
        "https://api.croma.com/searchservices/v1/search?currentPage=0&query=samsung&fields=FULL",
        '"products"',
    ),
    "myntra": ("https://www.myntra.com/gateway/v2/search/nike%20shoes?rows=5", '"products"'),
}


async def check(client: httpx.AsyncClient, name: str, url: str, marker: str) -> None:
    try:
        response = await client.get(url)
        ok = response.status_code == 200 and marker in response.text
        print(f"{name:10} {'OK     ' if ok else 'BLOCKED'} http={response.status_code}")
    except httpx.HTTPError as exc:
        print(f"{name:10} ERROR   {type(exc).__name__}")


async def main() -> None:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
        # Myntra's search API needs the session cookies its homepage sets.
        await client.get("https://www.myntra.com/")
        await asyncio.gather(*(check(client, n, u, m) for n, (u, m) in CHECKS.items()))


if __name__ == "__main__":
    asyncio.run(main())
