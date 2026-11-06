# Product Finder — Spec

Paste an Amazon product link; the app finds the exact same product on other Indian
stores and reports, per store, whether it is in stock, out of stock or not listed.

## Scope

| Category | Search on | Must match (besides brand + model) |
|---|---|---|
| Smartphones | Flipkart, Croma | RAM, storage |
| Televisions | Flipkart, Croma | Screen size |
| Sneakers | Flipkart, Myntra | Colour |
| T-shirts, polos, jerseys | Flipkart, Myntra | Colour |

The category comes from the Amazon page's breadcrumb. Any other category is rejected
as unsupported.

Out of scope: accounts, databases, queues, price history, LLM-based matching.

## Result statuses (one per store)

| Status | Meaning |
|---|---|
| `in_stock` | Exact match found and purchasable. Link shown. |
| `out_of_stock` | Exact match found, cannot be bought now. Link shown. |
| `not_listed` | Search worked, no exact match among the listings checked. The closest listing and its rejection reasons are included. |
| `failed` | The store could not be checked. `failure_reason` says why: `blocked`, `timeout`, `parse_error`, `availability_unknown` (match found, stock unclear) or `unexpected`. |

A failed search is never reported as `not_listed`, and a listing is never called in
stock or out of stock without a clear signal from the store.

## Flow

```
SearchOrchestrator.stream(search_id, amazon_url) yields events:
  1. Read the Amazon page: title, breadcrumb (category), spec tables, image
     -> "product" event, with the stores that will be searched
  2. For each store of the category, at the same time:
       search -> drop repeated listings
       -> open up to 6 product pages, at the same time, for listings that could
          still match but lack a required detail (colour) or a stock status
       -> match every listing -> prefer one in stock, then one out of stock
     -> one "result" event per store, in the order the stores finish
  3. "completed"; every step is also recorded in the in-memory job store

POST /api/v1/search/stream {amazon_url}  ->  the events as NDJSON (used by the website)
POST /api/v1/search {amazon_url}         ->  202 job, runs in the background
GET  /api/v1/search/{search_id}          ->  the job: status, product, results so far
```

The Amazon step must come first, because the store searches need its brand, model
and attributes. Each store has its own time limit (30 s), and one store failing never
affects the others.

## Matching rules

1. **Brand** must be equal after normalization: case, spaces and known aliases are
   ignored ("One Plus" == "OnePlus", "Redmi" == "Xiaomi").
2. **Model** must match.
   - Televisions compare the manufacturer model number, because names like
     "Crystal 4K" are shared across sizes and years. Numbers must be identical,
     except that a shortened code of at least 7 characters that the full one starts
     with also counts: Croma lists `43NU870` for LG's `43NU870BPLA`.
   - Everything else compares the model name, read from the title (after the brand,
     before the first bracket, separator or size), or from Amazon's "Model Name" for
     shoes and clothing. Filler words ("5G", "Galaxy", "Smartphone", "Sneakers",
     "Men's", "Polo") are ignored and known brand abbreviations are expanded (Puma's
     "ESS" = "Essential"). Numbers and variant words (Pro, Ultra, Max, Lite, FE, ...)
     must be identical, the gender must agree when both sides state one, and the
     RapidFuzz similarity must be at least 92.
3. **Every category attribute** must be present on both sides and equal. A missing
   attribute is a failed check, never a pass.
   - RAM / storage: normalized sizes ("12GB RAM" == "12 GB").
   - Screen size: inches ("138 cm (55 inch)" == "55 Inches").
   - Colour: mapped to basic colours ("Desert Dust" -> beige, "Wolf Grey" -> grey,
     adidas codes like "CGRANI" -> grey). The main colour must be equal, and when both
     sides list several colours the sets must be equal. Unknown colour words never
     match.
4. **Score** (brand 25, model 35, attributes 40) only ranks listings that already
   passed every check. A high score never overrides a failed check.
5. Every decision returns its checks and the reasons for any rejection.

## Stores

| Store | Search | Stock |
|---|---|---|
| Flipkart | Search page HTML (one card per listing). Fashion cards have no colour, so it is read from the product page's schema.org data. | "Currently unavailable" on the card, or `InStock` / `OutOfStock` in the product page's schema.org data. |
| Croma | The search API Croma's website uses (query ending in `:relevance`). | `stockFlag`: the stores holding stock; empty means out of stock. |
| Myntra | The search page's embedded results (`window.__myx`). Sneaker searches add "Shoes", which Myntra's search needs. | Stock per size: in stock if any size is available. |

Search text is brand + model, except TVs, which use the start of the Amazon title
(stores do not index model numbers well). Each store's own search link is returned
with every result. How each store responds from home and cloud connections is in
[docs/access-check.md](docs/access-check.md).

## Known limitations

- Myntra refuses cloud servers, so on the live site it reports `blocked`. Croma
  refuses home connections, so it reports `blocked` when run locally.
- Flipkart clothing titles rarely contain the model name ("PUMA Solid Men Polo Neck
  Blue T-Shirt"), so clothing is usually `not_listed` on Flipkart.
- Myntra search results give one main colour, so two colourways with the same main
  colour (white/black vs white/green) cannot be told apart there.
- iPhones: Apple does not publish RAM, so the Amazon page fails extraction.
- Only the first page of each store's search results is checked.
- Jobs live in memory and are lost when the backend restarts.

## Backend layout

```
backend/app/
  main.py                 FastAPI app, logging
  api.py                  routes
  config.py               settings from env
  schemas.py              Product, Candidate, MarketplaceResult, SearchEvent, SearchJob, enums
  errors.py               InvalidUrlError, ExtractionError, FetchError
  http.py                 shared HTTP client: host allowlist, timeouts, block detection
  job_store.py            in-memory job store
  extractors/amazon.py    URL validation, fetch, parse, category
  marketplaces/
    base.py               MarketplaceAdapter: search(), get_details(), search_page_url()
    flipkart.py  croma.py  myntra.py
  matching/
    normalizer.py         sizes, colours, brands, model names
    matcher.py            per-category rules, score, reasons
  orchestrator.py         runs the search and streams its steps
backend/scripts/          access_check.py: which stores answer from this machine
backend/tests/            unit and fixture tests on saved pages and API responses
frontend/                 Next.js page: search box, Amazon product, one card per store
```

## Security

- Only Amazon links are accepted (`amazon.in`, `amazon.com` and the `amzn.*` short
  links). Short links are followed and the final page must still be on Amazon.
- Store URLs are built by the backend, never taken from user input.
- Every outbound request, including each redirect, must go to an allowed host, so a
  redirect cannot reach an internal address.
- All outbound requests have timeouts. Internal errors are not sent to the client.
- No attempt is made to get around CAPTCHAs or bot protection.

## Build order

1. Access check and project skeleton.
2. Smartphones end to end: Amazon -> Flipkart -> matching -> API -> basic UI.
3. Croma, concurrent searches, partial failures.
4. Televisions, sneakers, clothing; Myntra.
5. Deployment on Vercel, streamed results, UI polish.
6. "Explain it to a 5-year-old" matching document.
