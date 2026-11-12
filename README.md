# Reclaim

AI-powered lost-and-found recovery network. Start with [docs/00_START_HERE.md](docs/00_START_HERE.md).

| Path | What |
|---|---|
| [apps/api](apps/api) | FastAPI backend on PostgreSQL with an outbox worker: PayPal Sandbox checkout with verified webhooks (local mock without credentials), signed Zapier events, AI extraction through an OpenAI-compatible chat API (the demo runs a Qwen vision model on Groq) with a keyword fallback. See its README for setup, the endpoint walkthrough and the demo-day runbook. |
| [apps/web](apps/web) | Next.js frontend: every MVP screen for individuals and organisations, with Playwright end-to-end tests. See its README for setup and the **demo run sheet**. |
| [docs](docs) | Product and engineering handover pack |

Quick start for the API (needs Docker):

```bash
docker compose up -d db                       # Postgres on localhost:5433
cd apps/api && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/alembic upgrade head
ENABLE_DEV_ROUTES=true .venv/Scripts/python -m uvicorn app.main:app --reload --port 8000   # http://localhost:8000/docs
```
