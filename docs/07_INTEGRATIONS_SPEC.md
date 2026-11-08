# 7. Integrations Specification

## 7.1 Integration principles

-   Domain state lives in Reclaim's database.
-   Provider adapters isolate external API details.
-   Every external operation has a correlation ID and idempotency
    strategy.
-   Secrets stay server-side and are never sent to the browser.
-   External failures are visible and retryable.
-   Clearly label Sandbox and simulated integrations in the UI/demo.

## 7.2 PayPal Checkout

### MVP use case

Collect the delivery fee from the owner after a claim is approved and a
delivery quote is established.

### Important financial distinction

Delivery checkout and optional finder reward payout are separate
operations. Reclaim must not claim to be escrow. Do not imply that a
delivery payment is automatically passed to a finder or organisation. A
production model where multiple independent organisations receive
payments may require PayPal partner/multiparty capabilities, onboarding
and approval. Confirm eligibility before designing that flow.

### API flow

1.  Backend creates a local payment row with status `created`.
2.  Backend obtains PayPal OAuth access token using client credentials.
3.  Backend creates an Orders v2 order using amount/currency from the
    approved quote.
4.  Browser redirects/opens PayPal approval URL.
5.  Browser returns with order reference.
6.  Backend captures order server-side.
7.  Backend verifies returned capture amount, currency and status.
8.  Backend updates payment/recovery in a transaction.
9.  Webhook is independently signature-verified and used for
    reconciliation.
10. Duplicate requests/events are idempotently ignored or reconciled.

Relevant endpoints: - OAuth: `POST /v1/oauth2/token` - Orders:
`POST /v2/checkout/orders` - Capture:
`POST /v2/checkout/orders/{id}/capture` - Refund:
`POST /v2/payments/captures/{id}/refund` - Webhooks: PayPal webhook
verification API and configured webhook endpoint.

### Required safeguards

-   Sandbox and live base URLs are separate configuration.
-   Never accept amount/currency from the browser as authoritative.
-   Verify PayPal order belongs to the current recovery and local user.
-   Verify capture status, amount and currency.
-   Use `PayPal-Request-Id` or equivalent idempotency support for
    retry-sensitive requests.
-   Verify webhook signature using PayPal's verification mechanism.
-   Persist provider event IDs to prevent duplicate processing.
-   Reconcile local state with PayPal on uncertain outcomes.
-   Never log client secret, access token or full sensitive payload.
-   Do not mark paid from query parameters or a frontend success page.

### Refunds

Refunds are a separate authorised workflow. Store refund amount and
provider refund ID. Never silently refund because a webhook is
duplicated or delayed.

### Finder reward payout (optional)

-   Separate payout entity and API workflow.
-   Trigger only after approved handover/recovery completion and
    configured policy checks.
-   Verify recipient eligibility and PayPal Payouts availability for the
    account/country.
-   Do not block MVP on Payouts if account eligibility is unclear.
-   Show reward as pending until provider confirms completion.
-   Keep delivery charge and reward accounting distinct.

### Official documentation to consult during implementation

-   https://developer.paypal.com/api/rest/
-   https://developer.paypal.com/docs/api/orders/v2/
-   https://developer.paypal.com/docs/api/payments.payouts-batch/v1/
-   https://developer.paypal.com/api/rest/webhooks/

Check current API version, country availability, account eligibility,
fees and partner requirements before live deployment.

## 7.3 Zapier

Zapier is an external workflow layer, not the system of record.

### Outbound event examples

-   `match.high_priority`
-   `claim.created`
-   `claim.approved`
-   `claim.rejected`
-   `recovery.delivery_requested`
-   `payment.captured`
-   `recovery.dispatched`
-   `recovery.completed`
-   `claim.flagged_for_review`

### Suggested MVP Zaps

1.  High-priority match → send a Slack/email notification to
    organisation staff.
2.  New claim → create a review task or add a row to a controlled Google
    Sheet.
3.  Optional: recovery completed → send a feedback request.

### Event envelope

``` json
{
  "event_id": "uuid",
  "event_type": "claim.created",
  "occurred_at": "2026-11-07T10:20:00Z",
  "organisation_id": "uuid",
  "data": {
    "claim_id": "uuid",
    "case_reference": "RC-000123",
    "status": "pending"
  }
}
```

Do not send private evidence, full addresses, serial numbers, passwords
or payment credentials to Zapier.

### Delivery behaviour

-   Use a transactional outbox.
-   Sign payloads with HMAC and include timestamp/signature headers.
-   Retry transient errors with exponential backoff.
-   Record attempt count, last response and delivery status.
-   Provide a dead-letter state and manual retry.
-   Protect against replay using timestamp tolerance and event ID.
-   Do not let a Zapier response change claim/payment truth.

## 7.4 Image storage

-   Use private buckets by default.
-   Generate short-lived signed URLs for authorised access.
-   Validate MIME type, extension and file signature.
-   Set maximum file size and image dimensions.
-   Strip EXIF metadata where appropriate.
-   Scan files where supported.
-   Separate public-safe thumbnails from private evidence.
-   Never expose raw storage keys.

## 7.5 Email and in-app notifications

-   In-app notification is required.
-   Email provider can be selected later.
-   Notification templates must use safe DTOs.
-   Do not put private evidence or hidden item attributes in email
    subject/body.
-   Retry provider errors and record delivery status.

## 7.6 Maps and geocoding

-   Map display is optional for MVP.
-   Do not require exact coordinates; support location labels and
    approximate areas.
-   Keep precise custody/storage location private.
-   Use configurable provider and respect provider terms.
-   Avoid exposing a found item's exact location before claim approval.

## 7.7 Courier integration

MVP may use a simulated courier workflow: - Create dispatch record. -
Generate a demo tracking reference. - Move through preparing,
dispatched, in-transit and delivered. - Clearly label simulation in UI.
A real courier integration requires partner credentials, serviceability
checks, quote rules, cancellation/refund handling and personal-data
controls.
