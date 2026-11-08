# Reclaim

AI-powered lost-and-found recovery network. Start with [docs/00_START_HERE.md](docs/00_START_HERE.md).

| Path | What |
|---|---|
| [apps/api](apps/api) | FastAPI backend. **Currently a stub** (in-memory, seeded, mocked PayPal). See its README for how to run it and the endpoint walkthrough. |
| [apps/web](apps/web) | Next.js frontend. Foundation in place: proxy to the API, typed client and design tokens. See its README. |
| [docs](docs) | Product and engineering handover pack |

Quick start for the API:

```bash
cd apps/api && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000   # http://localhost:8000/docs
```
