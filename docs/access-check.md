# Marketplace access check

Checked on 2026-11-05 from a home connection in India.
Re-run from any deploy host with `cd backend && uv run python scripts/access_check.py`.

| Site | Plain httpx | What works |
|---|---|---|
| Amazon.in | OK | Product HTML has `#productTitle`, breadcrumb (category), `#productOverview_feature_div` (brand, RAM), `#availability`, `#landingImage`. Storage often only appears in the title. |
| Flipkart | OK | Search HTML lists product links (`/p/itm...`). Each card carries spec bullets (e.g. "12 GB RAM \| 256 GB ROM") and "Currently unavailable" when out of stock. Product pages show "Buy now" or "Notify Me". |
| Myntra | OK, with session | JSON API `/gateway/v2/search/<query>` returns brand, `primaryColour`, `landingPageUrl` and per-size `inventoryInfo`. Returns 401 unless the client first loads the homepage to get session cookies, as a browser would. |
| Croma | Blocked | Akamai returns 403 for httpx and for headless Chromium. A real Chrome browser got through once and was blocked on the next request. |

## Decisions

- Amazon, Flipkart, Myntra: plain httpx + BeautifulSoup / JSON. No Playwright needed.
- Croma: the adapter calls Croma's search API with httpx. When Akamai blocks the
  request, the result is `failed` with reason `blocked`, never `not_listed`.
  Parsing is tested against saved fixtures so the adapter is ready if access works
  from the deploy host.
- Datacenter IPs (Render, Railway, Fly) are blocked more often than home
  connections, so the check must be repeated after deployment.
