# 5. API Contracts

Base path: `/api/v1`

All endpoints require authentication unless explicitly marked public or
webhook. Use Pydantic schemas and return stable error codes. Exact field
names may be adjusted during implementation, but maintain consistent
semantics.

## 5.1 Common response conventions

Success:

``` json
{
  "data": {},
  "meta": {
    "request_id": "uuid"
  }
}
```

Error:

``` json
{
  "error": {
    "code": "CLAIM_NOT_REVIEWABLE",
    "message": "This claim cannot be reviewed in its current state.",
    "details": {}
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

Use appropriate HTTP status codes: 400 validation, 401 unauthenticated,
403 forbidden, 404 not found, 409 state conflict, 422 semantic
validation, 429 rate limited, 500 unexpected error.

## 5.2 Authentication and profile

-   `POST /auth/register`
-   `POST /auth/login`
-   `POST /auth/logout`
-   `POST /auth/password/forgot`
-   `POST /auth/password/reset`
-   `GET /me`
-   `PATCH /me`

If using an external identity provider, adapt these routes to the
provider's session/token model.

## 5.3 Reports

### Create lost report

`POST /reports/lost`

Request:

``` json
{
  "category": "electronics",
  "item_label": "Laptop",
  "description": "Silver laptop with a small sticker near the keyboard.",
  "brand": "Example",
  "lost_at_start": "2026-11-07T09:00:00Z",
  "lost_at_end": "2026-11-07T11:00:00Z",
  "last_location": {
    "label": "Terminal 1, airport",
    "latitude": null,
    "longitude": null
  },
  "attributes_public": {
    "colour": "silver"
  },
  "attributes_private": {
    "distinctive_mark": "small dent on left corner"
  },
  "image_ids": []
}
```

Response: report DTO plus `processing_status`.

### Create found report

`POST /reports/found`

Request:

``` json
{
  "category": "electronics",
  "item_label": "Laptop",
  "description": "Silver laptop found near a seating area.",
  "found_at": "2026-11-07T10:15:00Z",
  "organisation_id": "uuid",
  "location_id": "uuid",
  "custody_status": "organisation_holds",
  "attributes_public": {
    "colour": "silver"
  },
  "attributes_private": {
    "sticker_description": "hidden detail"
  },
  "image_ids": []
}
```

### Other report routes

-   `GET /reports/{report_id}`
-   `PATCH /reports/{report_id}`
-   `POST /reports/{report_id}/withdraw`
-   `GET /reports/mine?type=lost|found&status=active`

Return only role-appropriate public/private fields. Never return private
fields merely because they exist in the model.

## 5.4 AI extraction

-   `POST /reports/{report_id}/extract`
-   `GET /reports/{report_id}/extraction`

Extraction should normally be queued. Return `202 Accepted` with a
job/report processing state. Do not block the report request on a slow
model call.

## 5.5 Matching

-   `POST /reports/{report_id}/match` (staff/admin or internal service;
    consider keeping internal)
-   `GET /reports/{report_id}/matches`
-   `GET /matches/{match_id}`
-   `POST /matches/{match_id}/dismiss`

Example match response:

``` json
{
  "id": "uuid",
  "score": 87.4,
  "label": "Strong potential match",
  "explanation": [
    "Similar item category and visible appearance",
    "Reported within a nearby time window",
    "Locations are geographically close"
  ],
  "status": "candidate",
  "found_item": {
    "item_label": "Laptop",
    "category": "electronics",
    "approximate_location": "Terminal 1"
  },
  "ownership_warning": "This is an AI-generated candidate, not proof of ownership."
}
```

## 5.6 Claims

-   `POST /matches/{match_id}/claims`
-   `GET /claims/{claim_id}`
-   `GET /claims/mine`
-   `GET /organisations/{organisation_id}/claims?status=pending`
-   `POST /claims/{claim_id}/evidence`
-   `POST /claims/{claim_id}/review`

Review request:

``` json
{
  "decision": "approved",
  "reason": "Claimant correctly identified the private distinguishing mark and supplied supporting evidence."
}
```

Only authorised reviewers may submit a decision. The API must validate
the state transition and organisation scope.

## 5.7 Recoveries

-   `POST /claims/{claim_id}/recoveries`
-   `GET /recoveries/{recovery_id}`
-   `POST /recoveries/{recovery_id}/collection/confirm`
-   `POST /recoveries/{recovery_id}/collection/validate-token`
-   `POST /recoveries/{recovery_id}/delivery/quote`
-   `POST /recoveries/{recovery_id}/delivery/dispatch`
-   `POST /recoveries/{recovery_id}/confirm-received`
-   `POST /recoveries/{recovery_id}/cancel`

Collection creation request:

``` json
{
  "method": "collection",
  "preferred_window_start": "2026-11-09T09:00:00Z",
  "preferred_window_end": "2026-11-09T12:00:00Z"
}
```

Delivery creation request:

``` json
{
  "method": "delivery",
  "address": {
    "recipient_name": "Demo User",
    "line1": "Example Street",
    "city": "Dubai",
    "country_code": "AE",
    "postal_code": null
  }
}
```

Do not expose delivery address to unauthorised staff or integrations.
Provide only the minimum details required for fulfilment.

## 5.8 PayPal

-   `POST /payments/paypal/create-order`
-   `POST /payments/paypal/capture-order`
-   `POST /payments/paypal/webhook` (unauthenticated at application
    session layer; must verify PayPal signature)
-   `GET /payments/{payment_id}`

Create-order request:

``` json
{
  "recovery_id": "uuid",
  "idempotency_key": "client-generated-unique-value"
}
```

The backend must derive amount and currency from the approved delivery
quote, not trust a client-supplied amount.

Create-order response:

``` json
{
  "payment_id": "uuid",
  "paypal_order_id": "provider-order-id",
  "approval_url": "https://www.sandbox.paypal.com/checkoutnow?token=...",
  "status": "created"
}
```

Capture request:

``` json
{
  "paypal_order_id": "provider-order-id"
}
```

The backend verifies order ownership, amount, currency and provider
status before marking captured. Repeated requests must be idempotent.

## 5.9 Zapier / integrations

-   `POST /integrations/zapier/test`
-   `POST /integrations/zapier/callback` only if a callback is needed
-   `GET /organisations/{id}/integrations`
-   `POST /organisations/{id}/integrations/zapier`
-   `PATCH /organisations/{id}/integrations/zapier`
-   `DELETE /organisations/{id}/integrations/zapier`

Outbound events should use a signed webhook payload and retry from the
outbox. Never accept a Zapier assertion as proof of payment or claim
approval.

## 5.10 Organisation operations

-   `POST /organisations`
-   `GET /organisations`
-   `GET /organisations/{id}`
-   `PATCH /organisations/{id}`
-   `POST /organisations/{id}/locations`
-   `GET /organisations/{id}/locations`
-   `POST /organisations/{id}/members`
-   `PATCH /organisations/{id}/members/{user_id}`
-   `GET /organisations/{id}/cases`
-   `GET /organisations/{id}/audit-logs`

## 5.11 Pagination and filtering

List endpoints should support: - `limit` - `cursor` or page-based
pagination (choose one convention) - `status` - `category` -
`location_id` - `date_from`, `date_to` - `sort` - `q` for quick search

Validate sort fields against an allow-list. Never interpolate raw user
input into SQL.

## 5.12 API acceptance tests

-   User A cannot read User B's private claim.
-   Staff from Organisation A cannot read Organisation B's case.
-   Non-reviewer cannot approve a claim.
-   Claim cannot be approved twice with conflicting decisions.
-   Delivery payment amount cannot be altered by client payload.
-   Repeated create-order/capture requests do not duplicate payment.
-   Invalid PayPal webhook signature is rejected.
-   Duplicate webhook event is processed once.
-   Zapier timeout does not roll back a completed claim or recovery
    transition.
