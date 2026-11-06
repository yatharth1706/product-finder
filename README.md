# Product Finder

Paste an Amazon product link and see whether the same product is in stock,
out of stock or not listed on Flipkart, Croma and Myntra.

**Live:** https://product-finder-lyart.vercel.app (API: https://product-finder-api.vercel.app)

Stores block automated requests differently. The live site (on Vercel) reaches
Amazon, Flipkart and Croma, but Myntra refuses cloud servers, so it shows
"could not check" there. Run the backend locally to see Myntra, and see
[docs/access-check.md](docs/access-check.md) for details.

**How matching works, explained simply:** [docs/how-matching-works.md](docs/how-matching-works.md)

See [SPEC.md](SPEC.md) for scope and design, and
[docs/access-check.md](docs/access-check.md) for what each marketplace allows.

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (health check at `/health`)

## Run locally

Backend (needs [uv](https://docs.astral.sh/uv/)):

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

## API

```bash
curl -X POST localhost:8000/api/v1/search \
  -H 'content-type: application/json' \
  -d '{"amazon_url": "https://www.amazon.in/dp/B0DSKNQW8F"}'
# -> 202 {"search_id": "...", "status": "pending"}

curl localhost:8000/api/v1/search/<search_id>
# -> {"status": "completed", "source_product": {...}, "results": [...]}
```

## Deployment

Both apps are on Vercel, as two projects:

- `frontend/` builds with `NEXT_PUBLIC_API_URL=https://product-finder-api.vercel.app`.
- `backend/` runs FastAPI as a Vercel Function in Mumbai (`bom1`, see
  `backend/vercel.json`) with `SEARCH_MODE=inline` and `CORS_ORIGINS` set to the
  frontend URL.

`SEARCH_MODE=inline` makes `POST /api/v1/search` wait and return the finished
search (about 5-10 seconds). Searches live in memory, and on serverless the next
request may reach a different instance, so polling would not be reliable there.
Locally and in Docker the default `background` mode returns at once and the
frontend polls `GET /api/v1/search/{id}`. The frontend handles both.

Both Vercel projects are connected to this repository (root directories
`backend` and `frontend`), so every push to `main` deploys both.

## Tests and lint

```bash
cd backend
uv run pytest
uv run ruff check . && uv run ruff format --check .

cd ../frontend
npx tsc --noEmit && npm run lint
```

Tests use saved pages in `backend/tests/fixtures/` and never call live sites.
