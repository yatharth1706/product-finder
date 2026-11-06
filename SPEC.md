# Product Finder — Spec

Paste an Amazon product link; the app finds the same product on other Indian
marketplaces and reports, per marketplace, whether it is in stock, out of stock
or not listed.

## Scope

| Category | Search on | Must match (besides brand + model) |
|---|---|---|
| Smartphones | Flipkart, Croma | RAM, storage |
| Televisions | Flipkart, Croma | Screen size |
| Sneakers | Flipkart, Myntra | Colour |
| T-shirts, polos, jerseys | Flipkart, Myntra | Colour |

Any other Amazon category is rejected as unsupported.

Out of scope: auth, databases, queues, price history, LLM-based matching.

## Result statuses (one per marketplace)

| Status | Meaning |
|---|---|
| `in_stock` | Exact match found and purchasable. Link shown. |
| `out_of_stock` | Exact match found, cannot be bought now. Link shown. |
| `not_listed` | Search worked, no exact match among the results checked. |
| `failed` | Search could not be completed. Carries a reason: `blocked`, `timeout` or `parse_error`. |

A failed search is never reported as `not_listed`.

## Flow

```
SearchOrchestrator.stream(search_id, amazon_url) yields events:
  1. Amazon extractor: fetch page, read title, breadcrumb (category), spec tables
     -> "product" event (with the marketplaces that will be searched)
  2. For each marketplace of the category, concurrently:
       search -> drop repeated listings
       -> open up to 6 product pages of listings that could still match but lack
          a required detail (colour) or a stock status
       -> match every listing -> prefer in stock, then out of stock
          (not listed: keep the closest listing and its rejection reasons)
     -> one "result" event per marketplace, in the order they finish
  3. "completed"; every step is also recorded in the job store

POST /api/v1/search/stream {amazon_url}  ->  the events as NDJSON (used by the website)
POST /api/v1/search {amazon_url}         ->  202 {search_id}, runs in the background
GET  /api/v1/search/{search_id}          ->  {status, source_product, results so far}
```

## Matching rules

1. Brand must be equal after normalization ("One Plus" == "OnePlus", "Redmi" == "Xiaomi").
2. Model must match.
   - Televisions: the manufacturer model number must be identical (`UA55M2EHAULXL`).
     Model names like "Crystal 4K" are shared across sizes and years.
   - Everything else: the model name is read from the title (or Amazon's "Model Name"
     for fashion). Filler words ("5G", "Galaxy", "Sneakers", "Men's") are ignored.
     Numbers and variant words (Pro, Ultra, Max, Lite, FE, ...) must be identical,
     the gender must agree when both sides state one, and the RapidFuzz similarity
     must be at least 92.
3. Every category attribute must be present on both sides and equal.
   A missing attribute is a failed check, never a pass.
   - RAM / storage: normalized sizes ("12GB RAM" == "12 GB").
   - Screen size: inches ("138 cm (55 inch)" == "55 Inches").
   - Colour: mapped to basic colours ("Desert Dust" -> beige, "Wolf Grey" -> grey).
     Main colour must be equal; when both sides list several colours, the sets must
     be equal. Unknown colour words never match.
4. Score (brand 25, model 35, attributes 40) only ranks candidates that already
   passed every check. A high score never overrides a failed check.
5. Every decision returns its checks and the reasons for any rejection.

## Known limitations

- Myntra refuses cloud servers, so on the live site (Vercel) it reports `blocked`.
  Croma refuses home connections but answers from Vercel.
- Flipkart clothing titles rarely contain the model name ("PUMA Solid Men Polo Neck
  Blue T-Shirt"), so clothing is usually `not_listed` on Flipkart.
- Myntra search results give one primary colour, so two colourways with the same
  main colour (white/black vs white/green) cannot be told apart there.
- iPhones: Apple does not publish RAM, so the Amazon page fails extraction.
- Only the first page (about 24 listings) of each search is checked.

## Backend layout

```
backend/app/
  main.py                 FastAPI app, logging
  api.py                  routes
  config.py               settings from env
  schemas.py              Product, Candidate, MarketplaceResult, SearchJob, enums
  errors.py               InvalidUrlError, ExtractionError, FetchError
  http.py                 shared HTTP client with host allowlist
  job_store.py            in-memory job store
  extractors/amazon.py    URL validation, fetch, parse, category
  marketplaces/
    base.py               MarketplaceAdapter
    flipkart.py  croma.py  myntra.py
                          search(), get_details()
  matching/
    normalizer.py         units, colours, brands
    matcher.py            per-category rules, score, reasons
  orchestrator.py         runs the pipeline, builds results
backend/tests/            matcher tests, parser tests on saved HTML fixtures
frontend/                 Next.js page: input, source product, result cards
```

## Security

- Only `https` Amazon hosts (`amazon.in`, `amazon.com`, `amzn.in`, `amzn.to`, ...) are accepted.
  Short links are followed and the final host must still be Amazon.
- Marketplace URLs are built by the backend, never taken from user input.
- All outbound requests have timeouts. Internal errors are not sent to the client.
- No attempt is made to get around CAPTCHAs or bot protection.

## Milestones

1. Access check + project skeleton.
2. Smartphones end to end: Amazon -> Flipkart -> matching -> API -> basic UI.
3. Croma, concurrent searches, partial failures.
4. Televisions, sneakers, clothing; Myntra.
5. Deploy, UI polish.
6. "Explain it to a 5-year-old" matching document.
