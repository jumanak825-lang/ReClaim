# 9. Implementation Plan and Acceptance Criteria

## 9.1 Delivery strategy

Build a vertical slice: one end-to-end recovery scenario working
securely is more valuable than a large set of disconnected screens.

Recommended order: 1. Repository and deployment foundation. 2. Auth,
roles and organisation scoping. 3. Reports and image upload. 4.
Extraction and matching. 5. Claims and human review. 6. Recovery
methods. 7. PayPal Sandbox. 8. Zapier events. 9. Organisation operations
dashboard. 10. Seeded demo, security testing and polish.

## 9.2 Milestone 0 --- Repository audit and setup

Tasks: - Inspect current repository. - Confirm framework/runtime
versions. - Confirm package manager and lint/test commands. - Identify
existing auth/database/storage integrations. - Create or update
architecture notes. - Create `.env.example`. - Establish local
development instructions. - Configure database migrations and health
endpoints.

Acceptance: - Existing code is understood before modification. - Local
web/API can start. - Database connection works. - Health endpoint
reports service status. - No secrets committed.

## 9.3 Milestone 1 --- Auth, roles and organisations

Tasks: - User registration/login/session. - User profile. - Organisation
and location models. - Membership and permissions. - Seed demo
organisations. - Protected frontend routes. - Backend scope enforcement.

Acceptance: - Individual can register and sign in. - Staff account can
be assigned to an organisation/location. - Unassigned staff cannot read
organisation cases. - Permission tests cover cross-tenant access.

## 9.4 Milestone 2 --- Lost/found reports and uploads

Tasks: - Lost report form and API. - Found report form and API. - Image
upload adapter. - Public/private attribute separation. - Report detail
and list pages. - Report status lifecycle. - Validation and upload
restrictions.

Acceptance: - Individual can create a lost report. - Individual can
create a found report. - Organisation staff can create a found report
for an authorised location. - Images persist and display through
authorised URLs. - Public DTO excludes private details. - User can view
only permitted reports.

## 9.5 Milestone 3 --- AI extraction and matching

Tasks: - Extraction provider interface. - Structured output schema. -
Background job/outbox. - Normalisation functions. - Candidate
retrieval. - Initial weighted scoring. - Match explanation. - Matcher
version tracking. - Seed known pairs and test fixtures.

Acceptance: - New reports trigger asynchronous extraction/matching. -
User sees processing state. - Known seeded pair is ranked above hard
negatives. - Missing attributes do not crash scoring. - AI outage falls
back to deterministic matching. - Score is labelled as candidate
relevance, not ownership proof.

## 9.6 Milestone 4 --- Claims and ownership verification

Tasks: - Claim creation. - Private verification question generation. -
Evidence upload. - Claim review queue. - Approve/reject/escalate state
machine. - Audit logs. - Notifications.

Acceptance: - Owner can claim a candidate. - Claimant can submit private
evidence. - Finder cannot access private evidence or answers. - Only
authorised reviewer can decide. - Every decision has a reason and audit
record. - AI cannot approve or reject.

## 9.7 Milestone 5 --- Recovery workflows

Tasks: - Recovery creation after approved claim. - Collection flow. -
One-time pickup token/QR. - Delivery address and quote. - Recovery event
timeline. - Staff dispatch/hand-over controls. - Receipt confirmation.

Acceptance: - Unapproved claim cannot start recovery. - Owner can choose
collection or delivery. - Expired/used pickup token is rejected. -
Delivery address is restricted. - Recovery state transitions are
validated. - Simulated courier clearly says demo/simulated.

## 9.8 Milestone 6 --- PayPal Sandbox

Tasks: - OAuth token helper. - Create Orders v2 order. - Approval URL. -
Server-side capture. - Webhook signature verification. - Event
deduplication. - Payment state reconciliation. - Payment UI and error
states.

Acceptance: - Payment amount comes from stored quote. - Browser cannot
mark payment paid. - Successful Sandbox capture advances recovery. -
Failed/cancelled payment does not advance to paid state. - Duplicate
capture/webhook does not duplicate effect. - Credentials remain
backend-only. - UI clearly labels Sandbox in demo.

## 9.9 Milestone 7 --- Zapier

Tasks: - Transactional outbox. - Signed webhook delivery. - Event
subscription/configuration. - Retry and failure states. - Test event
action. - Configure at least two Zaps.

Acceptance: - A high-priority match event reaches a configured Zap. - A
new claim event reaches a configured Zap. - Zapier outage does not roll
back core state. - Duplicate delivery is safe. - Payload excludes
private evidence and sensitive data.

## 9.10 Milestone 8 --- Organisation dashboard and AG Grid

Tasks: - Organisation overview. - Case list API with
filters/pagination. - AG Grid Community table. - Claim queue and case
detail. - Location switcher. - Staff management if time. - Export if
authorised and feasible.

Acceptance: - Grid shows cases within user's scope only. -
Search/filter/sort/pagination work. - Selecting a row opens case
detail. - Claim actions enforce backend permissions. - No
Enterprise-only feature is required for MVP.

## 9.11 Milestone 9 --- Demo hardening

Tasks: - Seed data script. - Reset demo environment script. - End-to-end
happy path. - Failure-path tests. - Mobile reporting QA. - Desktop
organisation dashboard QA. - Demo account instructions. - Logs and
health checks. - Short pitch narrative.

Acceptance: - Demo can be reset to known state. - Complete scenario
works repeatedly. - Payment and automation are visibly real
Sandbox/configured integrations. - Simulated services are labelled. - No
critical privacy or permission issue remains.

## 9.12 Suggested issue breakdown

Use labels: `frontend`, `backend`, `ai`, `payments`, `integrations`,
`security`, `testing`, `docs`.

Each issue should include: - User story. - API/UI scope. - Acceptance
criteria. - Permission implications. - Tests required. - Dependencies.

## 9.13 Testing strategy

### Unit

-   State transition rules.
-   Match scoring and missing-value handling.
-   Permission resolution.
-   Quote calculation.
-   Idempotency key handling.
-   Webhook event deduplication.

### Integration

-   API/database transactions.
-   Storage signed URL access.
-   PayPal Sandbox adapter using mocks and optional live Sandbox test.
-   Zapier event signing/retry.
-   Worker retries.

### End-to-end

1.  Register individual.
2.  Submit lost report.
3.  Staff submits found report.
4.  Match appears.
5.  Owner submits claim/evidence.
6.  Reviewer approves.
7.  Owner chooses delivery.
8.  Sandbox payment completes.
9.  Zapier event is received.
10. Recovery is marked dispatched and received.

### Negative tests

-   Cross-tenant access.
-   Private evidence leakage.
-   Invalid claim decision.
-   Duplicate payment/capture.
-   Forged webhook.
-   Expired pickup token.
-   External service timeout.

## 9.14 Definition of done per ticket

-   Code reviewed for scope and security.
-   Types/schemas updated.
-   Migrations included if schema changes.
-   Tests added and passing.
-   Loading/empty/error states implemented.
-   Audit/notification requirements considered.
-   Documentation and `.env.example` updated.
-   No secrets or demo-only bypasses committed.
