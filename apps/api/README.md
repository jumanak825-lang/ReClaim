# Reclaim API

FastAPI on PostgreSQL, with an outbox worker for background jobs. The
request/response shapes are the contract in [openapi.json](openapi.json).

**What's simulated, and labelled as such in responses:**
- Payments use **PayPal Sandbox** (Orders v2) when `PAYPAL_CLIENT_ID` and
  `PAYPAL_CLIENT_SECRET` are set. Without them, a **local mock checkout** is used
  (needs `ENABLE_DEV_ROUTES=true`). Either way `payment.is_sandbox` is `true`: no real money.
- The courier is **simulated** (`courier_is_simulated: true`, timeline events
  have `is_simulated: true`).
- Extraction uses **keyword rules** unless an AI key is configured
  (`is_fallback: true`). Match scores are unvalidated demo values.

## Run it

Needs Python 3.12+ and Docker.

```bash
# from the repo root: Postgres on localhost:5433 (5432 is often taken by a local install)
docker compose up -d db

cd apps/api
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # macOS/Linux: .venv/bin/pip
.venv/Scripts/alembic upgrade head                 # create/upgrade the schema
ENABLE_DEV_ROUTES=true .venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

In PowerShell, run `$env:ENABLE_DEV_ROUTES="true"` first, then the uvicorn command.

- With dev routes on, an **empty** database is seeded automatically at startup.
  To wipe and reseed at any time, run `.venv/Scripts/python -m app.seed` or call
  `POST /api/v1/dev/reset`. Both delete **all** data.
- `GET /api/v1/health` checks the process is up. `GET /api/v1/ready` returns 503
  until the database is reachable and migrations are current.
- Swagger UI: http://localhost:8000/docs
- Tests: `.venv/Scripts/python -m pytest -q`. They use a separate `reclaim_test`
  database (created by Compose) and never touch the dev data.

**`ENABLE_DEV_ROUTES`** turns on `/api/v1/dev/*`: reset, demo accounts, the mock
PayPal checkout and the courier shortcut. It is **off by default**, and those
routes return 404 when it's off. Turn it on for local development and for the
Playwright e2e run (`ENABLE_DEV_ROUTES=true npx playwright test`). Never turn it
on while the API is reachable from outside your machine, for example through ngrok.

### Background worker

Submitting a report, requesting extraction and every integration event go into
the `outbox_events` table. A worker processes them with retries
(exponential backoff, then `dead` after `WORKER_MAX_ATTEMPTS`).

- **`WORKER_MODE=embedded`** (default): the API process runs the worker itself.
  Nothing else to start locally.
- **`WORKER_MODE=external`**: run `python -m app.workers` as a separate process
  (Render worker service). Several workers can run at once, because rows are
  claimed with `FOR UPDATE SKIP LOCKED`.

A newly submitted report shows `processing_status: "processing"` until the
worker has run extraction and matching. That takes about a second locally, so poll
`GET /reports/{id}`.

## Wiring the frontend

1. **Proxy `/api/*` to `http://localhost:8000`** (docs/11 §1). The browser then
   sees one origin and the `reclaim_session` HttpOnly cookie just works.
2. **Types:** `npm run gen:api` in `apps/web` (reads [openapi.json](openapi.json)).
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
6. **Rate limits:** login/register (per IP and per email), uploads and claim
   submission return **429** `RATE_LIMITED` with a `Retry-After` header.

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

Seed content is in [seed/demo_seed.json](seed/demo_seed.json). The frontend owns
the content; edit it, then reseed.

## The demo path, endpoint by endpoint

All paths are under `/api/v1`.

**1. Lost report wizard (as owner)**
- `POST /uploads` (multipart: `file`, `visibility=public_safe|private_evidence`) → `{ id, url }`
- `POST /reports/lost` with `as_draft: true` and `image_ids` → draft report
- `POST /reports/{id}/extract` (202), then poll `GET /reports/{id}/extraction`
  until `status: "completed"`. Prefill the AI review step from it, and show
  `disclaimer` (it says whether the result is AI or the keyword fallback).
- `PATCH /reports/{id}` with the user's edits, then `POST /reports/{id}/submit`
- `GET /reports/{id}`: `processing_status` is `processing` until the worker runs, then `completed`

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
- `GET /recoveries/{id}`: `timeline`, `delivery_quote`, `available_actions`

**6. Delivery payment (PayPal Sandbox, or the local mock)**
- `POST /payments/paypal/create-order` `{ recovery_id, idempotency_key: crypto.randomUUID() }`.
  Reuse the same key when retrying the same click; it returns the same order.
- Redirect the browser to `approval_url`: PayPal's Sandbox checkout, or the
  local mock page (signed-in payer only). Both send the browser back to
  **`{APP}/checkout/paypal/return?recovery_id=…&token=<order_id>`**
  (PayPal also adds `PayerID`), or to **`/checkout/paypal/cancel?recovery_id=…`**.
  Build those two pages.
- On the return page: `POST /payments/paypal/capture-order { paypal_order_id: token }`,
  then refetch the recovery. **Never treat the redirect itself as paid.**
  - `200` with `payment.status: "captured"`: paid, and the recovery is now `preparing`.
  - `200` with `"approved"` (funds pending at PayPal) or `"unknown"` (amount mismatch,
    flagged for staff): show "payment processing" and poll `GET /recoveries/{id}`.
  - `409 PAYMENT_NOT_APPROVED`: the buyer didn't finish on PayPal; offer to pay again.
  - `502 PAYMENT_PROVIDER_UNAVAILABLE`: PayPal didn't answer. The server reconciles
    with PayPal in the background, so poll the recovery for a minute.
  - Capture is idempotent, so retrying is safe.
- Show a "Sandbox" badge (`payment.is_sandbox`).

**7. Fulfilment**
- Delivery (staff): `POST /recoveries/{id}/delivery/dispatch`. The worker moves it to
  `in_transit` after `SIMULATED_COURIER_SECONDS` (20s by default) and notifies the owner.
  Staff can skip the wait with `POST /dev/recoveries/{id}/advance-courier`.
  Then the owner calls `POST /recoveries/{id}/confirm-received` and the recovery is `completed`.
  Label the courier as simulated (`courier_is_simulated`).
- Collection:
  1. Staff: `POST /recoveries/{id}/collection/confirm` → `ready_for_pickup`.
  2. Owner: when `available_actions` has `show_pickup_code`, call
     `POST /recoveries/{id}/collection/pickup-token`. The response's `pickup_token`
     (e.g. `K7QM-9XDA`) is the **only** place the code appears: the server
     stores just a hash, and `GET /recoveries/{id}` always returns `null`. Calling
     it again issues a new code and invalidates the old one.
  3. Staff: `POST /recoveries/{id}/collection/validate-token { token }` → `completed`.
     Codes are single-use, case-insensitive, and expire after 72h.

**Organisation portal**
- `GET /me` → `memberships[]` drives the org switcher.
- `GET /organisations/{org}/overview`: summary cards (`is_seeded_demo_data` → show a label)
- `GET /organisations/{org}/cases?q=&status=&claim_status=&category=&location_id=&sort=-updated_at`: AG Grid rows
- `GET /organisations/{org}/cases/{caseId}`: case detail
- `GET /organisations/{org}/found-reports`, `/audit-logs`, `/integrations` (managers only)
- `POST /integrations/zapier/test { organisation_id }` (managers only): queues a
  signed test event; `last_delivery` on `/integrations` shows the result.

**Everyone**
- `GET /me/dashboard`: individual dashboard cards and recent activity
- `GET /notifications`, `GET /notifications/unread-count`,
  `POST /notifications/{id}/read`, `POST /notifications/read-all`
- `POST /auth/password/forgot` returns **501** `NOT_AVAILABLE_IN_DEMO`, as planned in docs/11

## Error codes you'll actually hit

`UNAUTHENTICATED` (401) · `INVALID_CREDENTIALS` (401) · `VALIDATION_ERROR` (400) ·
`FORBIDDEN`, `NOT_A_MEMBER`, `NOT_A_REVIEWER`, `INSUFFICIENT_ROLE`, `LOCATION_OUT_OF_SCOPE` (403) ·
`*_NOT_FOUND` (404, also returned when you lack access, so private things don't leak) ·
`CLAIM_ALREADY_ACTIVE`, `CLAIM_NOT_REVIEWABLE`, `FOUND_ITEM_ALREADY_CLAIMED`, `CLAIM_NOT_APPROVED`,
`RECOVERY_EXISTS`, `RECOVERY_INVALID_STATE`, `PICKUP_TOKEN_EXPIRED`, `PAYMENT_NOT_APPROVED`,
`IDEMPOTENCY_KEY_REUSED` (409) · `INVALID_PICKUP_TOKEN` (400) · `RATE_LIMITED` (429) ·
`FILE_SIGNATURE_MISMATCH`, `UNSUPPORTED_FILE_TYPE` (415) · `FILE_TOO_LARGE` (413) ·
`NOT_AVAILABLE_IN_DEMO` (501)

## Contract decisions on top of docs/05

These were needed for the screens and are part of the contract:

- `as_draft` + `POST /reports/{id}/submit`, so the wizard can run extraction before submitting.
- `GET /matches/mine`, `GET /matches/{id}/verification-questions`, `GET /me/dashboard`,
  `GET /organisations/{id}/overview|cases/{caseId}|found-reports`, plus the notifications
  and uploads routes.
- `POST /recoveries/{id}/collection/pickup-token`: pickup codes are stored hashed
  (docs/04 `pickup_token_hash`), so the claimant reveals a fresh code on demand.
- `found_location` on found reports for individual finders (the docs/11 spec fix).
- `in_transit` recovery state (docs/11 spec fix).
- One `ReportOut` shape for both lost and found reports (`report_type` tells them apart).
- Claims on items held by individual finders return 422 `CLAIM_NOT_SUPPORTED` for now.
- **One approved owner per found item** (FR-019). Approving a second claim on the same
  item returns 409 `FOUND_ITEM_ALREADY_CLAIMED`. Other pending claims stay pending,
  with no `approve` action and a warning in `ai_assist`, until a reviewer rejects them.
  A partial unique index in Postgres backs this up against concurrent approvals.
- **Location scope** (FR-017, FR-029). Staff whose membership lists `location_ids` only
  see reports, claims, recoveries, review-queue entries and notifications for those
  locations. Anything else returns 404. Recording a found item at another location
  returns 403 `LOCATION_OUT_OF_SCOPE`. An empty `location_ids` means all locations.
- `PATCH /reports/{id}`: omit a field to leave it unchanged. Explicit `null` is
  rejected (400) for `category`, `item_label`, `description` and `last_location`.
  A `lost_at_end` earlier than `lost_at_start` is rejected (400), including when
  the request sends only one of them.

## Backend design notes

**Security (review item 5)**
- Passwords: argon2id. Session cookies: random tokens, stored as SHA-256 only;
  rotated on login, deleted on logout.
- Rate limits: fixed windows in Postgres (`rate_limit_buckets`), shared by all
  processes. Failed attempts count even though their request rolls back. The client
  IP is the first `X-Forwarded-For` hop, because the web app proxies `/api`.
- Registration with an existing email returns 409, which reveals that the account
  exists. **Accepted for the hackathon**: without email verification there is no
  neutral response that also signs the user in. It's mitigated by the rate limits.
  Revisit when email verification lands.
- PayPal (docs/07 §7.2): OAuth client credentials. The order amount and currency come
  from the stored quote. `PayPal-Request-Id` is sent on create and capture.
  Capture checks PayPal's status, amount and currency before the recovery advances.
  A wrong amount marks the payment `unknown` and writes an audit entry; it never
  advances. A network error during capture queues a `payment.reconcile` job that
  asks PayPal for the order and applies the result. A capture that arrives after
  the recovery was cancelled is recorded and flagged to managers for a manual
  refund (refunds aren't automated).
- PayPal webhooks: verified with PayPal's `verify-webhook-signature` API using
  `PAYPAL_WEBHOOK_ID`. Unverified → 400. Not configured → 503 (never accepted
  unverified). Deduplicated on `(provider, provider_event_id)`. Only ids, statuses
  and amounts are stored (`payload_redacted`). Handles `PAYMENT.CAPTURE.COMPLETED`
  and `PAYMENT.CAPTURE.DENIED`.
- Logging: one access line per request (request id, method, path, status, duration;
  no query strings or bodies). Uvicorn's own access log is off, and `httpx` logs
  only warnings, because a Zapier hook URL is a secret. A test checks that passwords,
  session cookies, claim text, PayPal credentials and the Zapier URL never reach the logs.
- Zapier: events in the outbox are POSTed to `ZAPIER_WEBHOOK_URL` with
  `X-Reclaim-Event-Id`, `X-Reclaim-Timestamp` and
  `X-Reclaim-Signature: v1=<hex HMAC-SHA256(secret, "{timestamp}.{body}")>`.
  Only `match.high_priority`, `claim.created` and `integration.test` are sent
  (the two hackathon Zaps). Payloads carry ids, references and statuses only.
  Failures retry and never change claim or payment state. Retries reuse the same
  event id. Receivers verify with `app.integrations.zapier.verify()`, which checks the
  HMAC and rejects timestamps older than 5 minutes, and drop repeated event ids (see the
  runbook below).

**AI extraction**: `AI_PROVIDER=xai` with `AI_API_KEY` and `AI_VISION_MODEL` calls
xAI's chat completions API with a strict JSON schema. Only `public_safe` images are
sent. With no key, or on any error, the deterministic fallback runs instead.
Confirm the model id and pricing on docs.x.ai before setting it (docs/11 §7).
**The xAI call has only been tested against a mocked HTTP response, not the live API.**

**Schema deviations from docs/04** (deliberate):
- One `reports` table with `report_type` instead of separate lost/found tables:
  same lifecycle, one DTO, simpler matching. A check constraint enforces that a
  found report has a custodian.
- `claims.found_report_id` is denormalised so a partial unique index can enforce FR-019.
- Claim decision history comes from `audit_logs` rather than a separate table.
- `recoveries.delivery_address` is JSONB, not encrypted, for the hackathon.
- No `payouts` or `integration_endpoints` tables (cut in docs/11 §2; Zapier is configured from env).

**Migrations**: `alembic revision --autogenerate -m "..."`, then **review the file**.
Alembic silently drops `use_alter` foreign keys inside `create_table`, and it did here.
Run `alembic check` to confirm the models and migrations agree.

## Security checklist (docs/08 §8.11)

| Check | Covered by |
|---|---|
| User cannot access another user's private report | `test_full_delivery_flow` (404 for `other@`) |
| Staff cannot access an unassigned organisation | `test_full_delivery_flow`, `test_cases_filters_sort_pagination_and_scope` |
| Staff cannot access a location outside their scope | `test_reviewer_limited_to_one_location` |
| Public match response excludes private attributes | `test_public_match_and_found_views_exclude_private_values` |
| Finder cannot read claimant answers | `test_full_delivery_flow` (non-reviewer staff get no answers/evidence) |
| Non-reviewer cannot decide a claim | `test_full_delivery_flow` (`NOT_A_REVIEWER`) |
| AI response cannot change claim status | by design (`ai_assist` is read-only); `test_extraction_never_overwrites_user_fields` |
| Payment amount cannot be changed by client | `test_client_cannot_set_amount`, `test_create_order_uses_quote_and_is_idempotent` |
| Invalid PayPal webhook signature is rejected | `test_webhook_bad_or_missing_signature_rejected` |
| Duplicate PayPal webhook is idempotent | `test_webhook_captures_once_and_dedupes` |
| Duplicate capture request does not double charge | `test_capture_requires_approval_then_captures_once` |
| Zapier signature/replay checks work | `test_zapier_signature_verification`, `test_zapier_events_signed_and_free_of_private_data` |
| Expired pickup token is rejected | `test_expired_pickup_token_rejected` |
| Upload validation rejects disguised executables | `test_disguised_executable_rejected` |
| Secrets and evidence do not appear in logs | `test_logs_contain_no_secrets` |

## Runbook: PayPal Sandbox and the webhook tunnel (Day 3)

The hackathon runs the API on a laptop and exposes only what PayPal needs through
ngrok's free static domain (docs/11 §1). No Render deploy.

1. **Sandbox app.** Get the Sandbox app's client id and secret from the frontend
   developer, who creates the Sandbox accounts (docs/11 §3). Keep them in your
   local environment only, never in git.
   ```bash
   export PAYPAL_CLIENT_ID=...  PAYPAL_CLIENT_SECRET=...
   .venv/Scripts/python scripts/check_paypal.py      # "OAuth OK" means the credentials work
   ```
2. **Tunnel.** Install ngrok, add your authtoken, claim the free static domain, then:
   ```bash
   ngrok http --url=<your-static-domain>.ngrok-free.app 8000
   ```
   The tunnel exposes the **whole API**, so start the API with
   `ENABLE_DEV_ROUTES=false` while it's up. Reset the demo with
   `python -m app.seed` instead of the dev route.
3. **Webhook.** In the PayPal developer dashboard (Sandbox app → Webhooks), add
   `https://<your-static-domain>.ngrok-free.app/api/v1/payments/paypal/webhook`
   with the events `PAYMENT.CAPTURE.COMPLETED` and `PAYMENT.CAPTURE.DENIED`. Copy the
   webhook id into `PAYPAL_WEBHOOK_ID`. The domain is static, so you register it only
   once; re-register if it ever changes (docs/11 §7).
4. **Check.** Run a delivery checkout with the Sandbox buyer account. The recovery
   should move to `preparing`, and the webhook should appear in `webhook_events`
   with `processing_status` `processed` (or `ignored` if the browser capture got there first).

**Zapier.** Create a Catch Hook Zap. Set `ZAPIER_WEBHOOK_URL` to its URL and
`ZAPIER_WEBHOOK_SECRET` to a long random string. Then call
`POST /api/v1/integrations/zapier/test` as a manager. Zapier is outbound only, so no tunnel is needed.
To verify signatures inside the Zap, add a Code step that computes
`HMAC-SHA256(secret, X-Reclaim-Timestamp + "." + raw body)` and compares it with
`X-Reclaim-Signature` (after `v1=`). Skip events older than 5 minutes, and dedupe on
`X-Reclaim-Event-Id`, using a Zapier storage step or a Sheet lookup.

## Layout

```
app/
  main.py            app, CORS, request-ID + access-log middleware, embedded worker
  core/              config, envelope, errors, rate limiting
  db/                SQLAlchemy models, engine/session/transaction
  schemas/           Pydantic DTOs = the contract (keep stable)
  routers/           thin HTTP layer
  services/          domain logic: access, auth, reports, matching, claims, recoveries,
                     payments, notifications, events (audit/outbox), presenters (DTOs)
  integrations/      storage (local disk), ai (xAI + fallback), paypal, zapier
  workers/           outbox worker (`python -m app.workers`)
  seed.py            seed loader / reset (`python -m app.seed`)
migrations/          Alembic
seed/demo_seed.json  demo content (owned by frontend)
tests/               API tests against the reclaim_test database
```
