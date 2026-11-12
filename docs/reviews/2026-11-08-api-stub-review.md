# API stub review — fixes for the backend

**For:** Jumana (backend)
**Reviewed:** PR #1 `api-stub` (merge `de86c80`)
**Date:** 2026-11-08

The stub works well as a contract for the frontend. All 7 tests pass, and
regenerating `openapi.json` matches the committed file. None of the items
below change response shapes, so the frontend keeps building against the
current contract.

Fix items 1–4 in the stub, since the frontend runs against it every day.
Item 5 is a checklist for the real backend.

---

## 1. `PATCH /reports/{id}` with a null field breaks the report (confirmed)

**Repro** (as `owner@reclaim.example`):

```http
PATCH /api/v1/reports/{own_lost_report_id}
{"category": null}
```

- The response is `500 INTERNAL_ERROR`.
- Every later `GET /reports/{id}` for that report also returns `500`, until
  `POST /dev/reset`.

**Cause:** `ReportUpdate` allows explicit `null` for required fields
(`category`, `item_label`, `description`). `update_report` keeps those
nulls through `exclude_unset=True` and `setattr`s them onto the report
([services.py:362](../../apps/api/app/stub/services.py#L362)). Building
`ReportOut` then fails.

**Expected:** `400 VALIDATION_ERROR` with `details.fields`, and the report
unchanged (docs/05 §5.1).

**Suggested fix:** in `ReportUpdate`, reject explicit null for
`category`, `item_label`, `description` and `last_location`, for example
with a `model_validator` that checks `model_fields_set`. While you're there,
apply the same `lost_at_end >= lost_at_start` check that
`LostReportCreate` already has.

**Test:** PATCH with `{"category": null}` returns 400, and a GET afterwards
returns 200 with the category unchanged.

---

## 2. One found item can get two approved owners (found by reading the code)

**Scenario:**
- Two different lost reports both match the same found item, which is
  possible because `run_matching` scores every pair.
- Each owner submits a claim, one per match.
- A reviewer approves both. Nothing stops the second approval.

**Cause:** `review_claim`
([services.py:643](../../apps/api/app/stub/services.py#L643)) only checks the
claim's own state. `active_claim_for` checks one match, not the found report.

**Spec:**
- FR-019: "A report cannot have multiple simultaneously approved owners."
- docs/05 §5.12: "Claim cannot be approved twice with conflicting decisions."

**Suggested fix:**
- On `approved`, return `409` with a new code such as
  `FOUND_ITEM_ALREADY_CLAIMED` if any other claim on the same found report is
  `approved`.
- Decide what happens to the other pending claims on that item. They could
  stay pending for the reviewer to reject, or be marked as superseded.
- In the real backend, enforce this with a partial unique index on
  approved claims per found report (docs/04 §4.4).

**Test:** two lost reports against the same found item, each with a claim.
The first approval returns 200 and the second returns 409.

---

## 3. Location scope is only enforced in the cases list

**What's scoped today:** `_org_found` in `routers/organisations.py` filters
by the membership's `location_ids`. That covers the cases list, case detail
and found inventory.

**What isn't:** these only check that the user is a member of the org:
- `services.report_access`, behind `GET /reports/{id}`.
- `claim_role`, behind `GET /claims/{id}` and review.
- `recovery_role`, behind every `/recoveries/*` route.
- `org_claims`, behind the claim review queue.

So staff assigned to location A can read, and if they're a reviewer decide,
claims and recoveries for items at location B.

**Spec:** docs/08 §8.11 says "Staff cannot access a location outside their
scope". docs/01 FR-017 and FR-029 say the same.

**Suggested fix:** one helper, for example
`in_scope(user, org_id, location_id) -> role | None`, that applies
`location_ids` (empty means all locations). Use it in all four places, and
filter `org_claims` by the found report's `location_id`.

**Test:** seed a reviewer limited to one location.
- `GET /claims/{id}` for a claim at another location returns 404.
- The review queue doesn't list that claim.
- `POST /claims/{id}/review` on it returns 404 (or 403).

---

## 4. The dev routes are open without sign-in

| Route | Risk |
|---|---|
| `POST /dev/reset` | Anyone can wipe all data |
| `GET /dev/demo-accounts` | Lists the demo emails and passwords |
| `GET /dev/mock-paypal/approve?token=` | Anyone with an order id can mark a payment approved |
| `POST /dev/recoveries/{id}/advance-courier` | Signed in, but no role check |

This is fine on localhost. It becomes a problem once the API is exposed
through ngrok for the PayPal webhook (docs/11 §1).

**Suggested fix:**
- Only include the dev router when an env flag such as
  `ENABLE_DEV_ROUTES=true` is set. Default it to false in `.env.example`.
- Have `mock-paypal/approve` require the session of the payment's own user.
- Remove the dev routes when real PayPal Sandbox replaces the mock.

**Test:** with the flag off, `/dev/*` returns 404. With it on,
`mock-paypal/approve` without the payer's session returns 404.

---

## 4b. `GET /organisations/{id}/overview` has no location filter (contract gap)

The org overview (docs/02 Screen 10) has a location selector. The priority
queue already filters through `/cases?location_id=`. The overview cards
(active cases, found inventory, pending/escalated claims, recoveries) can't,
because `/overview` takes no `location_id`.

The frontend currently labels the cards "Across all (your) locations".

**Ask:** add an optional `location_id` query param to `/overview`. Validate it
against the org and the caller's assigned locations, return 404 for one
outside their scope, and apply it to every count. Then regenerate
`openapi.json`. Once it's in, the frontend will pass the selected location.

Also note that `recent_activity` on `/overview` is the caller's own
notifications, not organisation-wide activity. That's fine for the demo;
just confirm it's intended.

---

## 5. Checklist for the real backend (the stub is fine as it is)

These are expected gaps in a stub. Listing them so they aren't lost:

- [ ] Rate limits per user and per IP, returning 429 with `Retry-After`.
      Auth, uploads and claim submission first.
- [ ] Hash passwords with argon2id or bcrypt; the stub uses PBKDF2.
- [ ] Store a hash of the pickup token, not the token itself (docs/04
      `pickup_token_hash`).
- [ ] Verify PayPal webhook signatures and dedupe events by
      `(provider, provider_event_id)`. The stub currently accepts every
      webhook.
- [ ] Registration with an email that's already used returns 409, which
      reveals that the account exists. Either accept the risk for the
      hackathon or return the same response as a successful sign-up.
- [ ] Outbox delivery to Zapier with HMAC signing. The stub records events
      but never sends them.
- [ ] Add tests for 1–3 to the real backend's permission suite, so they
      carry over.

---

## Frontend dependencies

None of these block the frontend. If 2 or 3 add new error codes (for
example `FOUND_ITEM_ALREADY_CLAIMED`), say so in the PR and regenerate
`openapi.json` so the frontend can show a message for them.
