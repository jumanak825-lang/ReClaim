"""Shared enums and small DTOs.

These Literal types become string unions in the generated TypeScript.
Status values follow docs/03 §3.8 (plus `in_transit` from docs/11 §1).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Category = Literal[
    "electronics",
    "phone",
    "bag",
    "wallet",
    "keys",
    "documents",
    "clothing",
    "jewellery",
    "eyewear",
    "umbrella",
    "toy",
    "other",
]
ReportType = Literal["lost", "found"]
ReportStatus = Literal["draft", "submitted", "processing", "active", "resolved", "withdrawn", "expired", "rejected"]
CustodyStatus = Literal["finder_holds", "organisation_holds", "transferred", "released"]
MatchStatus = Literal["candidate", "claim_started", "confirmed", "dismissed"]
ClaimStatus = Literal["pending", "approved", "rejected", "escalated"]
RecoveryMethod = Literal["collection", "delivery"]
RecoveryStatus = Literal[
    "created",
    "awaiting_payment",
    "preparing",
    "ready_for_pickup",
    "dispatched",
    "in_transit",
    "received",
    "completed",
    "cancelled",
    "failed",
    "disputed",
]
PaymentStatus = Literal[
    "created", "approved", "captured", "failed", "voided", "refunded", "partially_refunded", "unknown"
]
MemberRole = Literal["staff", "reviewer", "manager", "admin"]
ImageVisibility = Literal["public_safe", "private_evidence"]
OrganisationType = Literal["airport", "hotel", "mall", "university", "event_venue", "other"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrgRef(Model):
    id: UUID
    name: str


class LocationRef(Model):
    id: UUID
    name: str


class Money(Model):
    amount_minor: int = Field(description="Integer minor units, e.g. 1500 = 15.00")
    currency: str = Field(description="ISO 4217 code, e.g. USD")


class ActivityItem(Model):
    type: str
    title: str
    body: str
    related_entity_type: str | None
    related_entity_id: UUID | None
    created_at: str


class ImageOut(Model):
    id: UUID
    url: str = Field(description="Same-origin path; send the session cookie to fetch it.")
    content_type: str
    size_bytes: int
    visibility: ImageVisibility
