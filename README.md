# Product Finder

Paste an Amazon product link and see whether the same product is in stock,
out of stock or not listed on Flipkart, Croma and Myntra.

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

## Tests and lint

```bash
cd backend
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
