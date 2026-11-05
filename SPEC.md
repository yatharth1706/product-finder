# Product Finder — Spec

Paste an Amazon product link; the app finds the same product on other Indian
marketplaces and reports, per marketplace, whether it is in stock, out of stock
or not listed.

## Scope

| Category | Search on | Must match (besides brand + model) |
|---|---|---|
| Smartphones | Flipkart, Croma, Reliance Digital | RAM, storage |
| Televisions | Flipkart, Croma, Reliance Digital | Screen size |
| Sneakers | Flipkart, Myntra | Colour |
| T-shirts, polos, jerseys | Flipkart, Myntra | Colour |

Any other Amazon category is rejected as unsupported.

Reliance Digital is an addition to the assignment's list: Croma blocks server
requests, so it gives the electronics categories a second store that works.

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
POST /api/v1/search {amazon_url}  ->  202 {search_id}
  background task:
    1. Amazon extractor: fetch page, read title, breadcrumb (category), spec tables
    2. Normalize attributes (units, colours, brand names)
    3. For each marketplace of the category, concurrently:
         search -> match every listing -> open up to 3 exact matches
         until one is confirmed in stock (else out of stock / unknown)
    4. Store results in the job store
GET /api/v1/search/{search_id}  ->  {status, source_product, results}
```

## Matching rules

1. Brand must be equal after normalization.
2. Model must match. The model is read from the title (after the brand, before the
   first bracket or separator) and filler words like "5G" or "Galaxy" are ignored.
   Numbers and variant words (Pro, Ultra, Max, FE, ...) must be identical, and the
   RapidFuzz similarity of the rest must be at least 92.
3. Every category attribute must be present on both sides and equal.
   A missing attribute is a failed check, never a pass.
4. Score (brand 25, model 35, attributes 40) only ranks candidates that already
   passed every check. A high score never overrides a failed check.
5. Every decision returns its checks and the reasons for any rejection.

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
    base.py               MarketplaceAdapter: search(), check_availability()
    flipkart.py  croma.py  reliance_digital.py  myntra.py
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
3. Croma (reports blocked) + Reliance Digital, concurrent searches, partial failures.
4. Televisions, then Myntra with sneakers and clothing.
5. Deploy, UI polish.
6. "Explain it to a 5-year-old" matching document.
