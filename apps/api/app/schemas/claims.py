from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .common import ClaimStatus, Category, ImageOut, Model
from .matches import MatchOut


class ClaimAnswerIn(Model):
    question_id: str
    answer: str = Field(min_length=1, max_length=1000, description="Use \"I don't remember\" when unsure.")


class ClaimCreate(Model):
    statement: str = Field(min_length=1, max_length=2000, description="Why the claimant believes it is theirs.")
    answers: list[ClaimAnswerIn] = Field(default_factory=list)
    evidence_image_ids: list[UUID] = Field(
        default_factory=list, max_length=6, description="Upload with visibility=private_evidence first."
    )


EvidenceType = Literal["photo", "receipt", "document", "text"]


class EvidenceIn(Model):
    evidence_type: EvidenceType
    image_id: UUID | None = None
    text: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _one(self) -> "EvidenceIn":
        if not self.image_id and not self.text:
            raise ValueError("Provide image_id or text")
        return self


class EvidenceOut(Model):
    id: UUID
    evidence_type: EvidenceType
    image: ImageOut | None
    text: str | None
    created_at: datetime


class ClaimAnswerOut(Model):
    question_id: str
    prompt: str
    answer: str


class ConsistencyFlag(Model):
    severity: Literal["info", "warning"]
    message: str


class AiAssistOut(Model):
    summary: str
    flags: list[ConsistencyFlag]
    disclaimer: str = "AI assistance only. A human reviewer makes the decision."


class ClaimHistoryItem(Model):
    action: str
    from_status: ClaimStatus | None
    to_status: ClaimStatus
    reason: str | None
    actor_display_name: str | None
    created_at: datetime


ClaimViewerRole = Literal["claimant", "reviewer", "staff"]


class ClaimOut(Model):
    id: UUID
    reference: str
    status: ClaimStatus
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None
    decision_reason: str | None
    match: MatchOut
    viewer_role: ClaimViewerRole
    claimant_display_name: str | None = Field(description="Shown to organisation staff only.")
    statement: str | None = Field(description="Claimant and reviewers only.")
    answers: list[ClaimAnswerOut] = Field(description="Claimant and reviewers only; empty otherwise.")
    evidence: list[EvidenceOut] = Field(description="Claimant and reviewers only; empty otherwise.")
    ai_assist: AiAssistOut | None = Field(description="Reviewers only.")
    history: list[ClaimHistoryItem]
    recovery_id: UUID | None
    available_actions: list[str] = Field(
        description="claimant: add_evidence, choose_recovery, view_recovery; reviewer: approve, reject, escalate"
    )


class ClaimListItem(Model):
    id: UUID
    reference: str
    status: ClaimStatus
    item_label: str
    category: Category
    location_name: str | None
    claimant_display_name: str | None
    score: float
    recovery_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ClaimReviewIn(Model):
    decision: Literal["approved", "rejected", "escalated"]
    reason: str = Field(min_length=10, max_length=2000)
