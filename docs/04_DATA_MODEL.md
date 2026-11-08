# 4. Data Model and Database Design

## 4.1 General rules

-   PostgreSQL is the source of truth.
-   Use UUID primary keys.
-   `created_at` and `updated_at` are UTC `timestamptz`.
-   Monetary values use integer minor units and ISO 4217 currency codes.
-   Private evidence and hidden item attributes must not be placed in
    public-facing JSON.
-   Organisation-scoped records must carry an organisation/location
    relationship and be checked on every request.
-   Use migrations; do not use runtime auto-create in production.

## 4.2 Core entities

### users

-   `id UUID PK`
-   `email CITEXT UNIQUE`
-   `password_hash` or external auth subject
-   `display_name`
-   `phone_e164 NULL`
-   `email_verified_at NULL`
-   `status`
-   timestamps

### organisations

-   `id UUID PK`
-   `name`
-   `slug UNIQUE`
-   `organisation_type` (airport, hotel, mall, university, event_venue,
    other)
-   `description NULL`
-   `status` (pending, active, suspended)
-   timestamps

### locations

-   `id UUID PK`
-   `organisation_id FK`
-   `name`
-   `address_public NULL`
-   `latitude NULL`, `longitude NULL`
-   `timezone`
-   `is_active`
-   timestamps

### organisation_memberships

-   `id UUID PK`
-   `organisation_id FK`
-   `user_id FK`
-   `role` (staff, reviewer, manager, admin)
-   `status`
-   timestamps
-   Unique constraint on `(organisation_id, user_id)`.

### location_memberships

-   `id UUID PK`
-   `location_id FK`
-   `user_id FK`
-   `permission_scope` or explicit permission set
-   timestamps

### lost_reports

-   `id UUID PK`
-   `owner_user_id FK`
-   `category`
-   `item_label`
-   `description_public`
-   `brand NULL`
-   `model NULL`
-   `lost_at_start NULL`, `lost_at_end NULL`
-   `last_location_text`
-   `last_location_lat NULL`, `last_location_lng NULL`
-   `status`
-   `visibility`
-   `attributes_public JSONB`
-   `attributes_private JSONB` (restricted access; consider separate
    table)
-   `matching_version`
-   timestamps

### found_reports

-   `id UUID PK`
-   `reporter_user_id FK NULL`
-   `organisation_id FK NULL`
-   `location_id FK NULL`
-   `category`
-   `item_label`
-   `description_public`
-   `found_at`
-   `custody_status` (finder_holds, organisation_holds, transferred,
    released)
-   `status`
-   `attributes_public JSONB`
-   `attributes_private JSONB`
-   `storage_reference` (private; never public)
-   timestamps

At least one of `reporter_user_id` or `organisation_id` must be present.
If organisation custody is selected, enforce a valid location and
membership.

### item_images

-   `id UUID PK`
-   `lost_report_id FK NULL`
-   `found_report_id FK NULL`
-   `storage_key`
-   `content_type`
-   `size_bytes`
-   `visibility` (public_safe, private_evidence)
-   `uploaded_by_user_id FK`
-   `scan_status`
-   timestamps

### matches

-   `id UUID PK`
-   `lost_report_id FK`
-   `found_report_id FK`
-   `score NUMERIC(5,2)`
-   `score_components JSONB`
-   `explanation_public`
-   `status`
-   `matcher_version`
-   `created_at`
-   Unique constraint on
    `(lost_report_id, found_report_id, matcher_version)` or an upsert
    strategy.

### claims

-   `id UUID PK`
-   `match_id FK`
-   `claimant_user_id FK`
-   `status`
-   `verification_questions JSONB` (private)
-   `review_summary_private`
-   `decision_by_user_id FK NULL`
-   `decision_reason NULL`
-   `decided_at NULL`
-   timestamps

### claim_evidence

-   `id UUID PK`
-   `claim_id FK`
-   `evidence_type`
-   `storage_key` or encrypted structured value
-   `private_metadata JSONB`
-   `reviewer_visibility`
-   timestamps

### recoveries

-   `id UUID PK`
-   `claim_id FK UNIQUE`
-   `method` (collection, delivery)
-   `status`
-   `delivery_address_encrypted NULL`
-   `delivery_quote_minor NULL`
-   `currency NULL`
-   `pickup_token_hash NULL`
-   `pickup_token_expires_at NULL`
-   `tracking_reference NULL`
-   `recipient_confirmed_at NULL`
-   timestamps

### recovery_events

-   `id UUID PK`
-   `recovery_id FK`
-   `event_type`
-   `description`
-   `metadata_private JSONB`
-   `created_by_user_id FK NULL`
-   `created_at`

### payments

-   `id UUID PK`
-   `recovery_id FK`
-   `provider` (paypal)
-   `provider_order_id UNIQUE`
-   `provider_capture_id UNIQUE NULL`
-   `amount_minor`
-   `currency`
-   `status`
-   `idempotency_key UNIQUE`
-   `captured_at NULL`
-   `refunded_minor DEFAULT 0`
-   timestamps

### payouts (optional phase)

-   `id UUID PK`
-   `found_report_id FK`
-   `recipient_user_id FK`
-   `provider_batch_id NULL`
-   `provider_item_id NULL`
-   `amount_minor`
-   `currency`
-   `status`
-   `idempotency_key UNIQUE`
-   timestamps

### webhook_events

-   `id UUID PK`
-   `provider`
-   `provider_event_id`
-   `event_type`
-   `verified_at NULL`
-   `processing_status`
-   `payload_redacted JSONB`
-   `received_at`
-   `processed_at NULL`
-   Unique constraint `(provider, provider_event_id)`.

### integration_endpoints

-   `id UUID PK`
-   `organisation_id FK`
-   `provider` (zapier)
-   `endpoint_url_encrypted`
-   `secret_hash` or secure secret reference
-   `enabled_events JSONB`
-   `status`
-   timestamps

### outbox_events

-   `id UUID PK`
-   `event_type`
-   `aggregate_type`
-   `aggregate_id`
-   `payload JSONB`
-   `delivery_status`
-   `attempt_count`
-   `next_attempt_at`
-   `created_at`
-   `delivered_at NULL`

### notifications

-   `id UUID PK`
-   `user_id FK`
-   `type`
-   `title`
-   `body_safe`
-   `related_entity_type`
-   `related_entity_id`
-   `read_at NULL`
-   `created_at`

### audit_logs

-   `id UUID PK`
-   `actor_user_id FK NULL`
-   `organisation_id FK NULL`
-   `action`
-   `entity_type`
-   `entity_id`
-   `before_redacted JSONB`
-   `after_redacted JSONB`
-   `reason NULL`
-   `request_id`
-   `created_at`

## 4.3 Relationships

-   User 1---many lost reports.
-   User 1---many found reports.
-   Organisation 1---many locations.
-   Organisation many---many users through memberships.
-   Lost report many---many found reports through matches.
-   Match 1---many claims over time, but only one active claim should be
    permitted unless a defined policy allows otherwise.
-   Claim 1---many evidence records.
-   Approved claim 1---0/1 recovery.
-   Recovery 1---many recovery events.
-   Recovery 1---many payment attempts; only one successful delivery
    capture should fund a recovery.
-   Found report 1---many optional reward payouts.

## 4.4 Indexes and constraints

Recommended: - `lost_reports(status, category, created_at)` -
`found_reports(status, category, found_at)` -
`matches(lost_report_id, score DESC)` - `claims(status, created_at)` -
`recoveries(status, updated_at)` - `payments(provider_order_id)`
unique - `webhook_events(provider, provider_event_id)` unique -
`organisation_memberships(user_id, organisation_id)` unique - Geospatial
index if PostGIS is enabled. - GIN indexes for selected JSONB attributes
only where justified.

Use partial unique indexes to prevent multiple active claims or
recoveries where appropriate. Define exactly what "active" means in the
migration.

## 4.5 Privacy and tenancy boundaries

-   Public report DTOs must be explicitly allow-listed.
-   Private item attributes are visible only to the owner/reporter and
    authorised reviewers.
-   Claim evidence is visible only to claimant and assigned authorised
    reviewers.
-   Found-item storage location is visible only to authorised
    custodians.
-   Organisation staff can access only assigned organisation/location
    records.
-   Super-admin access must be explicit, audited and justified.
-   Do not rely solely on frontend filtering.

## 4.6 Data retention

Create a configurable retention policy: - Withdrawn/expired public
reports can be hidden from discovery. - Private evidence should be
deleted or anonymised after the defined retention period, subject to
disputes/legal requirements. - Payment and audit records may need longer
retention under applicable financial/legal requirements. - User deletion
should trigger a documented anonymisation/deletion workflow without
destroying records that must lawfully be retained.

## 4.7 Migration sequence

1.  users and auth tables
2.  organisations, locations, memberships
3.  lost_reports, found_reports, item_images
4.  matches and matching metadata
5.  claims and evidence
6.  recoveries and recovery_events
7.  payments, payouts, webhook_events
8.  notifications, outbox_events, integrations, audit_logs
9.  indexes, constraints and row-level security if adopted
