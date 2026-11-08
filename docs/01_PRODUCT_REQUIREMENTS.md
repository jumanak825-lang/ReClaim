# 1. Product Requirements Document (PRD)

## 1.1 Product summary

**Reclaim** is an AI-powered lost-and-found recovery network that
connects individuals and participating organisations so that lost
belongings can be discovered, verified and returned across otherwise
disconnected locations.

**Tagline:** Lost something? Let AI bring it back.

Most lost-property processes are fragmented. A person may lose an item
in a hotel, airport, mall, university or event venue and have no idea
which organisation received it. Reclaim creates a shared discovery and
recovery layer across participating locations.

## 1.2 Problem statement

-   Lost-property records are spread across disconnected spreadsheets,
    desks, inboxes and portals.
-   Owners often do not know where to search.
-   Descriptions vary, so keyword-only search misses plausible matches.
-   Staff spend time manually comparing reports.
-   Organisations need a safe way to validate ownership and coordinate
    handover.
-   Delivery, collection, notifications and financial steps are handled
    inconsistently.

## 1.3 Vision and value

**Vision:** Make lost-property recovery work across organisational
boundaries.

**Value for individuals:** Report once, discover possible matches across
the network, prove ownership privately and choose a recovery method.

**Value for organisations:** One workflow for intake, AI-assisted
matching, claim review, handover, delivery and operational reporting.

**Value for finders:** A safe, documented way to report found property
and optionally receive a reward when an owner has recovered the item.

## 1.4 Product principles

1.  Network first: owners should not need to know which organisation has
    the item.
2.  AI-assisted discovery: matching should tolerate different wording,
    images and incomplete details.
3.  Privacy first: a candidate match is not proof of ownership.
4.  Human accountability: authorised staff make final claim decisions.
5.  Safe recovery: custody, handover and delivery are traceable.
6.  Payment integrity: financial state is verified server-side.
7.  Open integration: organisations can connect workflows without
    surrendering Reclaim's source of truth.

## 1.5 Users and roles

### Individual

-   Can create lost reports.
-   Can report found items as an individual finder.
-   Can view and manage their own reports and claims.
-   Can submit private claim evidence.
-   Can choose collection or delivery after approval.
-   Can view their own recovery and payment status.

### Organisation staff

-   Belongs to one or more organisations and locations.
-   Can create found reports for permitted locations.
-   Can view cases within assigned scope.
-   Can review claims if granted the relevant permission.
-   Can update custody and recovery status.
-   Cannot access other organisations' records.

### Organisation manager/admin

-   Manages organisation profile, locations, memberships and
    permissions.
-   Views organisation-wide operational data.
-   Can configure notification/integration settings where authorised.
-   Can audit actions by staff.

### Reclaim super admin

-   Manages network-level configuration, organisation onboarding and
    abuse escalation.
-   Has privileged access only through explicit audited workflows.
-   Should not be used as a shortcut around tenant permissions.

A user may act as both owner and finder. Roles are permissions, not
mutually exclusive account types.

## 1.6 Core workflows

### Workflow A: Lost item report

1.  User starts a report using a conversational or structured form.
2.  User describes the item and last known location/time.
3.  User optionally uploads images or evidence.
4.  AI extracts structured attributes.
5.  User reviews and confirms extracted details.
6.  Backend saves report and queues matching.
7.  User sees status and receives notifications when a candidate
    appears.

### Workflow B: Found item report

1.  Finder or staff reports an item.
2.  User uploads image and description.
3.  AI classifies the item and extracts visible attributes.
4.  Reporter selects location, found time and custody status.
5.  Backend stores public-safe and private attributes separately.
6.  Matching runs across eligible lost reports.
7.  Potential owners are notified without revealing the exact item
    location or hidden attributes.

### Workflow C: Claim and ownership verification

1.  Owner opens a potential match and submits a claim.
2.  System asks private questions based on attributes withheld from
    public listing.
3.  Owner may submit supporting evidence such as receipt, serial number,
    private photo or distinctive marks.
4.  AI may flag inconsistencies and summarise evidence for staff.
5.  Authorised staff reviews and approves, rejects or escalates.
6.  All decisions and reasons are audited.
7.  Approved claim unlocks recovery options.

### Workflow D: Collection

1.  Owner chooses collection.
2.  Organisation confirms pickup instructions and an available
    collection window.
3.  System generates a one-time pickup reference or QR token.
4.  Staff validates the token and claimant identity according to
    organisation policy.
5.  Both parties or authorised staff confirm handover.
6.  Recovery is marked complete and case closed.

### Workflow E: Delivery

1.  Owner chooses delivery after claim approval.
2.  System displays a delivery quote and service description.
3.  Owner pays through PayPal Checkout.
4.  Backend verifies payment status with PayPal.
5.  Recovery is created/advanced and delivery team is notified.
6.  Courier booking/tracking may be simulated in the MVP.
7.  Owner or authorised recipient confirms receipt.
8.  Case closes.

## 1.7 Functional requirements

### Reporting

-   FR-001: An authenticated individual can create a lost report.
-   FR-002: An authenticated individual can create a found report.
-   FR-003: Organisation staff can create found reports for authorised
    locations.
-   FR-004: Reports support category, free-text description, date/time,
    location and optional images.
-   FR-005: AI extraction is presented for user confirmation before
    final save where extraction changes user-entered meaning.
-   FR-006: Reporter can edit or withdraw a report while it is in an
    editable state.
-   FR-007: Public-safe attributes and private attributes must be stored
    separately.

### Discovery and matching

-   FR-008: New or materially updated reports trigger matching
    asynchronously.
-   FR-009: Matching searches eligible reports across participating
    organisations.
-   FR-010: Candidate results include score, explanation and status.
-   FR-011: Users only see candidate information permitted for their
    role.
-   FR-012: A match score must never be labelled as ownership proof.
-   FR-013: Staff can dismiss an incorrect candidate and provide a
    reason.

### Claims

-   FR-014: Owner can submit a claim against a candidate.
-   FR-015: Claim form can request private evidence.
-   FR-016: Staff can approve, reject or escalate a claim.
-   FR-017: Only authorised staff can decide claims for their
    organisation/location.
-   FR-018: Decision and reason are recorded in an audit log.
-   FR-019: A report cannot have multiple simultaneously approved
    owners.

### Recovery

-   FR-020: Approved claims can create collection or delivery
    recoveries.
-   FR-021: Collection supports a one-time pickup token.
-   FR-022: Delivery requires a server-verified successful payment
    before paid delivery is marked as funded.
-   FR-023: Staff can record handover, dispatch and delivery milestones.
-   FR-024: Owner can confirm receipt.
-   FR-025: Recovery events are timestamped and auditable.

### Organisation operations

-   FR-026: Organisation users have a scoped dashboard.
-   FR-027: Operations dashboard uses AG Grid Community for case
    management.
-   FR-028: Grid supports sorting, filtering, pagination, quick search
    and row navigation.
-   FR-029: Users can only access records within their assigned
    organisation/location permissions.
-   FR-030: Organisation admins can manage locations and memberships.

### Integrations

-   FR-031: Delivery payment uses PayPal Sandbox in the MVP.
-   FR-032: PayPal order creation/capture and webhook verification
    happen server-side.
-   FR-033: Backend emits signed events for Zapier automations.
-   FR-034: Zapier failure does not reverse or corrupt core Reclaim
    state.
-   FR-035: Integration attempts and outcomes are logged.

### Notifications

-   FR-036: Notify users about candidate matches, claim decisions and
    recovery milestones.
-   FR-037: Notification content must not disclose private item details
    to an unauthorised recipient.
-   FR-038: In-app notification is the minimum viable channel; email may
    be added if configured.

## 1.8 Non-functional requirements

-   Security: authentication, role-based access, organisation isolation,
    secure secrets, webhook verification.
-   Privacy: data minimisation, private evidence protection,
    retention/deletion policy.
-   Reliability: asynchronous AI work must be retryable and idempotent.
-   Performance: normal API reads should target sub-second responses
    under demo load; AI matching is asynchronous.
-   Accessibility: keyboard navigation, semantic controls, readable
    contrast and responsive layouts.
-   Observability: structured logs, request IDs, audit trails and
    integration error visibility.
-   Maintainability: modular monolith, migrations, typed contracts and
    documented setup.
-   Portability: provider adapters for AI, storage, payment and
    notifications.

## 1.9 MVP scope

### Must-have

-   Authentication and role-based access.
-   Individual lost/found reports.
-   Organisation and location setup with seeded demo organisations.
-   Image upload.
-   AI-assisted extraction.
-   Cross-report matching and ranked candidates.
-   Claim submission and private evidence.
-   Human claim review.
-   Collection and delivery workflows.
-   PayPal Sandbox delivery checkout.
-   Organisation dashboard with AG Grid Community.
-   At least two real Zapier automations.
-   Seeded demo data and end-to-end tests.

### Should-have if time permits

-   QR pickup reference.
-   Simulated courier status timeline.
-   Finder reward payout in Sandbox, only if account/API eligibility is
    confirmed.
-   Map-based proximity display.
-   Suspicious claim indicators.
-   CSV export with permission checks.

### Out of scope for MVP

-   Production escrow or custody of funds.
-   Global courier marketplace.
-   Native mobile applications.
-   Autonomous claim approval.
-   Production multi-party merchant onboarding.
-   Full organisation billing/subscriptions.
-   Guaranteed global coverage or guaranteed match accuracy.

## 1.10 Success metrics

Track, do not fabricate: - Candidate precision on a labelled test set. -
Percentage of lost reports receiving at least one useful candidate. -
Median time from report to first candidate. - Claim
approval/rejection/escalation rates. - Recovery completion rate. -
Median time from approval to recovery. - PayPal checkout completion
rate. - Zapier event delivery success rate. - Staff time per case, if
measured.

## 1.11 Monetisation hypotheses

-   Organisation subscriptions for operational tooling and network
    participation.
-   Event-based pricing for temporary event venues.
-   Enterprise plans for multi-location organisations.
-   Courier integration/referral revenue subject to contracts and
    applicable rules.
-   Keep basic individual reporting free. Do not charge someone merely
    to report a lost item.

## 1.12 Acceptance criteria for the MVP

A demo user can report a lost laptop, an organisation can report a found
laptop, the matcher surfaces the seeded pair, the owner submits private
evidence, staff approves the claim, the owner chooses delivery, a PayPal
Sandbox payment is verified by the backend, a Zapier automation is
triggered, and the recovery timeline can be completed. The system must
prevent an unrelated user from viewing private evidence or changing the
claim decision.
