# Reclaim

AI-powered lost-and-found recovery network. Start with [docs/00_START_HERE.md](docs/00_START_HERE.md).

| Path | What |
|---|---|
| [apps/api](apps/api) | FastAPI backend on PostgreSQL with an outbox worker. PayPal orders are still mocked. See its README for setup and the endpoint walkthrough. |
| [apps/web](apps/web) | Next.js frontend. Foundation in place: proxy to the API, typed client and design tokens. See its README. |
| [docs](docs) | Product and engineering handover pack |

Quick start for the API (needs Docker):

```bash
docker compose up -d db                       # Postgres on localhost:5433
cd apps/api && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/alembic upgrade head
ENABLE_DEV_ROUTES=true .venv/Scripts/python -m uvicorn app.main:app --reload --port 8000   # http://localhost:8000/docs
```
