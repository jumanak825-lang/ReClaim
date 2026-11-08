# 3. Technical Architecture

## 3.1 Architecture decision

Use a **modular monolith** with a separately deployable background
worker. This is simpler to build, test and deploy than microservices
while retaining clear domain boundaries.

## 3.2 High-level topology

``` text
Individual / Organisation Staff / Reclaim Admin
                    |
              Next.js Web App
                    |
              FastAPI REST API
       _____________|____________________________
      |             |            |               |
 PostgreSQL    Object Storage   AI Services   Integration Adapters
      |             |            |          /       |        \
 Outbox/events   Images       Extractor   PayPal  Zapier   Email
      |
 Background Worker / Queue
      |
 Matching, notifications, retries, cleanup
```

PayPal webhooks and Zapier callbacks enter through dedicated API routes,
are authenticated/verified, and then update internal state through
domain services.

## 3.3 Recommended stack

  -----------------------------------------------------------------------
  Layer                   Choice                  Notes
  ----------------------- ----------------------- -----------------------
  Web                     Next.js + TypeScript    App Router;
                                                  server/client
                                                  boundaries explicit

  UI                      Tailwind + shadcn/ui    Accessible primitives,
                                                  consistent tokens

  Data                    TanStack Query or       Avoid duplicating
                          established repository  server state
                          convention              

  Grid                    AG Grid Community       Check feature licensing

  API                     Python + FastAPI        Pydantic
                                                  request/response
                                                  schemas

  Database                PostgreSQL              UUIDs, transactions,
                                                  JSONB only for flexible
                                                  metadata

  Worker                  Redis-backed queue or   Persistent retries
                          Postgres outbox worker  

  Images                  S3-compatible /         Provider adapter
                          Cloudinary / Supabase   
                          Storage                 

  AI                      Vision/text model +     Provider abstraction
                          embedding provider      

  Payments                PayPal REST             Sandbox first

  Automation              Zapier webhooks         External workflow layer

  Hosting                 Render                  Web, API, worker and
                                                  database services
  -----------------------------------------------------------------------

## 3.4 Backend modules

-   `auth`: identity, sessions, membership resolution.
-   `organisations`: organisations, locations, staff and permissions.
-   `reports`: lost/found reports and media metadata.
-   `matching`: candidate generation, scoring, explanations and
    feedback.
-   `claims`: private evidence, verification questions, decisions.
-   `recoveries`: collection/delivery state machine.
-   `payments`: PayPal orders, captures, refunds and webhook events.
-   `payouts`: optional finder rewards, separate from checkout.
-   `notifications`: in-app/email notification orchestration.
-   `integrations`: Zapier event delivery and external callbacks.
-   `audit`: immutable business event records.
-   `admin`: network-level operations and escalation.

## 3.5 Frontend structure

Suggested structure:

``` text
apps/
  web/
    app/
      (public)/
      (auth)/
      (individual)/
      (organisation)/
      admin/
    components/
      ui/
      forms/
      reports/
      matches/
      claims/
      recoveries/
      organisation/
    lib/
      api/
      auth/
      permissions/
      validation/
    features/
      reports/
      matches/
      claims/
      recoveries/
      operations/
```

Adapt to the actual repository. Do not force a monorepo if the existing
project is already organised differently.

## 3.6 Backend structure

``` text
apps/
  api/
    app/
      main.py
      core/
        config.py
        security.py
        database.py
        errors.py
      modules/
        auth/
        organisations/
        reports/
        matching/
        claims/
        recoveries/
        payments/
        payouts/
        notifications/
        integrations/
        audit/
      workers/
      tests/
      migrations/
```

Each module should separate: - router/controller - request/response
schemas - service/domain logic - repository/data access - tests

Avoid placing business logic directly in route handlers.

## 3.7 Asynchronous work

Use a persistent queue or transactional outbox for: - image
processing, - AI extraction, - matching, - notifications, - Zapier
delivery, - payment reconciliation, - expired pickup token cleanup.

Critical events must not be lost if a process restarts. Use retry with
exponential backoff and a dead-letter/error state. Jobs must be
idempotent.

## 3.8 Core state machines

### Lost/found report

`draft → submitted → processing → active → resolved` Additional terminal
states: `withdrawn`, `expired`, `rejected`.

### Match

`candidate → claim_started → confirmed` or `dismissed` A match is not a
claim decision.

### Claim

`pending → approved | rejected | escalated` Escalated claims can return
to pending review or reach a final decision.

### Recovery

`created → awaiting_payment (delivery only) → preparing → ready_for_pickup | dispatched → received → completed`
Alternative terminal states: `cancelled`, `failed`, `disputed`.

### Payment

`created → approved → captured` Other states: `failed`, `voided`,
`refunded`, `partially_refunded`, `unknown`. Use provider state
reconciliation; do not invent a local state from a redirect.

## 3.9 API and data conventions

-   Prefix API with `/api/v1`.
-   JSON request/response.
-   UTC ISO-8601 timestamps.
-   UUID identifiers.
-   Money as integer minor units and ISO currency.
-   Pagination uses `limit` and `cursor` or `page`/`page_size`
    consistently.
-   Return stable machine-readable error codes.
-   Use `Idempotency-Key` for payment and other retry-sensitive
    operations.
-   Use correlation/request IDs in logs.

## 3.10 Render deployment

Suggested services: 1. `reclaim-web`: Next.js web service. 2.
`reclaim-api`: FastAPI web service. 3. `reclaim-worker`: background
worker. 4. Managed PostgreSQL. 5. Optional Redis if selected for
queueing.

Use health checks, environment-specific secrets and migration release
commands. Do not run migrations concurrently from every web instance.
Keep development, preview and production databases separate.

## 3.11 Architecture quality attributes

-   Tenant isolation: every organisation query is scoped by
    membership/permissions.
-   Resilience: external services fail independently; retries do not
    duplicate effects.
-   Auditability: claim decisions, payment transitions and custody
    changes are traceable.
-   Extensibility: provider adapters avoid locking the domain to one
    AI/storage vendor.
-   Testability: domain services can be tested without calling live
    PayPal, Zapier or AI services.
