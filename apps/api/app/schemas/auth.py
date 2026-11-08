from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from .common import ActivityItem, MemberRole, Model

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(Model):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class LoginIn(Model):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class MembershipOut(Model):
    organisation_id: UUID
    organisation_name: str
    organisation_slug: str
    role: MemberRole
    location_ids: list[UUID] = Field(description="Empty means all locations in the organisation.")


class MeOut(Model):
    id: UUID
    email: str
    display_name: str
    phone_e164: str | None
    created_at: datetime
    is_staff: bool = Field(description="True when the user has at least one organisation membership.")
    memberships: list[MembershipOut]


class MeUpdate(Model):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    phone_e164: str | None = Field(default=None, pattern=r"^\+[1-9]\d{6,14}$")


class DashboardCounts(Model):
    active_lost_reports: int
    active_found_reports: int
    potential_matches: int
    claims_awaiting_review: int
    active_recoveries: int


class DashboardOut(Model):
    counts: DashboardCounts
    recent_activity: list[ActivityItem]
