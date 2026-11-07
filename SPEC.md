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
       -> open product pages only where they change the answer: for exact
          matches with unknown stock, one at a time until one is in stock (max 3);
          for shoes missing their colour, up to 6, three at a time
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
     "Crystal 4K" are shared across sizes and years. Flipkart lists full model
     numbers, which must be identical (`K-55S25B`, the 2024 model, is not
     `K-55S25BM2`). Croma lists shortened ones (`43NU870` for `43NU870BPLA`,
     `55S25M2` for `K-55S25BM2`): accepted when the short code's characters appear
     in order in the full one and all its digits are the same. When the short code
     doesn't settle it (all three 43-inch Sony BRAVIA 2 II listings show "BRAVIA2"),
     the product page is opened for the full model number (`K-43S25M2`,
     `K-43S22BM2`, `K-43S22M2`).
   - Phones compare the model name from the title (after the brand, before the first
     bracket, separator or size). Filler words ("5G", "Galaxy", "Smartphone") are
     ignored, numbers and variant words (Pro, Ultra, Max, Lite, FE, ...) must be
     identical, and the RapidFuzz similarity must be at least 92. A phone sold as 5G
     needs a listing that says 5G, because stores drop "4G" from 4G models' names.
     Apple never publishes iPhone RAM (it is fixed per model), so Apple phones match on
     model and storage. Among equal matches, one in the Amazon product's colour ranks
     first.
   - Sneakers: every word of the model must appear in the listing's title, since
     stores add words ("Revolution 8 Road Running Shoes"). Numbers, variant words and
     gender (when both sides state one) must still be identical.
   - Clothing: the assignment says brand, model and colour must match, but clothing
     listings rarely name a model. Decision: for clothing, the "model" is the
     identifying words of the name ("TIRO 23", "teamLIGA", "ESS Logo", "025"), and a
     listing with no identifying words is not a match. A wrong product is worse than
     a missed one: Flipkart's closest listing for the Man United 24/25 Home jersey
     (adidas IU1397) is the 25/26 Fan jersey (KR2562), same colour, different product.
     Clothing names are mostly description ("Men Solid Polo Neck Pure Cotton Slim Fit
     T-Shirt"). Description words, sizes and colours are dropped on both sides, and
     the identifying words left must be the same: "TIRO 23 JSY Printed" matches
     "TIRO 23", "ESS Logo Graphic" does not match "ESS Logo". Searches use those words
     plus the garment type ("Puma teamLIGA Jersey").
   - Shoes and clothes take the model from the title, or from Amazon's "Model Name"
     when that reads like a name: stock codes (`M9166c-black-9`, `IU1397`) and
     trailing sizes ("ESS Logo Polo M") are ignored. Known brand abbreviations are
     expanded (Puma's "ESS" = "Essential").
3. **Every category attribute** must be present on both sides and equal. A missing
   attribute is a failed check, never a pass.
   - RAM / storage: normalized sizes ("12GB RAM" == "12 GB").
   - Screen size: inches ("138 cm (55 inch)" == "55 Inches").
   - Colour: mapped to basic colours ("Desert Dust" -> beige, "Wolf Grey" -> grey,
     codes like adidas "CGRANI" or Skechers "MVE"). The main colour must be equal,
     and when both sides list several colours the sets must be equal. Brand colour
     names with no known colour word ("Shimmer") match only the same main word.
4. **Score** (brand 25, model 35, attributes 40) only ranks listings that already
   passed every check. A high score never overrides a failed check.
5. Every decision returns its checks and the reasons for any rejection.

## Stores

| Store | Search | Stock |
|---|---|---|
| Flipkart | Search page HTML (one card per listing); phone searches name RAM and storage. Fashion cards have no colour: it comes from the product page's schema.org data, and the same search with Flipkart's colour filter marks listings in the product's main colour, which are opened first and used as a fallback when a page is rate-limited. | From the search card: "Currently unavailable" is out of stock, a price is in stock. |
| Croma | The search API Croma's website uses (query ending in `:relevance`); product pages (`window.__INITIAL_DATA__`) for TVs' full model numbers. | `stockFlag`: the stores holding stock; empty means out of stock. |
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
- Clothing listings often carry no model name (Myntra's Levi's 025 is "Levis Men Soft
  Pure Cotton Round Neck Tshirt"), and stores do not show the brand's style code, so
  those tops are `not_listed`.
- Flipkart rate-limits product pages from shared cloud addresses. Phones and TVs do not
  need them. Shoes and clothes read them through a relay: the same backend deployed on
  Fly.io, which has its own address. Without the relay they fall back to the colour
  filter's main colour, and a store whose needed pages were blocked reports `blocked`,
  never `not_listed`.
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
                          benchmark.py: score against 20 hand-checked products
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
