# 2. UX and Screen Specification

## 2.1 Experience direction

Reclaim should feel trustworthy, modern and calm. The experience is
about recovering something important, so avoid playful gamification as
the dominant visual language.

**Design attributes:** clear, reassuring, efficient, human, secure,
networked.

**Suggested visual direction:** light neutral canvas, deep navy/charcoal
typography, a confident blue or teal primary action, restrained green
for completed states, amber for pending review and red only for
destructive/error states. Keep visual tokens centralised so branding can
be adjusted.

Do not invent a final logo or brand system without approval.

## 2.2 Information architecture

### Public / individual

-   Home / landing page
-   Sign up / sign in
-   Individual dashboard
-   Report something lost
-   Report something found
-   My lost reports
-   My found reports
-   Matches
-   Match detail
-   Submit a claim
-   Claim status
-   Recovery detail
-   Notifications
-   Profile / privacy settings

### Organisation portal

-   Organisation overview
-   Cases / operations table
-   Lost reports
-   Found inventory
-   Matches
-   Claim review queue
-   Case detail
-   Recovery management
-   Locations
-   Staff and permissions
-   Integrations
-   Audit log
-   Organisation settings

### Reclaim administration

-   Organisation onboarding
-   Network health
-   Abuse/escalation queue
-   Global audit view
-   Configuration

## 2.3 Global navigation

### Individual navigation

-   Dashboard
-   Report Lost
-   Report Found
-   My Reports
-   Matches
-   Notifications
-   Profile

### Organisation navigation

-   Overview
-   Operations
-   Found Items
-   Claims
-   Recoveries
-   Locations
-   Team
-   Integrations
-   Settings

Display current organisation and location context clearly. If a staff
member belongs to multiple organisations, provide an explicit
organisation switcher.

## 2.4 Screen specifications

### Screen 1: Landing page

**Goal:** Explain the network and lead to reporting. - Hero: "Lost
something? Let AI bring it back." - Supporting copy: "One report. A
connected network of participating locations. A safer way home for your
belongings." - Primary CTA: Report a lost item. - Secondary CTA: Report
a found item. - Explain three steps: Report → Match → Recover. - Explain
organisation participation. - Trust section: private verification,
human-reviewed claims, secure recovery. - Avoid claims such as "find
anything instantly" or unsupported accuracy percentages.

### Screen 2: Authentication

-   Sign in and create account.
-   Email verification if supported by chosen auth method.
-   Password reset.
-   Clear error messages without leaking whether an email is registered.
-   Organisation staff sign-in uses the same identity system with
    membership-based access.

### Screen 3: Individual dashboard

**Summary cards:** Active lost reports, potential matches, claims
awaiting review, active recoveries. **Recent activity:** timeline of
report/claim/recovery events. **Primary actions:** Report lost, Report
found. **Empty state:** explain how to create first report. Do not
expose organisation-only data.

### Screen 4: Lost report wizard

Use a short, progressive flow: 1. Item basics: name/category,
description, brand/model if known. 2. Where and when: location,
date/time, approximate area. 3. Images and distinctive details: optional
public photo; private identifying details separated. 4. AI review:
extracted attributes with editable fields. 5. Confirmation: show privacy
summary and submit.

Required: item description, category (or AI-proposed category confirmed
by user), last-known location, approximate date/time. Allow "not sure"
for uncertain values. Never force a user to invent a serial number or
exact time.

### Screen 5: Found report wizard

1.  Item photo and description.
2.  Found location and time.
3.  Custody status: "I have the item" / "Handed to an organisation" /
    "Organisation is holding it".
4.  Visible attributes.
5.  Private details withheld from public listing.
6.  AI extraction review.
7.  Submit.

Warn users not to post exact storage location, access codes or sensitive
identifying details publicly.

### Screen 6: Report detail

-   Item summary.
-   Status timeline.
-   Reported location at privacy-appropriate precision.
-   AI processing state.
-   Candidate matches section.
-   Edit/withdraw actions only when permitted.
-   Explain that candidates are not confirmed ownership.

### Screen 7: Matches

-   Candidate cards with image thumbnail, category, approximate
    location, date range and match explanation.
-   Do not reveal hidden attributes or exact storage location.
-   Match score may be shown as "AI relevance" with a clear "not proof
    of ownership" explanation.
-   Actions: View candidate, Start claim, Not my item.

### Screen 8: Match detail and claim

-   Side-by-side comparison of safe attributes.
-   "Why this may match" explanation.
-   "Claim this item" action.
-   Private verification form: ask only for evidence relevant to this
    case.
-   Evidence upload supports allowed file types and size limits.
-   Explain who can review the evidence and why it is private.
-   Submit and show claim reference.

### Screen 9: Claim review (organisation)

-   Queue grouped by pending, escalated, decided.
-   Claim detail includes report pair, evidence summary, consistency
    flags and audit history.
-   Evidence should be shown only to authorised reviewers.
-   Approve, reject, escalate actions require confirmation and reason.
-   AI summary must be labelled as assistance, not a decision.
-   Prevent reviewer from deciding a claim outside their assigned scope.

### Screen 10: Organisation overview

-   Cards: active cases, found inventory, pending claims, recoveries in
    progress.
-   Trends only where enough data exists; otherwise show seeded demo
    label.
-   Priority queue and recent activity.
-   Location selector and organisation context.

### Screen 11: Operations table (AG Grid Community)

Suggested columns: - Case ID - Item - Report type - Candidate match - AI
relevance - Location - Reported date - Claim status - Recovery status -
Priority - Updated - Action

Features: - Quick filter/search. - Sort/filter. - Pagination. - Row
selection only for safe bulk operations. - Row click opens case
detail. - Column visibility if available in Community version. - CSV
export only if authorised. Avoid Enterprise-only features unless
licensed. Keep all permissions enforced server-side.

### Screen 12: Recovery choice

Only available after claim approval. - Collection option: location,
opening hours/collection windows, instructions. - Delivery option:
delivery address, quote, estimated service description. - Show price and
currency before checkout. - Clarify whether delivery quote is fixed or
estimated. - PayPal button/checkout action. - Do not imply a finder
reward is part of delivery fee.

### Screen 13: Recovery detail

Timeline: - Claim approved - Recovery method selected - Payment
pending/paid (delivery only) - Preparing for collection/dispatch - Ready
for pickup / dispatched - In transit (simulated if no courier
integration) - Received / handed over - Completed

For collection, display a one-time pickup token/QR with expiry. Never
expose it on a public page.

### Screen 14: Notifications

-   Match found.
-   Claim submitted.
-   Claim approved/rejected/escalated.
-   Delivery payment confirmed.
-   Ready for collection / dispatched / received.
-   Preferences for channels where supported.

### Screen 15: Integrations

Organisation admins only: - Zapier connection status. - Event
subscriptions enabled. - Last delivery attempt and error state. -
Rotate/revoke secret. - Test event action. Never display a full secret
after creation.

## 2.5 Important UI states

Every data-driven screen must implement: - Initial loading. - Empty
state. - Error state with retry. - Permission denied. - Stale/refreshing
state where appropriate. - Success feedback. - Disabled state while a
mutation is pending. - Confirmation for irreversible decisions.

## 2.6 Responsive behaviour

-   Individual reporting must work well on mobile.
-   Organisation dashboard is desktop-first but usable on tablet.
-   AG Grid should have a deliberate narrow-screen fallback, such as
    card rows or horizontal scrolling.
-   Do not hide essential claim/recovery actions on mobile.

## 2.7 Accessibility

-   Keyboard accessible forms and dialogs.
-   Visible focus states.
-   Labels for every input.
-   Meaningful alt text.
-   Status is conveyed with text/icon, not colour alone.
-   Error messages associated with fields.
-   Avoid timeouts that erase entered evidence.
