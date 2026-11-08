# Reclaim --- Claude Code Handover Pack

**Product:** Reclaim\
**Tagline:** Lost something? Let AI bring it back.\
**Document set:** Product requirements, UX, architecture, data model,
API contracts, AI matching, integrations, security, implementation plan,
and demo guide.

## How to use this pack

Give Claude Code this entire folder (or the ZIP) as project context.
Start with `CLAUDE.md`, then ask it to implement one milestone at a time
from `09_IMPLEMENTATION_PLAN.md`. Do not ask it to generate the entire
application in one pass.

Recommended first prompt:

> Read `CLAUDE.md` and all documents in the `docs/` directory. Treat
> them as the source of truth for Reclaim. First inspect the existing
> repository and report its current structure, stack, and gaps. Do not
> modify files yet. Then propose a milestone-1 implementation plan that
> follows the architecture and acceptance criteria. Ask before changing
> any existing architecture or introducing paid services.

## Documents

  -----------------------------------------------------------------------
  File                                Purpose
  ----------------------------------- -----------------------------------
  `CLAUDE.md`                         Coding-agent operating instructions
                                      and project guardrails

  `01_PRODUCT_REQUIREMENTS.md`        Product vision, scope, roles,
                                      requirements, stories, acceptance
                                      criteria

  `02_UX_AND_SCREEN_SPEC.md`          Information architecture,
                                      screen-by-screen UX, states and
                                      interactions

  `03_TECHNICAL_ARCHITECTURE.md`      Stack, modules, deployment,
                                      architecture and engineering
                                      conventions

  `04_DATA_MODEL.md`                  PostgreSQL schema, relationships,
                                      indexes, tenancy and data rules

  `05_API_CONTRACTS.md`               REST endpoints, request/response
                                      examples, errors and workflow
                                      contracts

  `06_AI_MATCHING_SPEC.md`            AI extraction, candidate
                                      generation, scoring, verification
                                      and evaluation

  `07_INTEGRATIONS_SPEC.md`           PayPal, Zapier, storage, maps and
                                      notification integration
                                      requirements

  `08_SECURITY_AND_PRIVACY.md`        Threat model, permissions, privacy,
                                      payment safety and audit
                                      requirements

  `09_IMPLEMENTATION_PLAN.md`         Phased build order, tickets,
                                      acceptance criteria and test
                                      strategy

  `10_HACKATHON_DEMO.md`              Seed data, demo story, run-of-show
                                      and judging narrative
  -----------------------------------------------------------------------

## Product decisions already made

-   Reclaim is an interconnected recovery network, not a standalone
    lost-property listing site.
-   Both individuals and organisations participate.
-   Both collection and delivery are supported.
-   AI helps discover likely matches, but never proves ownership or
    approves a claim by itself.
-   PayPal is used for delivery checkout and optionally a separate
    finder reward payout. Reclaim must not describe itself as escrow.
-   Zapier handles external automations. Reclaim's backend remains the
    source of truth.
-   AG Grid Community powers the organisation operations table.
-   Recommended stack: Next.js + TypeScript, FastAPI, PostgreSQL,
    background worker, Render, PayPal REST APIs, Zapier, and image
    storage.
-   MVP should prioritise a complete, believable recovery workflow over
    many shallow features.

## Assumptions to confirm during implementation

1.  Use a modular monolith, not microservices.
2.  Use email/password authentication for the hackathon MVP unless an
    existing auth provider is already configured.
3.  Use a single Reclaim merchant account for the MVP delivery checkout.
    Do not imply that independent organisations are automatically
    merchant-of-record or receive funds directly.
4.  Use PayPal Sandbox only in development/demo.
5.  Simulate courier booking and tracking unless a real courier API is
    explicitly configured.
6.  Start with one currency in the demo environment; store currency
    explicitly in every monetary record.
7.  Use a deterministic baseline matcher with embeddings/vision-assisted
    features. Do not make the demo dependent on an expensive or fragile
    model call.
8.  Treat all scoring weights and thresholds as initial tunable values,
    not validated performance claims.

## Definition of done

A feature is not done merely because its screen exists. It must have: -
A working backend contract. - Server-side validation and permission
checks. - Loading, empty, success and error states. - Relevant audit
events. - Automated tests for important business rules. - No secrets in
frontend code. - A clear local setup path documented in the repository.
