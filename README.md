# Product Finder

Paste an Amazon product link and see whether the exact same product is **in stock**,
**out of stock** or **not listed** on other Indian stores.

**Live:** https://product-finder-lyart.vercel.app (API: https://product-finder-api.vercel.app)

| Category | Searched on | Must match (besides brand and model) |
|---|---|---|
| Smartphones | Flipkart, Croma | RAM, storage |
| Televisions | Flipkart, Croma | Screen size |
| Sneakers | Flipkart, Myntra | Colour |
| T-shirts, polos, jerseys | Flipkart, Myntra | Colour |

- **How matching works, explained simply:** [docs/how-matching-works.md](docs/how-matching-works.md)
- **Scope, design and matching rules:** [SPEC.md](SPEC.md)
- **What each store allows, and from where:** [docs/access-check.md](docs/access-check.md)

## What you see

- The Amazon product appears as soon as it is read (about 2-3 seconds), then each
  store's card fills in as soon as that store finishes.
- A match shows the listing, its link, image and which checks passed. TVs also show
  the model number the match was made on.
- **Not listed** shows the closest listing and why it was rejected, for example
  "Storage mismatch: expected 256 GB, found 512 GB".
- **Could not check** means the store could not be searched (blocked, timeout, page
  not readable). It is never shown as "not listed". The card links to the store's
  own search so you can check yourself.
- Example buttons under the search box try a phone, a TV, a sold-out phone,
  sneakers and a polo.

### Stores that block automated requests

Stores treat home and cloud connections differently:

| | Live site (Vercel) | Running on a home connection |
|---|---|---|
| Amazon, Flipkart | Works | Works |
| Croma | Works | Blocked |
| Myntra | Blocked | Works |

The app reports a blocked store as "could not check" and does not try to get around
the block. Details in [docs/access-check.md](docs/access-check.md).

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (health check at `/health`)

## Run locally

Backend (Python 3.12, needs [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Frontend (Node 22+):

```bash
cd frontend
npm install
npm run dev
```

The frontend calls `http://localhost:8000` unless `NEXT_PUBLIC_API_URL` says otherwise,
and the backend accepts requests from `http://localhost:3000` unless `CORS_ORIGINS`
says otherwise. Settings are listed in [.env.example](.env.example).

## API

The website uses the streaming search, which sends each step as soon as it is known
(one JSON event per line):

```bash
curl -N -X POST localhost:8000/api/v1/search/stream \
  -H 'content-type: application/json' \
  -d '{"amazon_url": "https://www.amazon.in/dp/B0GWLJL55D"}'
# {"type": "accepted", "search_id": "..."}
# {"type": "product", "product": {...}, "platforms": ["flipkart", "croma"]}   ~2-3 s
# {"type": "result", "result": {"platform": "croma", ...}}                   as each store finishes
# {"type": "result", "result": {"platform": "flipkart", ...}}
# {"type": "completed"}
```

The same search is also available as a job you start and then poll:

```bash
curl -X POST localhost:8000/api/v1/search \
  -H 'content-type: application/json' \
  -d '{"amazon_url": "https://www.amazon.in/dp/B0GWLJL55D"}'
# -> 202 {"search_id": "...", "status": "pending", ...}

curl localhost:8000/api/v1/search/<search_id>
# -> {"status": "processing" | "completed" | "failed", "source_product": {...}, "results": [...]}
```

Each result has a `status` (`in_stock`, `out_of_stock`, `not_listed`, `failed`), and
`failed` results carry a `failure_reason` (`blocked`, `timeout`, `parse_error`,
`availability_unknown`, `unexpected`). An invalid link returns HTTP 400; an unknown
search id returns 404.

## Deployment

Both apps are on Vercel, as two projects connected to this repository (root
directories `backend` and `frontend`), so every push to `main` deploys both.

- `frontend/` is built with `NEXT_PUBLIC_API_URL=https://product-finder-api.vercel.app`.
- `backend/` runs FastAPI as a Vercel Function in Mumbai (`bom1`, see
  `backend/vercel.json`), with `CORS_ORIGINS` set to the frontend URL and
  `SEARCH_MODE=inline`.

The streaming search works the same on Vercel as locally, because the whole search
happens inside one request. The polling API is different: jobs live in memory, and
on serverless the next request may reach another instance, so `SEARCH_MODE=inline`
makes `POST /api/v1/search` wait and return the finished job there. Locally and in
Docker the default `background` mode returns at once.

## Tests and lint

```bash
cd backend
uv run pytest
uv run ruff check . && uv run ruff format --check .

cd ../frontend
npx tsc --noEmit && npm run lint
```

Tests use real pages and API responses saved in `backend/tests/fixtures/` and never
call live sites. To check which stores answer from a given machine:
`cd backend && uv run python scripts/access_check.py`.
