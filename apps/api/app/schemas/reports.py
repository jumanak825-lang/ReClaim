from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .common import (
    Category,
    CustodyStatus,
    ImageOut,
    LocationRef,
    Model,
    OrgRef,
    ReportStatus,
    ReportType,
)

Attrs = dict[str, str]


class PlaceIn(Model):
    label: str = Field(min_length=1, max_length=200, description="Free text, e.g. 'Terminal 1, airport'.")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class LostReportCreate(Model):
    category: Category
    item_label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    brand: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    lost_at_start: datetime | None = Field(default=None, description="Null = not sure.")
    lost_at_end: datetime | None = None
    last_location: PlaceIn
    attributes_public: Attrs = Field(default_factory=dict)
    attributes_private: Attrs = Field(
        default_factory=dict, description="Never shown publicly. Used for private verification."
    )
    image_ids: list[UUID] = Field(default_factory=list, max_length=6)
    as_draft: bool = Field(
        default=False,
        description="True keeps the report in `draft` so the wizard can run AI extraction "
        "before calling POST /reports/{id}/submit.",
    )

    @model_validator(mode="after")
    def _window(self) -> "LostReportCreate":
        if self.lost_at_start and self.lost_at_end and self.lost_at_end < self.lost_at_start:
            raise ValueError("lost_at_end must be after lost_at_start")
        return self


class FoundReportCreate(Model):
    category: Category
    item_label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    brand: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    found_at: datetime | None = None
    custody_status: CustodyStatus = Field(
        description="finder_holds = 'I have the item'; transferred = 'Handed to an organisation'; "
        "organisation_holds = staff recording an item their organisation holds (membership required)."
    )
    organisation_id: UUID | None = Field(default=None, description="Required unless custody is finder_holds.")
    location_id: UUID | None = Field(default=None, description="Required with organisation_id.")
    found_location: PlaceIn | None = Field(
        default=None, description="Where an individual found it. Required when custody is finder_holds."
    )
    storage_reference: str | None = Field(
        default=None, max_length=200, description="Staff only. Private; never shown publicly."
    )
    attributes_public: Attrs = Field(default_factory=dict)
    attributes_private: Attrs = Field(default_factory=dict)
    image_ids: list[UUID] = Field(default_factory=list, max_length=6)
    as_draft: bool = False


class ReportUpdate(Model):
    category: Category | None = None
    item_label: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    brand: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    lost_at_start: datetime | None = None
    lost_at_end: datetime | None = None
    found_at: datetime | None = None
    last_location: PlaceIn | None = None
    storage_reference: str | None = Field(default=None, max_length=200)
    attributes_public: Attrs | None = None
    attributes_private: Attrs | None = None
    image_ids: list[UUID] | None = Field(default=None, max_length=6)


ProcessingStatus = Literal["not_started", "processing", "completed", "failed"]
ViewerAccess = Literal["owner", "custodian", "public"]


class ReportOut(Model):
    id: UUID
    report_type: ReportType
    status: ReportStatus
    processing_status: ProcessingStatus = Field(description="AI/matching processing state for the report.")
    category: Category
    item_label: str
    description: str
    brand: str | None
    model: str | None
    lost_at_start: datetime | None
    lost_at_end: datetime | None
    found_at: datetime | None
    location_label: str = Field(description="Privacy-appropriate location text.")
    latitude: float | None
    longitude: float | None
    organisation: OrgRef | None
    location: LocationRef | None
    custody_status: CustodyStatus | None
    attributes_public: Attrs
    images: list[ImageOut] = Field(description="Only public_safe images unless viewer is owner/custodian.")
    match_count: int
    created_at: datetime
    updated_at: datetime
    viewer_access: ViewerAccess
    attributes_private: Attrs | None = Field(description="Null unless viewer is owner/custodian.")
    storage_reference: str | None = Field(description="Null unless viewer is an organisation custodian.")
    available_actions: list[str] = Field(
        description="Server-decided actions for this viewer: edit, submit, extract, withdraw, view_matches."
    )


class ExtractedField(Model):
    value: str | None
    confidence: float = Field(ge=0, le=1)


class ExtractionOut(Model):
    report_id: UUID
    status: ProcessingStatus
    provider: str
    is_fallback: bool = Field(description="True when the deterministic (non-AI) extractor produced the result.")
    category: ExtractedField
    item_label: ExtractedField
    brand: ExtractedField
    model: ExtractedField
    colour: ExtractedField
    suggested_attributes_public: Attrs
    disclaimer: str
    updated_at: datetime | None
