"""PostgreSQL tables (docs/04). Internal only: routers return DTOs from app/schemas.

Deliberate deviations from docs/04, recorded in apps/api/README.md:
- One `reports` table with `report_type` (lost|found) instead of separate lost/found tables.
- `claims.found_report_id` is denormalised so a partial unique index can enforce FR-019.
- Claim decision history lives in `audit_logs` (no separate claim history table).
- `delivery_address` is JSONB (not encrypted) for the hackathon.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map = {
        uuid.UUID: UUID(as_uuid=True),
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
    }


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def created() -> Mapped[datetime]:
    return mapped_column(default=now, server_default=text("now()"))


def updated() -> Mapped[datetime]:
    return mapped_column(default=now, onupdate=now, server_default=text("now()"))


# --------------------------------------------------------------------- identity ----

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lower-cased
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    phone_e164: Mapped[str | None] = mapped_column(String(20))
    email_verified_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = pk()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 of the cookie value
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = created()


class Organisation(Base):
    __tablename__ = "organisations"
    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    organisation_type: Mapped[str] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[uuid.UUID] = pk()
    organisation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    address_public: Mapped[str | None] = mapped_column(String(300))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(64))
    country_code: Mapped[str] = mapped_column(String(2))
    opening_hours: Mapped[str | None] = mapped_column(String(200))
    collection_instructions: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class OrganisationMembership(Base):
    __tablename__ = "organisation_memberships"
    __table_args__ = (UniqueConstraint("organisation_id", "user_id"),
                      CheckConstraint("role IN ('staff','reviewer','manager','admin')", name="ck_membership_role"))
    id: Mapped[uuid.UUID] = pk()
    organisation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class LocationMembership(Base):
    """Restricts an organisation membership to specific locations. None for a user = all locations."""
    __tablename__ = "location_memberships"
    __table_args__ = (UniqueConstraint("location_id", "user_id"),)
    id: Mapped[uuid.UUID] = pk()
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = created()


# ---------------------------------------------------------------------- reports ----

class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("report_type IN ('lost','found')", name="ck_report_type"),
        CheckConstraint("report_type = 'lost' OR owner_user_id IS NOT NULL OR organisation_id IS NOT NULL",
                        name="ck_found_has_custodian"),
        Index("ix_reports_type_status_category", "report_type", "status", "category", "created_at"),
    )
    id: Mapped[uuid.UUID] = pk()
    report_type: Mapped[str] = mapped_column(String(10))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organisations.id"), index=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id"))
    category: Mapped[str] = mapped_column(String(30))
    item_label: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(80))
    lost_at_start: Mapped[datetime | None]
    lost_at_end: Mapped[datetime | None]
    found_at: Mapped[datetime | None]
    location_label: Mapped[str] = mapped_column(String(300), default="")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    custody_status: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    attributes_public: Mapped[dict[str, Any]] = mapped_column(default=dict)
    attributes_private: Mapped[dict[str, Any]] = mapped_column(default=dict)
    storage_reference: Mapped[str | None] = mapped_column(String(200))
    image_ids: Mapped[list[Any]] = mapped_column(default=list)  # ordered list of item_images ids (str)
    extraction_status: Mapped[str] = mapped_column(String(20), default="not_started")
    extraction: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    extraction_provider: Mapped[str | None] = mapped_column(String(40))
    extraction_is_fallback: Mapped[bool] = mapped_column(Boolean, default=True)
    extraction_updated_at: Mapped[datetime | None]
    matching_version: Mapped[str | None] = mapped_column(String(20))
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class ItemImage(Base):
    __tablename__ = "item_images"
    id: Mapped[uuid.UUID] = pk()
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reports.id"), index=True)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("claims.id", use_alter=True, name="fk_item_images_claim_id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    visibility: Mapped[str] = mapped_column(String(20))
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    scan_status: Mapped[str] = mapped_column(String(20), default="signature_checked")
    created_at: Mapped[datetime] = created()


# --------------------------------------------------------------------- matching ----

class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("lost_report_id", "found_report_id", "matcher_version"),
                      Index("ix_matches_lost_score", "lost_report_id", text("score DESC")))
    id: Mapped[uuid.UUID] = pk()
    lost_report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"))
    found_report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"), index=True)
    score: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    score_components: Mapped[dict[str, Any]] = mapped_column(default=dict)
    explanation_public: Mapped[list[Any]] = mapped_column(default=list)
    status: Mapped[str] = mapped_column(String(20), default="candidate")
    matcher_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


# ----------------------------------------------------------------------- claims ----

ACTIVE_CLAIM_SQL = "status IN ('pending','escalated','approved')"


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        # One active claim per match, one approved owner per found item (FR-019, docs/04 §4.4).
        Index("uq_claims_active_per_match", "match_id", unique=True, postgresql_where=text(ACTIVE_CLAIM_SQL)),
        Index("uq_claims_approved_per_found", "found_report_id", unique=True,
              postgresql_where=text("status = 'approved'")),
        Index("ix_claims_status_created", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = pk()
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id"))
    found_report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"))
    claimant_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    statement: Mapped[str] = mapped_column(Text)  # private
    verification_answers: Mapped[list[Any]] = mapped_column(default=list)  # private
    decision_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    id: Mapped[uuid.UUID] = pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(20))
    image_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("item_images.id"))
    text_value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created()


# ------------------------------------------------------------------- recoveries ----

class Recovery(Base):
    __tablename__ = "recoveries"
    __table_args__ = (Index("ix_recoveries_status_updated", "status", "updated_at"),)
    id: Mapped[uuid.UUID] = pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"), unique=True)
    method: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    delivery_address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    delivery_quote_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    quote_expires_at: Mapped[datetime | None]
    preferred_window_start: Mapped[datetime | None]
    preferred_window_end: Mapped[datetime | None]
    pickup_token_hash: Mapped[str | None] = mapped_column(String(64))
    pickup_token_expires_at: Mapped[datetime | None]
    tracking_reference: Mapped[str | None] = mapped_column(String(40))
    dispatched_at: Mapped[datetime | None]
    recipient_confirmed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class RecoveryEvent(Base):
    __tablename__ = "recovery_events"
    id: Mapped[uuid.UUID] = pk()
    recovery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recoveries.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_private: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created()


# --------------------------------------------------------------------- payments ----

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[uuid.UUID] = pk()
    recovery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recoveries.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(20), default="paypal")
    # "mock" (local dev, no PayPal call) or "sandbox": decides how capture/reconcile talk to PayPal.
    provider_mode: Mapped[str] = mapped_column(String(10), default="mock", server_default="mock")
    approval_url: Mapped[str | None] = mapped_column(String(500))
    provider_order_id: Mapped[str] = mapped_column(String(64), unique=True)
    provider_capture_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20), default="created")
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    captured_at: Mapped[datetime | None]
    refunded_minor: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id"),)
    id: Mapped[uuid.UUID] = pk()
    provider: Mapped[str] = mapped_column(String(20))
    provider_event_id: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(100))
    verified_at: Mapped[datetime | None]
    processing_status: Mapped[str] = mapped_column(String(20), default="received")
    payload_redacted: Mapped[dict[str, Any]] = mapped_column(default=dict)
    received_at: Mapped[datetime] = created()
    processed_at: Mapped[datetime | None]


# ---------------------------------------------------------- outbox, notifications ----

class OutboxEvent(Base):
    """Persistent queue for background jobs and integration events (docs/03 §3.7).

    delivery_status: pending -> delivered | skipped, or failed (retrying) -> dead after max attempts.
    """
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_due", "delivery_status", "next_attempt_at"),)
    id: Mapped[uuid.UUID] = pk()
    event_type: Mapped[str] = mapped_column(String(60))
    aggregate_type: Mapped[str] = mapped_column(String(30))
    aggregate_id: Mapped[uuid.UUID]
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organisations.id"))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    delivery_status: Mapped[str] = mapped_column(String(20), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(default=now, server_default=text("now()"))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created()
    delivered_at: Mapped[datetime | None]


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body_safe: Mapped[str] = mapped_column(Text)
    related_entity_type: Mapped[str | None] = mapped_column(String(20))
    related_entity_id: Mapped[uuid.UUID | None]
    read_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),
                      Index("ix_audit_org_created", "organisation_id", "created_at"))
    id: Mapped[uuid.UUID] = pk()
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organisations.id"))
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[uuid.UUID]
    before_redacted: Mapped[dict[str, Any]] = mapped_column(default=dict)
    after_redacted: Mapped[dict[str, Any]] = mapped_column(default=dict)
    reason: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = created()


class RateLimitBucket(Base):
    """Fixed-window counters shared by every API process."""
    __tablename__ = "rate_limit_buckets"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
