"""Payments, notifications, organisations and integrations DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from .common import (
    ActivityItem,
    Category,
    ClaimStatus,
    Model,
    OrganisationType,
    PaymentStatus,
    RecoveryStatus,
    ReportStatus,
)
from .claims import ClaimListItem
from .matches import MatchOut
from .recoveries import RecoveryOut
from .reports import ReportOut


# --- payments -------------------------------------------------------------
class CreateOrderIn(Model):
    recovery_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=100, description="Client-generated, e.g. a UUID.")


class CreateOrderOut(Model):
    payment_id: UUID
    paypal_order_id: str
    approval_url: str = Field(description="Redirect the browser here to approve the payment.")
    status: PaymentStatus


class CaptureOrderIn(Model):
    paypal_order_id: str = Field(min_length=1, max_length=64)


class WebhookAck(Model):
    received: bool


# --- notifications --------------------------------------------------------
class NotificationOut(Model):
    id: UUID
    type: str = Field(
        description="match.found, claim.submitted, claim.new_for_review, claim.approved, claim.rejected, "
        "claim.escalated, payment.captured, recovery.ready_for_pickup, recovery.dispatched, "
        "recovery.in_transit, recovery.completed"
    )
    title: str
    body: str
    related_entity_type: Literal["report", "match", "claim", "recovery", "payment"] | None
    related_entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class UnreadCountOut(Model):
    unread: int


# --- organisations --------------------------------------------------------
class OrganisationOut(Model):
    id: UUID
    name: str
    slug: str
    organisation_type: OrganisationType
    description: str | None


class LocationOut(Model):
    id: UUID
    organisation_id: UUID
    name: str
    address_public: str | None
    latitude: float | None
    longitude: float | None
    timezone: str
    country_code: str
    opening_hours: str | None


class OrgOverviewOut(Model):
    active_cases: int
    found_inventory: int
    pending_claims: int
    escalated_claims: int
    recoveries_in_progress: int
    recent_activity: list[ActivityItem]
    is_seeded_demo_data: bool = Field(description="Show a 'seeded demo data' label when true.")


Priority = Literal["high", "medium", "low"]


class CaseRow(Model):
    id: UUID = Field(description="Found report id; use for case detail.")
    case_reference: str
    item_label: str
    category: Category
    report_type: Literal["found"]
    report_status: ReportStatus
    candidate_match_id: UUID | None
    ai_relevance: float | None
    location_id: UUID | None
    location_name: str | None
    reported_at: datetime
    claim_id: UUID | None
    claim_status: ClaimStatus | None
    recovery_id: UUID | None
    recovery_status: RecoveryStatus | None
    priority: Priority
    updated_at: datetime


class CaseDetailOut(Model):
    case_reference: str
    found_report: ReportOut
    matches: list[MatchOut]
    claims: list[ClaimListItem]
    recovery: RecoveryOut | None


class AuditLogOut(Model):
    id: UUID
    actor_display_name: str | None
    action: str
    entity_type: str
    entity_id: UUID
    reason: str | None
    request_id: str
    created_at: datetime


# --- integrations ---------------------------------------------------------
class LastDelivery(Model):
    event_type: str
    status: str
    attempted_at: datetime
    error: str | None


class IntegrationOut(Model):
    provider: Literal["zapier"]
    status: Literal["configured", "not_configured"]
    configured_via: Literal["env"] = "env"
    enabled_events: list[str]
    last_delivery: LastDelivery | None
    note: str


class ZapierTestIn(Model):
    organisation_id: UUID


class ZapierTestOut(Model):
    outbox_event_id: UUID
    status: str
    note: str


# --- dev ------------------------------------------------------------------
class DemoAccount(Model):
    email: str
    password: str
    display_name: str
    persona: str


class HealthOut(Model):
    status: Literal["ok"]
    mode: Literal["stub"]
