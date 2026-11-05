# Product Finder

Paste an Amazon product link and see whether the same product is in stock,
out of stock or not listed on Flipkart, Croma, Reliance Digital and Myntra.

Croma blocks requests from servers, so it reports "could not check"; see
[docs/access-check.md](docs/access-check.md).

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

## Tests and lint

```bash
cd backend
uv run pytest
uv run ruff check . && uv run ruff format --check .

cd ../frontend
npx tsc --noEmit && npm run lint
```

Tests use saved pages in `backend/tests/fixtures/` and never call live sites.
