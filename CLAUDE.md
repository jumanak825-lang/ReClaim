# Claude Code Instructions --- Reclaim

You are implementing **Reclaim**, an AI-powered interconnected
lost-and-found recovery network. Read every document in this handover
pack before implementation. These documents are the product and
engineering source of truth.

## Operating rules

1.  **Inspect before changing.** First inspect the repository, package
    files, existing code, environment templates and deployment
    configuration. Do not overwrite an existing working implementation
    without explaining why.
2.  **Build in milestones.** Follow `09_IMPLEMENTATION_PLAN.md` in
    order. Implement one milestone at a time and report files changed,
    commands run, tests passed and remaining issues.
3.  **Do not invent product scope.** Use `01_PRODUCT_REQUIREMENTS.md`
    and `02_UX_AND_SCREEN_SPEC.md`. If a requirement is ambiguous,
    record the assumption or ask one focused question.
4.  **Backend is authoritative.** Never trust client-side role claims,
    ownership decisions, payment status, webhook payloads, or AI match
    scores.
5.  **AI is advisory.** AI can extract attributes, rank candidate
    matches and flag inconsistencies. It must never autonomously approve
    ownership, release an item, capture a payment, or issue a payout.
6.  **Privacy by default.** Never expose private evidence, full contact
    details, exact storage location, serial numbers or hidden item
    attributes in public listings or to unauthorised users.
7.  **Payments are server-controlled.** Keep PayPal credentials on the
    backend. Verify order/capture state with PayPal and verify webhook
    signatures. Use idempotency. Never mark a payment paid based only on
    a browser redirect.
8.  **No escrow claims.** Delivery checkout and finder reward payout are
    separate operations. Do not describe Reclaim as holding funds in
    escrow.
9.  **Zapier is not the database.** Use backend outbox events and signed
    integration endpoints. Zapier failures must not corrupt core
    workflow state.
10. **Prefer simple, maintainable engineering.** Use a modular monolith.
    Avoid premature microservices, unnecessary abstractions and
    speculative features.
11. **Do not silently add paid dependencies.** Identify pricing, account
    requirements and alternatives before introducing a paid service.
12. **No fake production claims.** Clearly label simulated courier
    tracking, sandbox payments, seeded demo data and unvalidated AI
    scores.
13. **Tests matter.** Add tests for permissions, claim state
    transitions, payment idempotency, webhook verification, match
    ranking and tenant isolation.
14. **Keep documentation current.** Update README, `.env.example`,
    migrations, API docs and setup instructions whenever implementation
    changes them.

## Preferred stack

-   Web: Next.js, TypeScript, App Router.
-   UI: Tailwind CSS and shadcn/ui where appropriate.
-   Data fetching: TanStack Query or the existing project convention.
-   Operations table: AG Grid Community.
-   API: Python FastAPI.
-   Database: PostgreSQL.
-   Background work: a worker process with a persistent queue/outbox
    pattern. Do not rely on in-memory background tasks for critical
    work.
-   Hosting: Render.
-   Images: S3-compatible storage, Cloudinary or Supabase Storage. Keep
    provider access behind a storage adapter.
-   AI: provider-agnostic interfaces for vision/text extraction and
    embeddings.
-   Payments: PayPal REST APIs.
-   Automation: Zapier webhooks.

## Engineering conventions

-   Use UUID primary keys.
-   Store timestamps as UTC `timestamptz`; convert for display using the
    relevant location/user timezone.
-   Store money as integer minor units plus ISO currency code. Never use
    floating point for money.
-   Use database transactions for multi-step state changes.
-   Use explicit enums/constants for workflow statuses.
-   Validate all request bodies with Pydantic.
-   Use pagination on list endpoints.
-   Apply organisation/location access checks in the backend on every
    request.
-   Use structured logs with request IDs. Never log passwords, tokens,
    private claim evidence or full payment credentials.
-   Keep provider-specific code in integration modules.
-   Use migrations; do not rely on automatic schema creation in
    production.
-   Keep public DTOs separate from internal database models.
-   Use a transactional outbox for notifications/integration events
    where practical.

## Required first response

Before editing: 1. Summarise the existing repository and its stack. 2.
Identify what already exists versus what is missing. 3. List any
conflicts between the repository and this handover. 4. Propose the
smallest safe first milestone. 5. Wait for approval before destructive
changes or major stack changes.

## Environment variables

Create `.env.example` with names and descriptions, never real secrets.
Expected variables will include:

-   `DATABASE_URL`
-   `JWT_SECRET` or chosen auth-provider settings
-   `APP_BASE_URL`
-   `API_BASE_URL`
-   `CORS_ORIGINS`
-   `UPLOAD_PROVIDER`, `UPLOAD_BUCKET`, provider credentials
-   `AI_PROVIDER`, `AI_API_KEY`, model identifiers
-   `PAYPAL_BASE_URL` (Sandbox by default), `PAYPAL_CLIENT_ID`,
    `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`
-   `ZAPIER_WEBHOOK_SECRET`
-   `EMAIL_PROVIDER` and credentials if email is implemented
-   `REDIS_URL` if a Redis-backed queue is selected

Never commit `.env`, credentials, certificates or private test data.
