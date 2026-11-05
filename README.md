# Product Finder

Paste an Amazon product link and find the exact same product on Flipkart, Croma and Myntra,
with its stock status on each.

| Category | Searched on | Must also match (besides brand + model) |
|---|---|---|
| Smartphones | Flipkart, Croma | RAM, storage |
| Televisions | Flipkart, Croma | Screen size |
| Sneakers | Flipkart, Myntra | Colour |
| T-shirts, polos, jerseys | Flipkart, Myntra | Colour |

**Status:** Milestone 0 (project foundation) only. No search functionality yet.

## Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2, httpx, BeautifulSoup, RapidFuzz
- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind CSS v4, shadcn/ui, TanStack Query, Zod

## Run with Docker

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (health check at `/health`, OpenAPI docs at `/docs`)

## Run locally

Backend:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Checks

```bash
cd backend && pytest && ruff check . && ruff format --check .
```

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

## Layout

```text
backend/app/
  api/routes/     HTTP endpoints only, no business logic
  core/           config, logging, exceptions, constants
  schemas/        shared Pydantic models
  services/       extraction, normalization, matching, orchestration
  marketplaces/   one adapter per marketplace
  repositories/   in-memory search store
backend/tests/    unit/, integration/, fixtures/ (saved HTML)
frontend/         app/, components/, hooks/, lib/, types/
```
