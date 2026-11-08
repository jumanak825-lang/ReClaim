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

The home page shows the live API status, which confirms the proxy works.

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
| `npm run test:e2e` | Playwright end-to-end tests. Starts the stub API (needs `apps/api/.venv`) and the dev server if they aren't already running, and resets the API's demo data first. First time only: `npx playwright install chromium`. |

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
