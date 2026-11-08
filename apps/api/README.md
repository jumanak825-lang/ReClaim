# Reclaim API — stub backend

> **This is a temporary stub.** Data lives in memory: it is reseeded on every
> restart and on `POST /api/v1/dev/reset`. PayPal is mocked, the courier is
> simulated, and "AI" extraction and matching are keyword rules. The
> **request/response shapes are the real contract**. The real backend will
> keep them and swap the internals (`app/stub/`) for Postgres, a worker,
> PayPal Sandbox and a real extractor.

## Run it

Needs Python 3.12+.

```bash
cd apps/api
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs (sign in with `POST /auth/login`
  there and the cookie works for the rest of the page)
- OpenAPI JSON: http://localhost:8000/openapi.json, also committed as
  [openapi.json](openapi.json)
- Tests: `.venv/Scripts/python -m pytest -q`

Run a **single process**. Don't use `--workers`, because each process would
have its own in-memory data.

## Wiring the frontend

1. **Proxy `/api/*` to `http://localhost:8000`** (docs/11 §1). The browser then
   sees one origin and the `reclaim_session` HttpOnly cookie just works. In
   `next.config`:
   ```js
   async rewrites() { return [{ source: "/api/:path*", destination: "http://localhost:8000/api/:path*" }]; }
   ```
   Calling `:8000` directly from `localhost:3000` also works (CORS allows it with
   credentials), but use `credentials: "include"`.
2. **Types:** `npx openapi-typescript apps/api/openapi.json -o apps/web/lib/api/schema.d.ts`.
   Regenerate whenever `openapi.json` changes.
3. **Envelope:** every JSON response is `{ data, meta: { request_id, next_cursor } }`.
   Errors are `{ error: { code, message, details }, meta }`. Branch on
   `error.code`, not on the message. Validation errors are **400** `VALIDATION_ERROR`
   with `details.fields[] = { loc, message }`, which you can map to form fields.
4. **Pagination:** lists take `?limit=20&cursor=…`. Pass `meta.next_cursor` back
   as `cursor`. When it is `null`, there are no more pages.
5. **Server-decided UI:** reports, matches, claims and recoveries return
   `available_actions` (e.g. `["approve","reject","escalate"]`). Use it to show
   or hide buttons instead of re-deriving permissions on the client.

## Demo accounts

Password for all: **`reclaim-demo`** (also listed at `GET /api/v1/dev/demo-accounts`).

| Email | Who |
|---|---|
| `owner@reclaim.example` | Dana, the main demo user. Already has a lost backpack with a pending claim |
| `finder@reclaim.example` | Individual finder (holds a wallet) |
| `other@reclaim.example` | Unrelated user, for "permission denied" screens |
| `staff@harbourview.example` | Airport staff. Can see cases but **cannot** approve claims |
| `reviewer@harbourview.example` | Airport reviewer. Approves, rejects and escalates |
| `manager@harbourview.example` | Airport manager. Integrations and audit log |
| `reviewer@grandmeridian.example` | Hotel reviewer (other tenant). Can't see airport data |
| `manager@northgate.example` | Mall manager |

Seed content is in [seed/demo_seed.json](seed/demo_seed.json). You own the
content, so edit it and then hit `POST /api/v1/dev/reset`.

## The demo path, endpoint by endpoint

All paths are under `/api/v1`.

**1. Lost report wizard (as owner)**
- `POST /uploads` (multipart: `file`, `visibility=public_safe|private_evidence`) → `{ id, url }`
- `POST /reports/lost` with `as_draft: true` and `image_ids` → draft report
- `POST /reports/{id}/extract` (202), then poll `GET /reports/{id}/extraction`
  until `status: "completed"` (takes about 2s). Prefill the AI review step from it.
- `PATCH /reports/{id}` with the user's edits, then `POST /reports/{id}/submit`
- `GET /reports/{id}`: `processing_status` is `processing` for about 2s, then `completed`

To surface the seeded **target laptop**, report: category `electronics`, label
"Laptop", a description mentioning *silver* and *sticker*, location "Terminal
1, airport", lost yesterday, attribute `colour: silver`. The laptop scores as a
strong match and the silver tablet comes back as a weaker candidate.

**2. Matches**
- `GET /reports/{id}/matches` or `GET /matches/mine`, then `GET /matches/{id}`
- Show `score` as "AI relevance" next to `ownership_warning`.
- `POST /matches/{id}/dismiss` handles "Not my item".

**3. Claim**
- `GET /matches/{id}/verification-questions`
- `POST /matches/{id}/claims` `{ statement, answers: [{question_id, answer}], evidence_image_ids }`
- `GET /claims/{id}`, `GET /claims/mine`, `POST /claims/{id}/evidence`

**4. Review (as reviewer@harbourview)**
- `GET /organisations/{org}/claims?status=pending`
- `GET /claims/{id}`: reviewers also get `ai_assist` (label it as assistance), the answers and the evidence
- `POST /claims/{id}/review` `{ decision: approved|rejected|escalated, reason (≥10 chars) }`

**5. Recovery (as owner)**
- `POST /claims/{id}/recoveries` with `{ method: "collection" }` or
  `{ method: "delivery", address: {...} }`
- `GET /recoveries/{id}`: `timeline`, `delivery_quote`, `pickup_token`
  (claimant only), `available_actions`

**6. Delivery payment (mock PayPal)**
- `POST /payments/paypal/create-order` `{ recovery_id, idempotency_key: crypto.randomUUID() }`
- Redirect the browser to `approval_url`. That opens a mock checkout page on
  the API. Approve sends the browser to
  **`{APP}/checkout/paypal/return?token=<order_id>&recovery_id=…`**. Cancel
  sends it to **`/checkout/paypal/cancel?…`**. Build those two pages.
- On the return page: `POST /payments/paypal/capture-order { paypal_order_id: token }`,
  then refetch the recovery. Capture is idempotent, so it's safe to retry.
- Show a "Sandbox" badge (`payment.is_sandbox`).

**7. Fulfilment (as staff)**
- Delivery: `POST /recoveries/{id}/delivery/dispatch`. After about 20s it moves to
  `in_transit` on its own (or call `POST /dev/recoveries/{id}/advance-courier`).
  Then the owner calls `POST /recoveries/{id}/confirm-received` and the recovery is `completed`.
  Label the courier as simulated (`courier_is_simulated`).
- Collection: `POST /recoveries/{id}/collection/confirm` issues a pickup code,
  which only the owner sees. Staff then call `POST /recoveries/{id}/collection/validate-token { token }`,
  which completes the recovery.

**Organisation portal**
- `GET /me` → `memberships[]` drives the org switcher.
- `GET /organisations/{org}/overview`: summary cards (`is_seeded_demo_data` → show a label)
- `GET /organisations/{org}/cases?q=&status=&claim_status=&category=&location_id=&sort=-updated_at`: AG Grid rows
- `GET /organisations/{org}/cases/{caseId}`: case detail
- `GET /organisations/{org}/found-reports`, `/audit-logs`, `/integrations` (managers only)
- `POST /integrations/zapier/test { organisation_id }`

**Everyone**
- `GET /me/dashboard`: individual dashboard cards and recent activity
- `GET /notifications`, `GET /notifications/unread-count`,
  `POST /notifications/{id}/read`, `POST /notifications/read-all`
- `POST /auth/password/forgot` returns **501** `NOT_AVAILABLE_IN_DEMO`, as planned in docs/11

## Error codes you'll actually hit

`UNAUTHENTICATED` (401) · `INVALID_CREDENTIALS` (401) · `VALIDATION_ERROR` (400) ·
`FORBIDDEN`, `NOT_A_MEMBER`, `NOT_A_REVIEWER`, `INSUFFICIENT_ROLE` (403) ·
`*_NOT_FOUND` (404, also returned when you lack access, so private things don't leak) ·
`CLAIM_ALREADY_ACTIVE`, `CLAIM_NOT_REVIEWABLE`, `CLAIM_NOT_APPROVED`, `RECOVERY_EXISTS`,
`RECOVERY_INVALID_STATE`, `PAYMENT_NOT_APPROVED`, `IDEMPOTENCY_KEY_REUSED` (409) ·
`INVALID_PICKUP_TOKEN` (400) · `FILE_SIGNATURE_MISMATCH`, `UNSUPPORTED_FILE_TYPE` (415) ·
`FILE_TOO_LARGE` (413) · `NOT_AVAILABLE_IN_DEMO` (501)

## Assumptions added on top of docs/05

These were needed for the screens and should be treated as part of the contract:

- `as_draft` + `POST /reports/{id}/submit`, so the wizard can run extraction before submitting.
- `GET /matches/mine`, `GET /matches/{id}/verification-questions`, `GET /me/dashboard`,
  `GET /organisations/{id}/overview|cases/{caseId}|found-reports`, plus the notifications
  and uploads routes.
- `found_location` on found reports for individual finders (the docs/11 spec fix).
- `in_transit` recovery state (docs/11 spec fix).
- One `ReportOut` shape for both lost and found reports (`report_type` tells them apart).
- Claims on items held by individual finders return 422 `CLAIM_NOT_SUPPORTED` for now.

## Layout

```
app/
  main.py            app, CORS, request-ID middleware, error handlers
  core/              config, envelope, errors
  schemas/           Pydantic DTOs = the contract (keep stable)
  routers/           thin HTTP layer
  stub/              in-memory store, seed loader, matcher, services  ← replace with real backend
seed/demo_seed.json  demo content
tests/               end-to-end demo path + permission checks
```
