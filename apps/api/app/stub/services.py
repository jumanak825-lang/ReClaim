"""STUB business logic.

Implements the demo-path state machines and permission rules from
docs/03-05 against the in-memory store, so the frontend gets realistic
behaviour (403s, 409s, status transitions). The real backend replaces
this module with Postgres-backed services; the routers and schemas stay.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from ..core.config import settings
from ..core.envelope import request_id_var
from ..core.errors import ApiError, not_found
from . import matcher
from .models import (
    AuditLog,
    Claim,
    ClaimHistory,
    Evidence,
    Image,
    Match,
    Notification,
    OutboxEvent,
    Payment,
    Recovery,
    RecoveryEvent,
    Report,
    Session,
    User,
    now,
)
from .store import db

REVIEW_ROLES = {"reviewer", "manager", "admin"}
ADMIN_ROLES = {"manager", "admin"}
ACTIVE_CLAIM = {"pending", "escalated", "approved"}
OPEN_RECOVERY = {"created", "awaiting_payment", "preparing", "ready_for_pickup", "dispatched", "in_transit", "received"}

# ---------------------------------------------------------------- auth ----


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def register(email: str, password: str, display_name: str) -> User:
    if db.user_by_email(email):
        # Docs/02: don't leak whether an email exists. Return a generic conflict.
        raise ApiError(409, "REGISTRATION_FAILED", "Could not create an account with these details.")
    user = User(email=email.lower(), password_hash=hash_password(password), display_name=display_name)
    db.users[user.id] = user
    return user


def login(email: str, password: str) -> User:
    user = db.user_by_email(email)
    if not user or not verify_password(password, user.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    return user


def create_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.sessions[token] = Session(user_id=user.id, expires_at=now() + timedelta(hours=settings.session_ttl_hours))
    return token


def session_user(token: str | None) -> User | None:
    if not token or token not in db.sessions:
        return None
    s = db.sessions[token]
    if s.expires_at < now():
        del db.sessions[token]
        return None
    return db.users.get(s.user_id)


def end_session(token: str | None) -> None:
    if token:
        db.sessions.pop(token, None)


# ----------------------------------------------------------- membership ----


def memberships_of(user: User):
    return [m for m in db.memberships if m.user_id == user.id]


def role_in(user: User, org_id: UUID | None) -> str | None:
    if org_id is None:
        return None
    return next((m.role for m in db.memberships if m.user_id == user.id and m.organisation_id == org_id), None)


def can_review(user: User, org_id: UUID | None) -> bool:
    return role_in(user, org_id) in REVIEW_ROLES


def require_member(user: User, org_id: UUID, roles: set[str] | None = None) -> str:
    if org_id not in db.organisations:
        raise not_found("organisation")
    role = role_in(user, org_id)
    if role is None:
        raise ApiError(403, "NOT_A_MEMBER", "You are not a member of this organisation.")
    if roles and role not in roles:
        raise ApiError(403, "INSUFFICIENT_ROLE", "Your role does not allow this action.")
    return role


# ---------------------------------------------------- side effects ----


def notify(user_id: UUID | None, type_: str, title: str, body: str, entity_type: str | None, entity_id: UUID | None):
    if user_id:
        db.notifications.append(Notification(user_id, type_, title, body, entity_type, entity_id))


def notify_org(org_id: UUID | None, roles: set[str], type_: str, title: str, body: str, et: str, eid: UUID):
    for m in db.memberships:
        if m.organisation_id == org_id and m.role in roles:
            notify(m.user_id, type_, title, body, et, eid)


def audit(actor: User | None, org_id: UUID | None, action: str, et: str, eid: UUID, reason: str | None = None):
    db.audit_logs.append(
        AuditLog(actor.id if actor else None, org_id, action, et, eid, reason, request_id_var.get())
    )


def emit(event_type: str, aggregate_type: str, aggregate_id: UUID, org_id: UUID | None, data: dict[str, Any]):
    """Record an outbox event. The stub never sends it to Zapier."""
    db.outbox.append(OutboxEvent(event_type, aggregate_type, aggregate_id, org_id, data))


# --------------------------------------------------------------- images ----

ALLOWED_TYPES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
    "application/pdf": [b"%PDF"],
}


def save_upload(user: User, content_type: str, data: bytes, visibility: str) -> Image:
    if content_type not in ALLOWED_TYPES:
        raise ApiError(415, "UNSUPPORTED_FILE_TYPE", "Allowed types: JPEG, PNG, WebP, PDF.")
    if content_type == "application/pdf" and visibility != "private_evidence":
        raise ApiError(422, "PDF_EVIDENCE_ONLY", "PDFs can only be uploaded as private evidence.")
    if not any(data.startswith(sig) for sig in ALLOWED_TYPES[content_type]):
        raise ApiError(415, "FILE_SIGNATURE_MISMATCH", "File content does not match its type.")
    if len(data) > settings.max_upload_bytes:
        raise ApiError(413, "FILE_TOO_LARGE", "Files must be 8 MB or smaller.")
    if not data:
        raise ApiError(400, "EMPTY_FILE", "The file is empty.")
    img = Image(uploader_id=user.id, content_type=content_type, data=data, visibility=visibility)
    db.images[img.id] = img
    return img


def _claim_images(user: User, image_ids: list[UUID]) -> list[UUID]:
    for iid in image_ids:
        img = db.images.get(iid)
        if not img or img.uploader_id != user.id:
            raise ApiError(422, "INVALID_IMAGE", f"Image {iid} was not uploaded by you.")
    return image_ids


def can_view_image(user: User, img: Image) -> bool:
    if img.uploader_id == user.id:
        return True
    if img.report_id and img.report_id in db.reports:
        access = report_access(user, db.reports[img.report_id])
        if access in {"owner", "custodian"}:
            return True
        if access == "public" and img.visibility == "public_safe":
            return True
    if img.claim_id and img.claim_id in db.claims:
        return claim_role(user, db.claims[img.claim_id]) in {"claimant", "reviewer"}
    return False


# -------------------------------------------------------------- reports ----


def refresh_report(r: Report) -> Report:
    if r.status == "processing" and r.processing_until and now() >= r.processing_until:
        r.status = "active"
        r.updated_at = now()
    return r


def processing_status(r: Report) -> str:
    refresh_report(r)
    if r.status in {"draft"}:
        return "not_started"
    if r.status in {"submitted", "processing"}:
        return "processing"
    return "completed"


def report_access(user: User, r: Report) -> str | None:
    if user.id in (r.owner_user_id, r.created_by_user_id):
        return "owner"
    if r.organisation_id and role_in(user, r.organisation_id):
        return "custodian"
    for m in db.matches.values():
        if m.status == "dismissed" or r.id not in (m.lost_report_id, m.found_report_id):
            continue
        other = db.reports[m.found_report_id if r.report_type == "lost" else m.lost_report_id]
        if user.id in (other.owner_user_id, other.created_by_user_id) or (
            other.organisation_id and role_in(user, other.organisation_id)
        ):
            return "public"
    return None


def get_report(user: User, report_id: UUID) -> tuple[Report, str]:
    r = db.reports.get(report_id)
    access = report_access(user, r) if r else None
    if not r or not access or (r.status == "draft" and access == "public"):
        raise not_found("report")
    return refresh_report(r), access


def require_report_editor(user: User, report_id: UUID) -> Report:
    r, access = get_report(user, report_id)
    if access == "public":
        raise ApiError(403, "FORBIDDEN", "You cannot change this report.")
    return r


def _attach_images(r: Report, image_ids: list[UUID]) -> None:
    r.image_ids = list(image_ids)
    for iid in image_ids:
        db.images[iid].report_id = r.id


def create_lost(user: User, body) -> Report:
    _claim_images(user, body.image_ids)
    r = Report(
        report_type="lost",
        category=body.category,
        item_label=body.item_label,
        description=body.description,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        brand=body.brand,
        model=body.model,
        lost_at_start=body.lost_at_start,
        lost_at_end=body.lost_at_end,
        location_label=body.last_location.label,
        latitude=body.last_location.latitude,
        longitude=body.last_location.longitude,
        attributes_public=dict(body.attributes_public),
        attributes_private=dict(body.attributes_private),
    )
    db.reports[r.id] = r
    _attach_images(r, body.image_ids)
    audit(user, None, "report.created", "lost_report", r.id)
    if not body.as_draft:
        submit(user, r)
    return r


def create_found(user: User, body) -> Report:
    _claim_images(user, body.image_ids)
    org = loc = None
    if body.custody_status == "finder_holds":
        if not body.found_location:
            raise ApiError(422, "FOUND_LOCATION_REQUIRED", "Tell us where you found the item.")
    else:
        if body.custody_status == "released":
            raise ApiError(422, "INVALID_CUSTODY", "A new report cannot start as released.")
        if not body.organisation_id or not body.location_id:
            raise ApiError(422, "ORGANISATION_REQUIRED", "Choose the organisation and location holding the item.")
        org = db.organisations.get(body.organisation_id)
        loc = db.locations.get(body.location_id)
        if not org or not loc or loc.organisation_id != org.id:
            raise ApiError(422, "INVALID_LOCATION", "That location does not belong to the organisation.")
        if body.custody_status == "organisation_holds" and not role_in(user, org.id):
            raise ApiError(403, "NOT_A_MEMBER", "Only organisation staff can record items their organisation holds.")
    is_staff = org is not None and role_in(user, org.id) is not None
    if body.storage_reference and not is_staff:
        raise ApiError(403, "FORBIDDEN", "Only organisation staff can set a storage reference.")
    r = Report(
        report_type="found",
        category=body.category,
        item_label=body.item_label,
        description=body.description,
        owner_user_id=None if is_staff else user.id,
        created_by_user_id=user.id,
        organisation_id=org.id if org else None,
        location_id=loc.id if loc else None,
        brand=body.brand,
        model=body.model,
        found_at=body.found_at,
        location_label=f"{loc.name}, {org.name}" if loc and org else body.found_location.label,
        latitude=loc.latitude if loc else (body.found_location.latitude if body.found_location else None),
        longitude=loc.longitude if loc else (body.found_location.longitude if body.found_location else None),
        custody_status=body.custody_status,
        attributes_public=dict(body.attributes_public),
        attributes_private=dict(body.attributes_private),
        storage_reference=body.storage_reference,
    )
    db.reports[r.id] = r
    _attach_images(r, body.image_ids)
    audit(user, r.organisation_id, "report.created", "found_report", r.id)
    if not body.as_draft:
        submit(user, r)
    return r


def submit(user: User, r: Report) -> Report:
    if r.status != "draft":
        raise ApiError(409, "REPORT_NOT_DRAFT", "Only draft reports can be submitted.")
    if r.report_type == "lost" and not r.location_label:
        raise ApiError(422, "LOCATION_REQUIRED", "Add the last known location.")
    r.status = "processing"
    r.processing_until = now() + timedelta(seconds=settings.stub_processing_seconds)
    r.updated_at = now()
    run_matching(r)
    return r


def update_report(user: User, report_id: UUID, body) -> Report:
    r = require_report_editor(user, report_id)
    if r.status in {"resolved", "withdrawn", "expired", "rejected"}:
        raise ApiError(409, "REPORT_CLOSED", "This report can no longer be edited.")
    data = body.model_dump(exclude_unset=True)
    if "image_ids" in data:
        _claim_images(user, data["image_ids"])
        _attach_images(r, data.pop("image_ids"))
    if "storage_reference" in data and not (r.organisation_id and role_in(user, r.organisation_id)):
        raise ApiError(403, "FORBIDDEN", "Only organisation staff can set a storage reference.")
    if r.report_type == "lost" and data.get("found_at") is not None:
        raise ApiError(422, "INVALID_FIELD", "found_at applies to found reports only.")
    if r.report_type == "found" and (data.get("lost_at_start") or data.get("lost_at_end")):
        raise ApiError(422, "INVALID_FIELD", "lost_at_* applies to lost reports only.")
    place = data.pop("last_location", None)
    if place:
        if r.report_type == "found" and r.organisation_id:
            raise ApiError(422, "INVALID_FIELD", "Organisation-held items use the organisation location.")
        r.location_label, r.latitude, r.longitude = place["label"], place.get("latitude"), place.get("longitude")
    for key, value in data.items():
        setattr(r, key, value)
    r.updated_at = now()
    if r.status in {"processing", "active"}:
        run_matching(r)
    return r


def withdraw(user: User, report_id: UUID) -> Report:
    r = require_report_editor(user, report_id)
    if r.status in {"resolved", "withdrawn"}:
        raise ApiError(409, "REPORT_CLOSED", "This report is already closed.")
    if any(c.status in ACTIVE_CLAIM for c in claims_for_report(r)):
        raise ApiError(409, "REPORT_HAS_ACTIVE_CLAIM", "Resolve the open claim before withdrawing.")
    r.status = "withdrawn"
    r.updated_at = now()
    audit(user, r.organisation_id, "report.withdrawn", f"{r.report_type}_report", r.id)
    return r


def my_reports(user: User, type_: str | None, status: str | None) -> list[Report]:
    out = []
    for r in db.reports.values():
        if user.id not in (r.owner_user_id, r.created_by_user_id):
            continue
        refresh_report(r)
        if type_ and r.report_type != type_:
            continue
        if status and r.status != status:
            continue
        out.append(r)
    return sorted(out, key=lambda r: r.created_at, reverse=True)


# ----------------------------------------------------------- extraction ----

COLOURS = ["black", "white", "silver", "grey", "gray", "gold", "red", "blue", "navy", "green", "brown", "pink",
           "purple", "yellow", "orange", "beige"]
BRANDS = ["northwind", "contoso", "fabrikam", "example"]
CATEGORY_WORDS = {
    "electronics": ["laptop", "tablet", "headphones", "earbuds", "camera", "charger", "notebook"],
    "phone": ["phone", "smartphone", "mobile"],
    "bag": ["bag", "backpack", "suitcase", "handbag", "tote", "luggage"],
    "wallet": ["wallet", "purse", "cardholder"],
    "keys": ["key", "keys", "fob", "keyring"],
    "documents": ["passport", "card", "licence", "license", "document"],
    "clothing": ["jacket", "coat", "scarf", "hat", "sweater", "hoodie"],
    "jewellery": ["ring", "necklace", "bracelet", "earring", "watch"],
    "eyewear": ["glasses", "sunglasses", "spectacles"],
    "umbrella": ["umbrella"],
    "toy": ["toy", "teddy", "doll"],
}


def start_extraction(user: User, report_id: UUID) -> Report:
    r = require_report_editor(user, report_id)
    text = f"{r.item_label} {r.description}".lower()
    words = text.replace(",", " ").replace(".", " ").split()
    cat, label = None, None
    for c, keys in CATEGORY_WORDS.items():
        hit = next((w for w in words if w in keys), None)
        if hit:
            cat, label = c, hit.capitalize()
            break
    colour = next((c for c in COLOURS if c in words), None)
    brand = next((b.capitalize() for b in BRANDS if b in words), None)
    r.extraction = {
        "category": (cat, 0.6 if cat else 0.0),
        "item_label": (label, 0.6 if label else 0.0),
        "brand": (brand, 0.5 if brand else 0.0),
        "model": (None, 0.0),
        "colour": (colour, 0.7 if colour else 0.0),
    }
    r.extraction_ready_at = now() + timedelta(seconds=settings.stub_processing_seconds)
    return r


# ------------------------------------------------------------- matching ----


def _found_location_text(found: Report) -> str:
    if found.location_id:
        loc = db.locations[found.location_id]
        return f"{loc.name}, {db.organisations[loc.organisation_id].name}"
    return found.location_label


def run_matching(r: Report) -> None:
    others = [o for o in db.reports.values() if o.report_type != r.report_type and o.status in {"processing", "active"}]
    for o in others:
        lost, found = (r, o) if r.report_type == "lost" else (o, r)
        if lost.owner_user_id and lost.owner_user_id == found.owner_user_id:
            continue
        score, comps, why = matcher.score_pair(lost, found, _found_location_text(found))
        existing = next(
            (m for m in db.matches.values()
             if m.lost_report_id == lost.id and m.found_report_id == found.id
             and m.matcher_version == matcher.MATCHER_VERSION),
            None,
        )
        if existing:
            existing.score, existing.components, existing.explanation = score, comps, why
            continue
        if score < matcher.SURFACE_THRESHOLD:
            continue
        m = Match(lost.id, found.id, score, comps, why, matcher.MATCHER_VERSION)
        db.matches[m.id] = m
        notify(lost.owner_user_id, "match.found", "Potential match found",
               f"A found {found.item_label.lower()} may match your report. Review it privately.", "match", m.id)
        if found.organisation_id:
            notify_org(found.organisation_id, REVIEW_ROLES, "match.found", "New candidate match",
                       f"A lost report may match found item: {found.item_label}.", "match", m.id)
        if score >= matcher.STRONG_THRESHOLD:
            emit("match.high_priority", "match", m.id, found.organisation_id,
                 {"match_id": str(m.id), "score": score, "item_label": found.item_label})


def match_visible(m: Match) -> bool:
    lost, found = db.reports[m.lost_report_id], db.reports[m.found_report_id]
    refresh_report(lost)
    refresh_report(found)
    return lost.status in {"active", "resolved"} and found.status in {"active", "resolved"}


def match_access(user: User, m: Match) -> str | None:
    lost, found = db.reports[m.lost_report_id], db.reports[m.found_report_id]
    if lost.owner_user_id == user.id:
        return "owner"
    if found.organisation_id and role_in(user, found.organisation_id):
        return "custodian"
    if user.id in (found.owner_user_id, found.created_by_user_id):
        return "finder"
    return None


def get_match(user: User, match_id: UUID) -> Match:
    m = db.matches.get(match_id)
    if not m or not match_access(user, m) or not match_visible(m):
        raise not_found("match")
    return m


def matches_for_report(user: User, report_id: UUID) -> list[Match]:
    r, access = get_report(user, report_id)
    if access == "public":
        return []
    ms = [
        m for m in db.matches.values()
        if r.id in (m.lost_report_id, m.found_report_id) and match_visible(m)
        and not (m.status == "dismissed" and access == "owner")
    ]
    return sorted(ms, key=lambda m: m.score, reverse=True)


def my_matches(user: User) -> list[Match]:
    ms = [
        m for m in db.matches.values()
        if db.reports[m.lost_report_id].owner_user_id == user.id and m.status != "dismissed" and match_visible(m)
    ]
    return sorted(ms, key=lambda m: m.score, reverse=True)


def dismiss_match(user: User, match_id: UUID) -> Match:
    m = get_match(user, match_id)
    if match_access(user, m) != "owner":
        raise ApiError(403, "FORBIDDEN", "Only the owner of the lost report can dismiss a match.")
    if m.status != "candidate":
        raise ApiError(409, "MATCH_NOT_DISMISSABLE", "This match has an active claim.")
    m.status = "dismissed"
    return m


def active_claim_for(m: Match) -> Claim | None:
    return next((c for c in db.claims.values() if c.match_id == m.id and c.status in ACTIVE_CLAIM), None)


QUESTIONS = [
    ("q_marks", "Describe any distinctive marks, stickers, damage or engravings on the item."),
    ("q_contents", "What was inside, attached to or stored with the item (case, accessories, contents)?"),
    ("q_when_where", "When and where exactly do you think you lost it?"),
    ("q_other", "Is there anything else only the owner would know about this item?"),
]


def verification_questions(user: User, match_id: UUID) -> list[tuple[str, str]]:
    m = get_match(user, match_id)
    if match_access(user, m) != "owner":
        raise ApiError(403, "FORBIDDEN", "Only the owner of the lost report can claim this item.")
    return QUESTIONS


# --------------------------------------------------------------- claims ----


def claims_for_report(r: Report) -> list[Claim]:
    mids = {m.id for m in db.matches.values() if r.id in (m.lost_report_id, m.found_report_id)}
    return [c for c in db.claims.values() if c.match_id in mids]


def claim_org(c: Claim) -> UUID | None:
    return db.reports[db.matches[c.match_id].found_report_id].organisation_id


def claim_role(user: User, c: Claim) -> str | None:
    if c.claimant_user_id == user.id:
        return "claimant"
    org = claim_org(c)
    if can_review(user, org):
        return "reviewer"
    if role_in(user, org):
        return "staff"
    return None


def get_claim(user: User, claim_id: UUID) -> tuple[Claim, str]:
    c = db.claims.get(claim_id)
    role = claim_role(user, c) if c else None
    if not c or not role:
        raise not_found("claim")
    return c, role


def create_claim(user: User, match_id: UUID, body, *, at: datetime | None = None) -> Claim:
    m = get_match(user, match_id)
    if match_access(user, m) != "owner":
        raise ApiError(403, "FORBIDDEN", "Only the owner of the lost report can claim this item.")
    if m.status == "dismissed":
        raise ApiError(409, "MATCH_DISMISSED", "This match was dismissed.")
    if active_claim_for(m):
        raise ApiError(409, "CLAIM_ALREADY_ACTIVE", "There is already an active claim for this match.")
    found = db.reports[m.found_report_id]
    if not found.organisation_id:
        raise ApiError(422, "CLAIM_NOT_SUPPORTED",
                       "Claims on items held by individual finders are not supported in the demo.")
    qmap = dict(QUESTIONS)
    for a in body.answers:
        if a.question_id not in qmap:
            raise ApiError(422, "UNKNOWN_QUESTION", f"Unknown question {a.question_id}.")
    _claim_images(user, body.evidence_image_ids)
    c = Claim(
        reference="CLM-" + secrets.token_hex(3).upper(),
        match_id=m.id,
        claimant_user_id=user.id,
        statement=body.statement,
        answers=[{"question_id": a.question_id, "prompt": qmap[a.question_id], "answer": a.answer}
                 for a in body.answers],
    )
    if at:
        c.created_at = c.updated_at = at
    for iid in body.evidence_image_ids:
        img = db.images[iid]
        img.visibility, img.claim_id = "private_evidence", c.id
        c.evidence.append(Evidence("photo", image_id=iid))
    c.history.append(ClaimHistory("claim.created", None, "pending", None, user.id))
    db.claims[c.id] = c
    m.status = "claim_started"
    audit(user, found.organisation_id, "claim.created", "claim", c.id)
    notify(user.id, "claim.submitted", "Claim submitted",
           f"Your claim {c.reference} is waiting for review.", "claim", c.id)
    notify_org(found.organisation_id, REVIEW_ROLES, "claim.new_for_review", "New claim to review",
               f"Claim {c.reference} for {found.item_label}.", "claim", c.id)
    emit("claim.created", "claim", c.id, found.organisation_id,
         {"claim_id": str(c.id), "case_reference": c.reference, "status": c.status})
    return c


def add_evidence(user: User, claim_id: UUID, body) -> Claim:
    c, role = get_claim(user, claim_id)
    if role != "claimant":
        raise ApiError(403, "FORBIDDEN", "Only the claimant can add evidence.")
    if c.status not in {"pending", "escalated"}:
        raise ApiError(409, "CLAIM_CLOSED", "Evidence can only be added while the claim is under review.")
    if body.image_id:
        _claim_images(user, [body.image_id])
        img = db.images[body.image_id]
        img.visibility, img.claim_id = "private_evidence", c.id
    c.evidence.append(Evidence(body.evidence_type, image_id=body.image_id, text=body.text))
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
    before = c.status
    c.status = decision
    c.updated_at = now()
    if decision != "escalated":
        c.decision_by_user_id, c.decision_reason, c.decided_at = user.id, reason, now()
    c.history.append(ClaimHistory(f"claim.{decision}", before, decision, reason, user.id))
    m = db.matches[c.match_id]
    if decision == "approved":
        m.status = "confirmed"
    elif decision == "rejected":
        m.status = "dismissed"
    org = claim_org(c)
    audit(user, org, f"claim.{decision}", "claim", c.id, reason)
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
    return sorted((c for c in db.claims.values() if c.claimant_user_id == user.id),
                  key=lambda c: c.created_at, reverse=True)


def org_claims(user: User, org_id: UUID, status: str | None) -> list[Claim]:
    require_member(user, org_id)
    cs = [c for c in db.claims.values() if claim_org(c) == org_id and (not status or c.status == status)]
    return sorted(cs, key=lambda c: c.created_at, reverse=True)


def ai_assist(c: Claim) -> tuple[str, list[tuple[str, str]]]:
    found = db.reports[db.matches[c.match_id].found_report_id]
    answers = " ".join(a["answer"] for a in c.answers).lower()
    answer_tokens = matcher._tokens(answers)
    flags: list[tuple[str, str]] = []
    hits = 0
    for key, value in found.attributes_private.items():
        if answer_tokens & matcher._tokens(value):
            hits += 1
            flags.append(("info", f"An answer contains terms consistent with the recorded '{key.replace('_', ' ')}'."))
    if found.attributes_private and not hits:
        flags.append(("warning", "No answer referenced the item's recorded private details."))
    if not c.evidence:
        flags.append(("info", "No supporting evidence uploaded."))
    dont = sum(1 for a in c.answers if "don't remember" in a["answer"].lower() or "dont remember" in a["answer"].lower())
    if dont:
        flags.append(("info", f"{dont} answer(s) were 'I don't remember'."))
    total = len(found.attributes_private)
    summary = (
        f"Answers align with {hits} of {total} recorded private detail(s)."
        if total else "The found report has no recorded private details to compare against."
    )
    return summary, flags


# ----------------------------------------------------------- recoveries ----


def recovery_for_claim(c: Claim) -> Recovery | None:
    return next((r for r in db.recoveries.values() if r.claim_id == c.id), None)


def refresh_recovery(rec: Recovery) -> Recovery:
    if rec.status == "dispatched" and rec.dispatched_at and \
            now() - rec.dispatched_at >= timedelta(seconds=settings.stub_courier_seconds):
        _advance_courier(rec)
    return rec


def _advance_courier(rec: Recovery) -> None:
    rec.status = "in_transit"
    rec.updated_at = now()
    rec.events.append(RecoveryEvent("in_transit", "In transit with courier (simulated).", True))
    c = db.claims[rec.claim_id]
    notify(c.claimant_user_id, "recovery.in_transit", "Item in transit",
           "Your item is on its way (simulated courier).", "recovery", rec.id)


def advance_courier(rec_id: UUID) -> Recovery:
    rec = db.recoveries.get(rec_id)
    if not rec:
        raise not_found("recovery")
    if rec.status != "dispatched":
        raise ApiError(409, "RECOVERY_NOT_DISPATCHED", "Only dispatched recoveries can advance.")
    _advance_courier(rec)
    return rec


def recovery_role(user: User, rec: Recovery) -> str | None:
    c = db.claims[rec.claim_id]
    if c.claimant_user_id == user.id:
        return "claimant"
    if role_in(user, claim_org(c)):
        return "staff"
    return None


def get_recovery(user: User, rec_id: UUID) -> tuple[Recovery, str]:
    rec = db.recoveries.get(rec_id)
    role = recovery_role(user, rec) if rec else None
    if not rec or not role:
        raise not_found("recovery")
    return refresh_recovery(rec), role


def _quote(rec: Recovery) -> None:
    c = db.claims[rec.claim_id]
    found = db.reports[db.matches[c.match_id].found_report_id]
    loc = db.locations.get(found.location_id) if found.location_id else None
    domestic = loc is not None and rec.address and rec.address["country_code"] == loc.country_code
    rec.quote_minor = 1500 if domestic else 4500
    rec.currency = "USD"
    rec.quote_expires_at = now() + timedelta(hours=24)


def _event(rec: Recovery, user: User | None, type_: str, desc: str, simulated: bool = False) -> None:
    rec.events.append(RecoveryEvent(type_, desc, simulated, user.id if user else None))
    rec.updated_at = now()


def create_recovery(user: User, claim_id: UUID, body) -> Recovery:
    c, role = get_claim(user, claim_id)
    if role != "claimant":
        raise ApiError(403, "FORBIDDEN", "Only the claimant can choose a recovery method.")
    if c.status != "approved":
        raise ApiError(409, "CLAIM_NOT_APPROVED", "Recovery is available only after the claim is approved.")
    if recovery_for_claim(c):
        raise ApiError(409, "RECOVERY_EXISTS", "A recovery already exists for this claim.")
    rec = Recovery(claim_id=c.id, method=body.method, status="created")
    rec.events.append(RecoveryEvent("claim_approved", "Claim approved.", False, c.decision_by_user_id, c.decided_at or now()))
    if body.method == "collection":
        rec.preferred_window_start, rec.preferred_window_end = body.preferred_window_start, body.preferred_window_end
        _event(rec, user, "method_selected", "Collection selected.")
        rec.status = "preparing"
        _event(rec, None, "preparing", "Staff are preparing the item for collection.")
    else:
        rec.address = body.address.model_dump()
        _quote(rec)
        _event(rec, user, "method_selected", "Delivery selected.")
        rec.status = "awaiting_payment"
        _event(rec, None, "awaiting_payment", "Waiting for delivery payment.")
        emit("recovery.delivery_requested", "recovery", rec.id, claim_org(c),
             {"recovery_id": str(rec.id), "case_reference": c.reference, "country_code": rec.address["country_code"]})
    db.recoveries[rec.id] = rec
    audit(user, claim_org(c), "recovery.created", "recovery", rec.id)
    return rec


def _require(rec: Recovery, role: str, needed: str, method: str | None, statuses: set[str]) -> None:
    if role != needed:
        raise ApiError(403, "FORBIDDEN", "You cannot perform this recovery action.")
    if method and rec.method != method:
        raise ApiError(409, "WRONG_RECOVERY_METHOD", f"This action applies to {method} only.")
    if rec.status not in statuses:
        raise ApiError(409, "RECOVERY_INVALID_STATE", "This action is not allowed in the current state.",
                       {"status": rec.status})


def refresh_quote(user: User, rec_id: UUID) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    _require(rec, role, "claimant", "delivery", {"awaiting_payment"})
    _quote(rec)
    return rec


def confirm_collection(user: User, rec_id: UUID) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    _require(rec, role, "staff", "collection", {"preparing"})
    rec.status = "ready_for_pickup"
    rec.pickup_token = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
    rec.pickup_token_expires_at = now() + timedelta(hours=72)
    _event(rec, user, "ready_for_pickup", "Ready for collection.")
    c = db.claims[rec.claim_id]
    notify(c.claimant_user_id, "recovery.ready_for_pickup", "Ready for collection",
           "Your item is ready. Show your pickup code at the desk.", "recovery", rec.id)
    audit(user, claim_org(c), "recovery.ready_for_pickup", "recovery", rec.id)
    return rec


def validate_token(user: User, rec_id: UUID, token: str) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    _require(rec, role, "staff", "collection", {"ready_for_pickup"})
    if rec.pickup_token_expires_at and rec.pickup_token_expires_at < now():
        raise ApiError(409, "PICKUP_TOKEN_EXPIRED", "This pickup code has expired.")
    norm = lambda s: s.replace("-", "").replace(" ", "").upper()  # noqa: E731
    if not rec.pickup_token or not hmac.compare_digest(norm(token), norm(rec.pickup_token)):
        raise ApiError(400, "INVALID_PICKUP_TOKEN", "That pickup code is not valid.")
    rec.pickup_token = None
    rec.status = "received"
    _event(rec, user, "handed_over", "Item handed over at the desk.")
    _complete(user, rec)
    return rec


def dispatch(user: User, rec_id: UUID) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    _require(rec, role, "staff", "delivery", {"preparing"})
    rec.status = "dispatched"
    rec.dispatched_at = now()
    rec.tracking_reference = "SIM-" + secrets.token_hex(4).upper()
    _event(rec, user, "dispatched", "Dispatched with courier (simulated).", True)
    c = db.claims[rec.claim_id]
    notify(c.claimant_user_id, "recovery.dispatched", "Item dispatched",
           f"Tracking {rec.tracking_reference} (simulated courier).", "recovery", rec.id)
    emit("recovery.dispatched", "recovery", rec.id, claim_org(c),
         {"recovery_id": str(rec.id), "tracking_reference": rec.tracking_reference})
    audit(user, claim_org(c), "recovery.dispatched", "recovery", rec.id)
    return rec


def confirm_received(user: User, rec_id: UUID) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    _require(rec, role, "claimant", "delivery", {"dispatched", "in_transit"})
    rec.status = "received"
    _event(rec, user, "received", "Recipient confirmed the item was received.")
    _complete(user, rec)
    return rec


def _complete(user: User, rec: Recovery) -> None:
    rec.status = "completed"
    _event(rec, None, "completed", "Recovery completed.")
    c = db.claims[rec.claim_id]
    m = db.matches[c.match_id]
    m.status = "confirmed"
    for rid in (m.lost_report_id, m.found_report_id):
        db.reports[rid].status = "resolved"
        db.reports[rid].updated_at = now()
    db.reports[m.found_report_id].custody_status = "released"
    notify(c.claimant_user_id, "recovery.completed", "Recovery complete", "Your item has been returned.",
           "recovery", rec.id)
    audit(user, claim_org(c), "recovery.completed", "recovery", rec.id)
    emit("recovery.completed", "recovery", rec.id, claim_org(c),
         {"recovery_id": str(rec.id), "case_reference": c.reference})


def cancel_recovery(user: User, rec_id: UUID, reason: str) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    if rec.status not in {"created", "awaiting_payment", "preparing", "ready_for_pickup"}:
        raise ApiError(409, "RECOVERY_INVALID_STATE", "This recovery can no longer be cancelled.")
    if captured_payment(rec):
        raise ApiError(409, "REFUND_REQUIRED", "A captured payment exists; refunds are not available in the demo.")
    rec.status = "cancelled"
    rec.pickup_token = None
    _event(rec, user, "cancelled", f"Cancelled: {reason}")
    audit(user, claim_org(db.claims[rec.claim_id]), "recovery.cancelled", "recovery", rec.id, reason)
    return rec


# ------------------------------------------------------------- payments ----


def latest_payment(rec: Recovery) -> Payment | None:
    ps = sorted((p for p in db.payments.values() if p.recovery_id == rec.id), key=lambda p: p.created_at)
    return ps[-1] if ps else None


def captured_payment(rec: Recovery) -> Payment | None:
    return next((p for p in db.payments.values() if p.recovery_id == rec.id and p.status == "captured"), None)


def create_order(user: User, recovery_id: UUID, idem_key: str) -> Payment:
    existing = next((p for p in db.payments.values() if p.idempotency_key == idem_key), None)
    if existing:
        if existing.user_id != user.id or existing.recovery_id != recovery_id:
            raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "This idempotency key was used for another request.")
        return existing
    rec, role = get_recovery(user, recovery_id)
    _require(rec, role, "claimant", "delivery", {"awaiting_payment"})
    if not rec.quote_expires_at or rec.quote_expires_at < now():
        _quote(rec)
    p = Payment(
        recovery_id=rec.id,
        user_id=user.id,
        provider_order_id="MOCK-" + secrets.token_hex(8).upper(),
        amount_minor=rec.quote_minor or 0,  # server-derived, never from the client
        currency=rec.currency or "USD",
        idempotency_key=idem_key,
    )
    db.payments[p.id] = p
    _event(rec, user, "payment_pending", "Payment started (PayPal Sandbox, mocked in stub).")
    return p


def approval_url(p: Payment) -> str:
    return f"{settings.api_base_url}/api/v1/dev/mock-paypal/checkout?token={p.provider_order_id}"


def payment_by_order(order_id: str) -> Payment | None:
    return next((p for p in db.payments.values() if p.provider_order_id == order_id), None)


def mock_approve(order_id: str) -> Payment:
    p = payment_by_order(order_id)
    if not p:
        raise not_found("payment")
    if p.status == "created":
        p.status = "approved"
    return p


def capture_order(user: User, order_id: str) -> Payment:
    p = payment_by_order(order_id)
    if not p or p.user_id != user.id:
        raise not_found("payment")
    if p.status == "captured":
        return p  # idempotent
    if p.status != "approved":
        raise ApiError(409, "PAYMENT_NOT_APPROVED", "The buyer has not approved this payment yet.")
    rec = db.recoveries[p.recovery_id]
    if rec.status != "awaiting_payment":
        raise ApiError(409, "RECOVERY_INVALID_STATE", "This recovery is not awaiting payment.")
    p.status = "captured"
    p.provider_capture_id = "MOCKCAP-" + secrets.token_hex(6).upper()
    p.captured_at = now()
    rec.status = "preparing"
    _event(rec, user, "payment_captured", "Delivery payment confirmed (Sandbox, mocked in stub).")
    _event(rec, None, "preparing", "Staff are preparing the item for dispatch.")
    c = db.claims[rec.claim_id]
    org = claim_org(c)
    notify(user.id, "payment.captured", "Payment confirmed", "Delivery payment received.", "recovery", rec.id)
    notify_org(org, {"staff", "reviewer", "manager", "admin"}, "payment.captured", "Delivery paid",
               f"Claim {c.reference} is ready to dispatch.", "recovery", rec.id)
    audit(user, org, "payment.captured", "payment", p.id)
    emit("payment.captured", "payment", p.id, org,
         {"payment_id": str(p.id), "recovery_id": str(rec.id), "amount_minor": p.amount_minor, "currency": p.currency})
    return p


def get_payment(user: User, payment_id: UUID) -> Payment:
    p = db.payments.get(payment_id)
    if not p:
        raise not_found("payment")
    get_recovery(user, p.recovery_id)  # raises 404 if no access
    return p


# -------------------------------------------------------- notifications ----


def my_notifications(user: User, unread_only: bool) -> list[Notification]:
    ns = [n for n in db.notifications if n.user_id == user.id and (not unread_only or n.read_at is None)]
    return sorted(ns, key=lambda n: n.created_at, reverse=True)


def mark_read(user: User, nid: UUID | None) -> int:
    count = 0
    for n in db.notifications:
        if n.user_id == user.id and n.read_at is None and (nid is None or n.id == nid):
            n.read_at = now()
            count += 1
    if nid is not None and count == 0 and not any(n.id == nid and n.user_id == user.id for n in db.notifications):
        raise not_found("notification")
    return count
