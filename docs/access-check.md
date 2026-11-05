# Marketplace access check

Checked on 2026-11-05 from a home connection in India.
Re-run from any deploy host with `cd backend && uv run python scripts/access_check.py`.

| Site | Plain httpx | What works |
|---|---|---|
| Amazon.in | OK | Product HTML has `#productTitle`, breadcrumb (category), `#productOverview_feature_div` (brand, RAM), `#availability`, `#landingImage`. Storage often only appears in the title. |
| Flipkart | OK | Search HTML has one `div[data-id]` card per listing. Electronics cards carry spec bullets ("12 GB RAM \| 256 GB ROM", "Model ID: UA55...") and "Currently unavailable" when out of stock. Fashion cards carry brand and title but no colour. Product pages include schema.org Product data (JSON-LD) with colour and `InStock` / `OutOfStock`. |
| Myntra | OK, with session | JSON API `/gateway/v2/search/<query>` returns brand, `primaryColour`, `landingPageUrl` and per-size `inventoryInfo`. Returns 401 unless the client first loads the homepage to get session cookies, as a browser would. |
| Croma | Blocked | Akamai returns 403 for httpx and for headless Chromium. A real Chrome browser got through once and was blocked on the next request. |
| Reliance Digital | OK | Search pages embed the listing data as JSON (`window.__INITIAL_STATE__`): brand, colour, storage, `sellable` flag. `sellable` is false exactly when stock quantity is 0. 12 listings per page (`page_no=N`). |

## From Vercel (Mumbai, `bom1`)

Checked on 2026-11-05 against the deployed backend.

| Site | Result |
|---|---|
| Amazon.in | OK |
| Flipkart | OK |
| Reliance Digital | OK |
| Croma | Refused (HTTP 400) |
| Myntra | Refused: returns a fake "Site Maintenance" page (HTTP 200) while the site works from a home connection. Reported as `blocked`. |

## Decisions

- Amazon, Flipkart, Myntra: plain httpx + BeautifulSoup / JSON. No Playwright needed.
- Croma: the adapter calls Croma's search API with httpx. When Akamai blocks the
  request, the result is `failed` with reason `blocked`, never `not_listed`.
  The response parser is not written: we have no real Croma response to build it
  from. If a request ever succeeds, the result is `parse_error` instead of a guess.
  To finish it, save a Croma search API response from a browser into
  `backend/tests/fixtures/croma/` and write the parser against it.
- Reliance Digital was added as an extra electronics store for smartphones and
  televisions, so the electronics categories have a second working source while
  Croma is blocked. Croma still appears in every result.
- Datacenter IPs (Render, Railway, Fly) are blocked more often than home
  connections, so the check must be repeated after deployment.
