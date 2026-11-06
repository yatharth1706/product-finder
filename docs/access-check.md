# Marketplace access check

Checked on 2026-11-05 from a home connection in India.
Re-run from any deploy host with `cd backend && uv run python scripts/access_check.py`.

| Site | Plain httpx | What works |
|---|---|---|
| Amazon.in | OK | Product HTML has `#productTitle`, breadcrumb (category), `#productOverview_feature_div` (brand, RAM), `#availability`, `#landingImage`. Storage often only appears in the title. |
| Flipkart | OK | Search HTML has one `div[data-id]` card per listing. Electronics cards carry spec bullets ("12 GB RAM \| 256 GB ROM", "Model ID: UA55...") and "Currently unavailable" when out of stock. Fashion cards carry brand and title but no colour. Product pages include schema.org Product data (JSON-LD) with colour and `InStock` / `OutOfStock`. |
| Myntra | OK | The search page (`/nike-air-max-bia`) embeds its results as JSON (`window.__myx`): brand, `primaryColour`, `landingPageUrl` and per-size `inventoryInfo`. The JSON API (`/gateway/v2/search/...`) has the same data but needs session cookies from the homepage first. |
| Croma | Blocked | Akamai returns 403 for httpx and for headless Chromium from a home connection. A real Chrome browser got through once and was blocked on the next request. |

## From Vercel (Mumbai, `bom1`)

Checked on 2026-11-05 against the deployed backend.

| Site | Result |
|---|---|
| Amazon.in | OK |
| Flipkart | OK |
| Croma | OK. The search API answers once `query` ends with `:relevance`, as on Croma's website (without it: HTTP 400 "Invalid Search Request"). Listings carry name, link, image, a shortened model code in `summary`, and `stockFlag` (stores holding stock; empty means out of stock). |
| Myntra | Refused, for both the search page and the JSON API: returns a fake "Site Maintenance" page (HTTP 200) while the site works from a home connection. Reported as `blocked`. |

## Decisions

- Amazon, Flipkart, Myntra: plain httpx + BeautifulSoup / JSON. No Playwright needed.
- Croma: the adapter calls the same search API as Croma's website. From a home
  connection Akamai blocks it, which is reported as `blocked`; from Vercel it
  answers. The parser was built from responses captured on Vercel and saved in
  `backend/tests/fixtures/croma/`.
- Datacenter IPs (Render, Railway, Fly) are blocked more often than home
  connections, so the check must be repeated after deployment.
