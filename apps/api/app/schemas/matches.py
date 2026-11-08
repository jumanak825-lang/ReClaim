from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .common import Category, MatchStatus, Model, ReportType

OWNERSHIP_WARNING = "This is an AI-generated candidate, not proof of ownership."


class MatchItemSummary(Model):
    report_id: UUID
    report_type: ReportType
    item_label: str
    category: Category
    approximate_location: str
    organisation_name: str | None
    date_start: datetime | None
    date_end: datetime | None
    thumbnail_url: str | None
    attributes_public: dict[str, str]


class ScoreComponents(Model):
    category: float = Field(ge=0, le=1)
    description: float = Field(ge=0, le=1)
    attributes: float = Field(ge=0, le=1)
    location: float = Field(ge=0, le=1)
    time: float = Field(ge=0, le=1)


class MatchOut(Model):
    id: UUID
    score: float = Field(description="AI relevance 0-100. Advisory only; not proof of ownership.")
    label: str = Field(description="'Strong potential match' (>=85) or 'Possible match' (65-84.99).")
    explanation: list[str]
    score_components: ScoreComponents
    status: MatchStatus
    matcher_version: str
    created_at: datetime
    lost_item: MatchItemSummary
    found_item: MatchItemSummary
    ownership_warning: str = OWNERSHIP_WARNING
    active_claim_id: UUID | None
    available_actions: list[str] = Field(description="start_claim, dismiss, view_claim")


class VerificationQuestion(Model):
    id: str
    prompt: str
    allow_dont_remember: bool = True
