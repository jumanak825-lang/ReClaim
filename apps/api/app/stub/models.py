"""In-memory records for the STUB backend.

These stand in for the PostgreSQL tables in docs/04. They are internal:
routers never return them directly, only the DTOs in app/schemas.
Everything here is replaced when the real persistence layer lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    email: str
    password_hash: str
    display_name: str
    phone_e164: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)


@dataclass
class Session:
    user_id: UUID
    expires_at: datetime


@dataclass
class Organisation:
    name: str
    slug: str
    organisation_type: str
    description: str | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class Location:
    organisation_id: UUID
    name: str
    timezone: str
    country_code: str
    address_public: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    opening_hours: str | None = None
    collection_instructions: str | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class Membership:
    organisation_id: UUID
    user_id: UUID
    role: str
    location_ids: list[UUID] = field(default_factory=list)


@dataclass
class Image:
    uploader_id: UUID
    content_type: str
    data: bytes
    visibility: str
    report_id: UUID | None = None
    claim_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)


@dataclass
class Report:
    report_type: str  # lost | found
    category: str
    item_label: str
    description: str
    owner_user_id: UUID | None = None  # lost: owner; found: individual reporter
    created_by_user_id: UUID | None = None
    organisation_id: UUID | None = None
    location_id: UUID | None = None
    brand: str | None = None
    model: str | None = None
    lost_at_start: datetime | None = None
    lost_at_end: datetime | None = None
    found_at: datetime | None = None
    location_label: str = ""
    latitude: float | None = None
    longitude: float | None = None
    custody_status: str | None = None
    status: str = "draft"
    attributes_public: dict[str, str] = field(default_factory=dict)
    attributes_private: dict[str, str] = field(default_factory=dict)
    storage_reference: str | None = None
    image_ids: list[UUID] = field(default_factory=list)
    processing_until: datetime | None = None
    extraction: dict[str, Any] | None = None
    extraction_ready_at: datetime | None = None
    is_seed: bool = False
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)
    updated_at: datetime = field(default_factory=now)


@dataclass
class Match:
    lost_report_id: UUID
    found_report_id: UUID
    score: float
    components: dict[str, float]
    explanation: list[str]
    matcher_version: str
    status: str = "candidate"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)


@dataclass
class Evidence:
    evidence_type: str
    image_id: UUID | None = None
    text: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)


@dataclass
class ClaimHistory:
    action: str
    from_status: str | None
    to_status: str
    reason: str | None
    actor_user_id: UUID | None
    created_at: datetime = field(default_factory=now)


@dataclass
class Claim:
    reference: str
    match_id: UUID
    claimant_user_id: UUID
    statement: str
    answers: list[dict[str, str]]
    status: str = "pending"
    evidence: list[Evidence] = field(default_factory=list)
    history: list[ClaimHistory] = field(default_factory=list)
    decision_by_user_id: UUID | None = None
    decision_reason: str | None = None
    decided_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)
    updated_at: datetime = field(default_factory=now)


@dataclass
class RecoveryEvent:
    event_type: str
    description: str
    is_simulated: bool = False
    created_by_user_id: UUID | None = None
    created_at: datetime = field(default_factory=now)


@dataclass
class Recovery:
    claim_id: UUID
    method: str
    status: str
    address: dict[str, Any] | None = None
    quote_minor: int | None = None
    currency: str | None = None
    quote_expires_at: datetime | None = None
    preferred_window_start: datetime | None = None
    preferred_window_end: datetime | None = None
    pickup_token: str | None = None  # real backend stores only a hash
    pickup_token_expires_at: datetime | None = None
    tracking_reference: str | None = None
    dispatched_at: datetime | None = None
    events: list[RecoveryEvent] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)
    updated_at: datetime = field(default_factory=now)


@dataclass
class Payment:
    recovery_id: UUID
    user_id: UUID
    provider_order_id: str
    amount_minor: int
    currency: str
    idempotency_key: str
    status: str = "created"
    provider_capture_id: str | None = None
    captured_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)


@dataclass
class Notification:
    user_id: UUID
    type: str
    title: str
    body: str
    related_entity_type: str | None
    related_entity_id: UUID | None
    read_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)


@dataclass
class AuditLog:
    actor_user_id: UUID | None
    organisation_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID
    reason: str | None
    request_id: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)


@dataclass
class OutboxEvent:
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    organisation_id: UUID | None
    payload: dict[str, Any]
    delivery_status: str = "stubbed_not_sent"
    attempt_count: int = 0
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)
