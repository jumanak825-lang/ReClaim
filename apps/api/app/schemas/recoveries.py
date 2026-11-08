from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .common import Model, PaymentStatus, RecoveryMethod, RecoveryStatus


class AddressIn(Model):
    recipient_name: str = Field(min_length=1, max_length=120)
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")


class AddressOut(Model):
    """Full for the claimant; staff see recipient name, city and country only."""

    recipient_name: str
    line1: str | None
    line2: str | None
    city: str
    region: str | None
    postal_code: str | None
    country_code: str


class RecoveryCreate(Model):
    method: RecoveryMethod
    preferred_window_start: datetime | None = None
    preferred_window_end: datetime | None = None
    address: AddressIn | None = None

    @model_validator(mode="after")
    def _check(self) -> "RecoveryCreate":
        if self.method == "delivery" and self.address is None:
            raise ValueError("address is required for delivery")
        return self


class DeliveryQuoteOut(Model):
    amount_minor: int
    currency: str
    is_estimate: bool
    service_description: str
    expires_at: datetime


class CollectionInfo(Model):
    location_name: str
    organisation_name: str
    address_public: str | None
    opening_hours: str | None
    instructions: str | None
    preferred_window_start: datetime | None
    preferred_window_end: datetime | None


class RecoveryEventOut(Model):
    event_type: str
    description: str
    is_simulated: bool
    created_at: datetime


class PaymentOut(Model):
    id: UUID
    recovery_id: UUID
    provider: Literal["paypal"]
    paypal_order_id: str
    status: PaymentStatus
    amount_minor: int
    currency: str
    is_sandbox: bool
    captured_at: datetime | None
    created_at: datetime


RecoveryViewerRole = Literal["claimant", "staff"]


class RecoveryOut(Model):
    id: UUID
    claim_id: UUID
    claim_reference: str
    item_label: str
    method: RecoveryMethod
    status: RecoveryStatus
    viewer_role: RecoveryViewerRole
    collection: CollectionInfo | None
    delivery_address: AddressOut | None
    delivery_quote: DeliveryQuoteOut | None
    payment: PaymentOut | None
    pickup_token: str | None = Field(
        description="Claimant only, while ready_for_pickup and unexpired. Never show on a public page."
    )
    pickup_token_expires_at: datetime | None
    tracking_reference: str | None
    courier_is_simulated: bool = Field(description="Always true for now: label the courier as simulated.")
    timeline: list[RecoveryEventOut]
    available_actions: list[str] = Field(
        description="claimant: pay_with_paypal, confirm_received, cancel; "
        "staff: mark_ready_for_pickup, validate_pickup_token, dispatch, cancel"
    )
    created_at: datetime
    updated_at: datetime


class ValidateTokenIn(Model):
    token: str = Field(min_length=4, max_length=32)


class CancelIn(Model):
    reason: str = Field(min_length=3, max_length=500)
