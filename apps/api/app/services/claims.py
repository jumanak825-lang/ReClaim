"""Claims, private evidence and human review (docs/05 §5.6, FR-016..FR-019)."""

from __future__ import annotations

import secrets
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..core import ratelimit
from ..core import config
from ..core.errors import ApiError, not_found
from ..db.models import AuditLog, Claim, ClaimEvidence, ItemImage, Match, Report, User, now
from ..db.session import db
from . import matcher
from .access import REVIEW_ROLES, report_role, require_member
from .events import audit, emit, notify, notify_org
from .matching import QUESTIONS, active_claim_for, get_match, match_access
from .reports import own_images


def claim_found(c: Claim) -> Report:
    return db().get(Report, c.found_report_id)


def claim_org(c: Claim) -> UUID | None:
    return claim_found(c).organisation_id


def claim_role(user: User, c: Claim) -> str | None:
    if c.claimant_user_id == user.id:
        return "claimant"
    role = report_role(user, claim_found(c))  # location-scoped
    if role in REVIEW_ROLES:
        return "reviewer"
    if role:
        return "staff"
    return None


def get_claim(user: User, claim_id: UUID) -> tuple[Claim, str]:
    c = db().get(Claim, claim_id)
    role = claim_role(user, c) if c else None
    if not c or not role:
        raise not_found("claim")
    return c, role


def other_approved_claim(c: Claim) -> Claim | None:
    """Another approved claim on the same found item (FR-019: one approved owner per item)."""
    return db().scalar(select(Claim).where(Claim.found_report_id == c.found_report_id,
                                           Claim.status == "approved", Claim.id != c.id))


def evidence_of(c: Claim) -> list[ClaimEvidence]:
    return list(db().scalars(select(ClaimEvidence).where(ClaimEvidence.claim_id == c.id)
                             .order_by(ClaimEvidence.created_at)))


def history_of(c: Claim) -> list[AuditLog]:
    return list(db().scalars(select(AuditLog).where(AuditLog.entity_type == "claim", AuditLog.entity_id == c.id,
                                                    AuditLog.action.like("claim.%"))
                             .order_by(AuditLog.created_at)))


def create_claim(user: User, match_id: UUID, body, *, at: datetime | None = None) -> Claim:
    m = get_match(user, match_id)
    if match_access(user, m) != "owner":
        raise ApiError(403, "FORBIDDEN", "Only the owner of the lost report can claim this item.")
    if at is None:
        ratelimit.hit("claim", str(user.id), config.settings.rate_limit_claim)
    if m.status == "dismissed":
        raise ApiError(409, "MATCH_DISMISSED", "This match was dismissed.")
    if active_claim_for(m):
        raise ApiError(409, "CLAIM_ALREADY_ACTIVE", "There is already an active claim for this match.")
    found = db().get(Report, m.found_report_id)
    if not found.organisation_id:
        raise ApiError(422, "CLAIM_NOT_SUPPORTED",
                       "Claims on items held by individual finders are not supported in the demo.")
    qmap = dict(QUESTIONS)
    for a in body.answers:
        if a.question_id not in qmap:
            raise ApiError(422, "UNKNOWN_QUESTION", f"Unknown question {a.question_id}.")
    images = own_images(user, body.evidence_image_ids)
    c = Claim(
        reference="CLM-" + secrets.token_hex(3).upper(), match_id=m.id, found_report_id=found.id,
        claimant_user_id=user.id, statement=body.statement, status="pending",
        verification_answers=[{"question_id": a.question_id, "prompt": qmap[a.question_id], "answer": a.answer}
                              for a in body.answers],
    )
    if at:
        c.created_at = c.updated_at = at
    db().add(c)
    _flush_or_conflict()
    for img in images:
        img.visibility, img.claim_id = "private_evidence", c.id
        db().add(ClaimEvidence(claim_id=c.id, evidence_type="photo", image_id=img.id))
    m.status = "claim_started"
    audit(user, found.organisation_id, "claim.created", "claim", c.id, after={"from": None, "to": "pending"})
    notify(user.id, "claim.submitted", "Claim submitted",
           f"Your claim {c.reference} is waiting for review.", "claim", c.id)
    notify_org(found.organisation_id, found.location_id, REVIEW_ROLES, "claim.new_for_review",
               "New claim to review", f"Claim {c.reference} for {found.item_label}.", "claim", c.id)
    emit("claim.created", "claim", c.id, found.organisation_id,
         {"claim_id": str(c.id), "case_reference": c.reference, "status": c.status,
          "item_label": found.item_label})
    return c


def _flush_or_conflict() -> None:
    try:
        with db().begin_nested():
            db().flush()
    except IntegrityError as exc:
        name = getattr(getattr(exc.orig, "diag", None), "constraint_name", "") or ""
        if "approved_per_found" in name:
            raise ApiError(409, "FOUND_ITEM_ALREADY_CLAIMED", "Another claim on this item has already been approved.")
        if "active_per_match" in name:
            raise ApiError(409, "CLAIM_ALREADY_ACTIVE", "There is already an active claim for this match.")
        raise


def add_evidence(user: User, claim_id: UUID, body) -> Claim:
    c, role = get_claim(user, claim_id)
    if role != "claimant":
        raise ApiError(403, "FORBIDDEN", "Only the claimant can add evidence.")
    if c.status not in {"pending", "escalated"}:
        raise ApiError(409, "CLAIM_CLOSED", "Evidence can only be added while the claim is under review.")
    if body.image_id:
        (img,) = own_images(user, [body.image_id])
        img.visibility, img.claim_id = "private_evidence", c.id
    db().add(ClaimEvidence(claim_id=c.id, evidence_type=body.evidence_type, image_id=body.image_id,
                           text_value=body.text))
    c.updated_at = now()
    return c


def review_claim(user: User, claim_id: UUID, decision: str, reason: str) -> Claim:
    c, role = get_claim(user, claim_id)
    if role != "reviewer":
        raise ApiError(403, "NOT_A_REVIEWER", "Only authorised reviewers can decide claims.")
    if c.claimant_user_id == user.id:
        raise ApiError(403, "SELF_REVIEW_FORBIDDEN", "You cannot review your own claim.")
    allowed = {"pending": {"approved", "rejected", "escalated"}, "escalated": {"approved", "rejected"}}
    if decision not in allowed.get(c.status, set()):
        raise ApiError(409, "CLAIM_NOT_REVIEWABLE", "This claim cannot be reviewed in its current state.",
                       {"status": c.status, "decision": decision})
    if decision == "approved":
        winner = other_approved_claim(c)
        if winner:
            # Other pending claims on the item stay pending; a reviewer must reject them with a reason.
            raise ApiError(409, "FOUND_ITEM_ALREADY_CLAIMED",
                           "Another claim on this item has already been approved.",
                           {"approved_claim_reference": winner.reference})
    before = c.status
    c.status = decision
    c.updated_at = now()
    if decision != "escalated":
        c.decision_by_user_id, c.decision_reason, c.decided_at = user.id, reason, now()
    _flush_or_conflict()  # the partial unique index is the backstop against concurrent approvals
    m = db().get(Match, c.match_id)
    if decision == "approved":
        m.status = "confirmed"
    elif decision == "rejected":
        m.status = "dismissed"
    org = claim_org(c)
    audit(user, org, f"claim.{decision}", "claim", c.id, reason, before={"status": before},
          after={"from": before, "to": decision})
    titles = {"approved": "Claim approved", "rejected": "Claim not approved", "escalated": "Claim escalated"}
    bodies = {
        "approved": f"Claim {c.reference} was approved. Choose collection or delivery.",
        "rejected": f"Claim {c.reference} was not approved.",
        "escalated": f"Claim {c.reference} needs further review.",
    }
    notify(c.claimant_user_id, f"claim.{decision}", titles[decision], bodies[decision], "claim", c.id)
    event = "claim.flagged_for_review" if decision == "escalated" else f"claim.{decision}"
    emit(event, "claim", c.id, org, {"claim_id": str(c.id), "case_reference": c.reference, "status": c.status})
    return c


def my_claims(user: User) -> list[Claim]:
    return list(db().scalars(select(Claim).where(Claim.claimant_user_id == user.id)
                             .order_by(Claim.created_at.desc())))


def org_claims(user: User, org_id: UUID, status: str | None) -> list[Claim]:
    require_member(user, org_id)
    q = select(Claim).join(Report, Report.id == Claim.found_report_id).where(Report.organisation_id == org_id)
    if status:
        q = q.where(Claim.status == status)
    cs = db().scalars(q.order_by(Claim.created_at.desc()))
    return [c for c in cs if report_role(user, claim_found(c))]  # location-scoped


def ai_assist(c: Claim) -> tuple[str, list[tuple[str, str]]]:
    """Advisory consistency flags for reviewers. Never changes the claim (CLAUDE.md rule 5)."""
    found = claim_found(c)
    answers = " ".join(a["answer"] for a in c.verification_answers).lower()
    answer_tokens = matcher._tokens(answers)
    flags: list[tuple[str, str]] = []
    winner = other_approved_claim(c) if c.status in {"pending", "escalated"} else None
    if winner:
        flags.append(("warning", f"Claim {winner.reference} on this item is already approved. "
                                 "This claim cannot be approved."))
    hits = 0
    for key, value in found.attributes_private.items():
        if answer_tokens & matcher._tokens(str(value)):
            hits += 1
            flags.append(("info", f"An answer contains terms consistent with the recorded '{key.replace('_', ' ')}'."))
    if found.attributes_private and not hits:
        flags.append(("warning", "No answer referenced the item's recorded private details."))
    if not evidence_of(c):
        flags.append(("info", "No supporting evidence uploaded."))
    dont = sum(1 for a in c.verification_answers
               if "don't remember" in a["answer"].lower() or "dont remember" in a["answer"].lower())
    if dont:
        flags.append(("info", f"{dont} answer(s) were 'I don't remember'."))
    total = len(found.attributes_private)
    summary = (f"Answers align with {hits} of {total} recorded private detail(s)." if total
               else "The found report has no recorded private details to compare against.")
    return summary, flags


def image_of(e: ClaimEvidence) -> ItemImage | None:
    return db().get(ItemImage, e.image_id) if e.image_id else None
