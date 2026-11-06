# Marketplace access check

Which stores answer the backend's requests, and from where. Re-run from any machine
with `cd backend && uv run python scripts/access_check.py`, which sends the same
requests as the adapters.

## From a home connection in India

Checked on 2026-11-05 and 2026-11-06.

| Site | Result | What the backend reads |
|---|---|---|
| Amazon.in | OK | Product HTML: `#productTitle`, breadcrumb (category), spec tables (`#productOverview_feature_div`, `table.prodDetTable`, detail bullets), the colour picker, `#landingImage`. Storage often appears only in the title. |
| Flipkart | OK | Search HTML: one `div[data-id]` card per listing. Electronics cards carry spec bullets ("12 GB RAM \| 256 GB ROM", "Model ID: UA55...") and "Currently unavailable" when out of stock. Fashion cards carry brand and title but no colour. Product pages include schema.org Product data (JSON-LD) with colour and `InStock` / `OutOfStock`. |
| Myntra | OK | The search page (`/nike-air-max-bia-shoes?rawQuery=...`) embeds its results as JSON (`window.__myx`): brand, `primaryColour`, `landingPageUrl` and per-size `inventoryInfo`. (The JSON API `/gateway/v2/search/...` has the same data but needs session cookies from the homepage first.) |
| Croma | Blocked | Akamai returns 403 "Access Denied" for plain HTTP and for headless Chromium. A real Chrome browser got through once and was blocked on the next request. |

## From Vercel (Mumbai, `bom1`)

Checked on 2026-11-05 and 2026-11-06 against the deployed backend.

| Site | Result |
|---|---|
| Amazon.in | OK |
| Flipkart | OK |
| Croma | OK. The search API answers once `query` ends with `:relevance`, as on Croma's website (without it: HTTP 400 "Invalid Search Request"). Listings carry name, link, image, manufacturer, a shortened model code in `summary`, and `stockFlag` (the stores holding stock; empty means out of stock). |
| Myntra | Refused, for both the search page and the JSON API: a fake "Site Maintenance" page (HTTP 200) while the site works from a home connection. Reported as `blocked`. |

## Decisions

- Every store is read with plain HTTP requests (httpx) and BeautifulSoup or JSON.
  No headless browser is needed.
- A refused request is reported as `blocked` and never as `not_listed`. Refusals are
  recognised by status code (401, 403, 429, 503), by Akamai's "Access Denied" page,
  and by Myntra's fake maintenance page.
- No attempt is made to get around a block (rotating proxies, browser fingerprinting,
  CAPTCHA solving). Blocked stores get a "Search on <store> yourself" link instead.
- The Croma parser was built from real responses captured on Vercel, saved in
  `backend/tests/fixtures/croma/`. Until then, every Croma request had been blocked
  and the request format could not be checked.

## How other projects handle this

Open-source price comparison projects run into the same blocks:

- Projects that read Myntra from a server route their requests through paid scraping
  services (Scrape.do, Scrapingdog, Apify), which send them from residential
  connections. That is deliberately getting around Myntra's bot protection, which
  this project avoids.
- Others run only locally, drive a real browser (Playwright), or drive the stores'
  mobile apps on cloud phones.
- At least one FastAPI project left Croma out entirely after hitting the same 403.
