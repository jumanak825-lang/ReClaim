# Reclaim web

Next.js 16 (App Router, TypeScript), Tailwind 4, shadcn/ui (Radix, Nova preset), TanStack Query.

> Next.js 16 differs from older versions. Check `node_modules/next/dist/docs/`
> before relying on older patterns (see [AGENTS.md](AGENTS.md)).

## Run it

Start the API first (see [apps/api/README.md](../api/README.md)), then:

```bash
cd apps/web
cp .env.example .env.local   # optional; defaults to http://localhost:8000
npm install
npm run dev                  # http://localhost:3000
```

Sign in with a demo account (password `reclaim-demo`). See the run sheet below.

## What's built

| Area | Screens |
|---|---|
| Public & auth | Landing, sign in, register, password-reset notice |
| Individuals | Dashboard, lost and found report wizards (drafts, AI suggestions), report detail, My reports, matches, claim with private questions and evidence, My claims, recovery choice, recovery timeline, PayPal return/cancel, pickup code, notifications |
| Organisations | Overview with location selector and priority queue, Operations (AG Grid), case detail, claim queue and review, recovery management, audit log, integrations |

Labelled as such in the UI: PayPal **Sandbox** (mocked locally when no PayPal credentials are set), **simulated** courier, keyword-based extraction when no AI key is set, and **seeded demo data**.

## How it talks to the API

- The browser calls same-origin `/api/*`. `next.config.ts` proxies that to
  `API_BASE_URL`, so the `reclaim_session` HttpOnly cookie is first-party.
- Types are generated from the API contract. Regenerate them whenever
  `apps/api/openapi.json` changes:
  ```bash
  npm run gen:api   # writes lib/api/schema.d.ts
  ```
- Use `api` from `lib/api/client.ts` (typed `openapi-fetch`).
  - `unwrap(api.GET(...))` returns the envelope's `data`, or throws an
    `ApiError` with the server's stable `code`. Branch on `code`, never on
    `message`.
  - `unwrapRaw(...)` is for responses without the envelope, such as health.

## Scripts

| Command | What |
|---|---|
| `npm run dev` | Dev server |
| `npm run build` | Production build (also type-checks) |
| `npm run lint` | ESLint |
| `npm run gen:api` | Regenerate API types |
| `npm run test:e2e` | Playwright end-to-end tests against the real API. Needs Postgres running and migrated (`docker compose up -d db`, then `alembic upgrade head`; see apps/api/README.md). Starts the API with `ENABLE_DEV_ROUTES=true` and `RATE_LIMITS_ENABLED=false`, plus the dev server, unless they're already running. **If you already run the API yourself, start it with both of those set**, or resets fail and sign-ins hit the rate limit. Resets all demo data. First time only: `npx playwright install chromium`. |

## Auth

- `proxy.ts` sends visitors without a `reclaim_session` cookie on `/dashboard`,
  `/report/*` and `/org/*` to `/sign-in?next=…`. That's only a quick first
  check.
- The real check is `AuthGate` (`components/auth/auth-gate.tsx`). It calls
  `GET /me` and sends a 401 to sign-in, so the API stays authoritative.
- `next` is only honoured for paths on this site (`lib/safe-next.ts`), so it
  can't be used for an open redirect.
- `/org/[orgSlug]` pages check the slug against the user's memberships and
  show a permission-denied state otherwise. The API still enforces
  membership on every request.

## Design tokens

Colours live as CSS variables in `app/globals.css` (docs/02 §2.1):
- Teal primary on a light neutral canvas, with navy text.
- `success` (green) for completed states, `warning` (amber) for pending
  review, `destructive` (red) for errors only.

Change the brand colours there, not in components.

## Demo run sheet

The story from [docs/10_HACKATHON_DEMO.md](../../docs/10_HACKATHON_DEMO.md). It is also an automated test: `npx playwright test e2e/demo.spec.ts`.

**Before you start:** API running with `ENABLE_DEV_ROUTES=true`, then reset the data with `POST /api/v1/dev/reset` (Swagger at http://localhost:8000/docs). In PowerShell:

```powershell
cd apps\api
$env:ENABLE_DEV_ROUTES="true"; $env:RATE_LIMITS_ENABLED="false"; .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

`RATE_LIMITS_ENABLED=false` avoids the 10-sign-ins-per-minute limit while switching accounts on stage. Never expose the API (e.g. through ngrok) with dev routes on.

| Act | Who | Steps |
|---|---|---|
| 1. Report lost | `owner@reclaim.example` | **Report lost** → Electronics, "Laptop", mention *silver* and *sticker*, colour silver → "Terminal 1, airport", yesterday → add a photo and a private mark → review suggestions → privacy summary → submit |
| 2. Found inventory | `staff@harbourview.example` | **Operations** grid; open the Terminal 1 laptop case (storage reference visible to staff only). **Log found item** shows the staff wizard |
| 3. AI candidate | owner | Report page → **View possible matches** → the Terminal 1 laptop. Point out "AI relevance … not proof of ownership" and that hidden details aren't shown |
| 4. Verify | owner, then `reviewer@harbourview.example` | **Claim this item** → describe the sticker and dent privately → submit. Reviewer: **Claims** → open it → AI assistance (not a decision) → **Approve** with a reason → **Audit log** shows it |
| 5. Pay | owner | Bell → "Claim approved" → **Choose collection or delivery** → delivery address → price → **Pay with PayPal (Sandbox)** → approve → server-confirmed payment |
| 6. Deliver | staff, then owner | Staff: recovery → **Dispatch (simulated courier)**. Courier moves to in transit automatically (or `POST /api/v1/dev/recoveries/{id}/advance-courier`). Owner: **I've received my item** → case closed |

Zapier: as `manager@harbourview.example`, **Integrations** → **Send test event** (needs `ZAPIER_WEBHOOK_URL` on the API).

**Known gap:** the overview's summary cards don't follow the location selector yet (needs `location_id` on `GET /organisations/{id}/overview`); the priority queue and Operations grid do.
