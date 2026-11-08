"""Lost/found reports, uploads and AI extraction requests."""

from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import or_, select

from ..core import config
from ..core.errors import ApiError, not_found
from ..db.models import Claim, ItemImage, Location, Match, Organisation, Report, User, now
from ..db.session import db
from ..integrations import ai
from ..integrations.storage import storage
from .access import report_role, role_in, scoped_role
from .events import audit, emit

CLOSED = {"resolved", "withdrawn", "expired", "rejected"}
ACTIVE_CLAIM = {"pending", "escalated", "approved"}

# --------------------------------------------------------------------- uploads ----

ALLOWED_TYPES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
    "application/pdf": [b"%PDF"],
}


def save_upload(user: User, content_type: str, data: bytes, visibility: str) -> ItemImage:
    if content_type not in ALLOWED_TYPES:
        raise ApiError(415, "UNSUPPORTED_FILE_TYPE", "Allowed types: JPEG, PNG, WebP, PDF.")
    if content_type == "application/pdf" and visibility != "private_evidence":
        raise ApiError(422, "PDF_EVIDENCE_ONLY", "PDFs can only be uploaded as private evidence.")
    if not data:
        raise ApiError(400, "EMPTY_FILE", "The file is empty.")
    if len(data) > config.settings.max_upload_bytes:
        raise ApiError(413, "FILE_TOO_LARGE", "Files must be 8 MB or smaller.")
    if not any(data.startswith(sig) for sig in ALLOWED_TYPES[content_type]) or (
            content_type == "image/webp" and data[8:12] != b"WEBP"):
        raise ApiError(415, "FILE_SIGNATURE_MISMATCH", "File content does not match its type.")
    img = ItemImage(id=uuid.uuid4(), uploaded_by_user_id=user.id, content_type=content_type,
                    size_bytes=len(data), visibility=visibility, storage_key="")
    img.storage_key = img.id.hex
    storage().put(img.storage_key, data)
    db().add(img)
    return img


def read_image(img: ItemImage) -> bytes:
    return storage().get(img.storage_key)


def own_images(user: User, image_ids: list[UUID]) -> list[ItemImage]:
    out = []
    for iid in image_ids:
        img = db().get(ItemImage, iid)
        if not img or img.uploaded_by_user_id != user.id:
            raise ApiError(422, "INVALID_IMAGE", f"Image {iid} was not uploaded by you.")
        out.append(img)
    return out


def can_view_image(user: User, img: ItemImage) -> bool:
    from .claims import claim_role  # cycle: claims imports reports

    if img.uploaded_by_user_id == user.id:
        return True
    if img.report_id:
        r = db().get(Report, img.report_id)
        access = report_access(user, r) if r else None
        if access in {"owner", "custodian"}:
            return True
        if access == "public" and img.visibility == "public_safe":
            return True
    if img.claim_id:
        c = db().get(Claim, img.claim_id)
        return bool(c) and claim_role(user, c) in {"claimant", "reviewer"}
    return False


def report_images(r: Report) -> list[ItemImage]:
    imgs = [db().get(ItemImage, UUID(i)) for i in r.image_ids]
    return [i for i in imgs if i is not None]


def _attach_images(r: Report, images: list[ItemImage]) -> None:
    for old in report_images(r):
        if old.report_id == r.id and old not in images:
            old.report_id = None
    for img in images:
        img.report_id = r.id
    r.image_ids = [str(i.id) for i in images]


# --------------------------------------------------------------------- access ----

def processing_status(r: Report) -> str:
    if r.status == "draft":
        return "not_started"
    if r.status in {"submitted", "processing"}:
        return "processing"
    return "completed"


def report_access(user: User, r: Report) -> str | None:
    if user.id in (r.owner_user_id, r.created_by_user_id):
        return "owner"
    if report_role(user, r):
        return "custodian"
    col = Match.found_report_id if r.report_type == "lost" else Match.lost_report_id
    mine = Match.lost_report_id if r.report_type == "lost" else Match.found_report_id
    for other_id in db().scalars(select(col).where(mine == r.id, Match.status != "dismissed")):
        other = db().get(Report, other_id)
        if other and (user.id in (other.owner_user_id, other.created_by_user_id) or report_role(user, other)):
            return "public"
    return None


def get_report(user: User, report_id: UUID) -> tuple[Report, str]:
    r = db().get(Report, report_id)
    access = report_access(user, r) if r else None
    if not r or not access or (r.status == "draft" and access == "public"):
        raise not_found("report")
    return r, access


def require_report_editor(user: User, report_id: UUID) -> Report:
    r, access = get_report(user, report_id)
    if access == "public":
        raise ApiError(403, "FORBIDDEN", "You cannot change this report.")
    return r


def claims_for_report(r: Report) -> list[Claim]:
    col = Match.lost_report_id if r.report_type == "lost" else Match.found_report_id
    return list(db().scalars(select(Claim).join(Match, Match.id == Claim.match_id).where(col == r.id)))


# ----------------------------------------------------------------- lifecycle ----

def create_lost(user: User, body) -> Report:
    images = own_images(user, body.image_ids)
    r = Report(
        id=uuid.uuid4(), report_type="lost", category=body.category, item_label=body.item_label,
        description=body.description, owner_user_id=user.id, created_by_user_id=user.id,
        brand=body.brand, model=body.model, lost_at_start=body.lost_at_start, lost_at_end=body.lost_at_end,
        location_label=body.last_location.label, latitude=body.last_location.latitude,
        longitude=body.last_location.longitude, attributes_public=dict(body.attributes_public),
        attributes_private=dict(body.attributes_private), status="draft", image_ids=[],
    )
    db().add(r)
    db().flush()  # insert the report before images reference it (no ORM relationship to order it)
    _attach_images(r, images)
    audit(user, None, "report.created", "lost_report", r.id)
    if not body.as_draft:
        submit(user, r)
    return r


def create_found(user: User, body) -> Report:
    images = own_images(user, body.image_ids)
    org = loc = None
    if body.custody_status == "finder_holds":
        if not body.found_location:
            raise ApiError(422, "FOUND_LOCATION_REQUIRED", "Tell us where you found the item.")
    else:
        if body.custody_status == "released":
            raise ApiError(422, "INVALID_CUSTODY", "A new report cannot start as released.")
        if not body.organisation_id or not body.location_id:
            raise ApiError(422, "ORGANISATION_REQUIRED", "Choose the organisation and location holding the item.")
        org = db().get(Organisation, body.organisation_id)
        loc = db().get(Location, body.location_id)
        if not org or not loc or loc.organisation_id != org.id:
            raise ApiError(422, "INVALID_LOCATION", "That location does not belong to the organisation.")
        if body.custody_status == "organisation_holds":
            if not role_in(user, org.id):
                raise ApiError(403, "NOT_A_MEMBER",
                               "Only organisation staff can record items their organisation holds.")
            if not scoped_role(user, org.id, loc.id):
                raise ApiError(403, "LOCATION_OUT_OF_SCOPE", "You are not assigned to this location.")
    is_staff = org is not None and loc is not None and scoped_role(user, org.id, loc.id) is not None
    if body.storage_reference and not is_staff:
        raise ApiError(403, "FORBIDDEN", "Only organisation staff can set a storage reference.")
    fl = body.found_location
    r = Report(
        id=uuid.uuid4(), report_type="found", category=body.category, item_label=body.item_label,
        description=body.description, owner_user_id=None if is_staff else user.id, created_by_user_id=user.id,
        organisation_id=org.id if org else None, location_id=loc.id if loc else None,
        brand=body.brand, model=body.model, found_at=body.found_at,
        location_label=f"{loc.name}, {org.name}" if loc and org else fl.label,
        latitude=loc.latitude if loc else (fl.latitude if fl else None),
        longitude=loc.longitude if loc else (fl.longitude if fl else None),
        custody_status=body.custody_status, attributes_public=dict(body.attributes_public),
        attributes_private=dict(body.attributes_private), storage_reference=body.storage_reference,
        status="draft", image_ids=[],
    )
    db().add(r)
    db().flush()  # insert the report before images reference it (no ORM relationship to order it)
    _attach_images(r, images)
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
    db().flush()
    emit("report.process", "report", r.id, r.organisation_id, {"report_id": str(r.id)})
    return r


def update_report(user: User, report_id: UUID, body) -> Report:
    r = require_report_editor(user, report_id)
    if r.status in CLOSED:
        raise ApiError(409, "REPORT_CLOSED", "This report can no longer be edited.")
    data = body.model_dump(exclude_unset=True)
    # Validate everything before mutating, so a rejected PATCH leaves the report unchanged.
    if "storage_reference" in data and not report_role(user, r):
        raise ApiError(403, "FORBIDDEN", "Only organisation staff can set a storage reference.")
    if r.report_type == "lost" and data.get("found_at") is not None:
        raise ApiError(422, "INVALID_FIELD", "found_at applies to found reports only.")
    if r.report_type == "found" and (data.get("lost_at_start") or data.get("lost_at_end")):
        raise ApiError(422, "INVALID_FIELD", "lost_at_* applies to lost reports only.")
    place = data.pop("last_location", None)
    if place and r.report_type == "found" and r.organisation_id:
        raise ApiError(422, "INVALID_FIELD", "Organisation-held items use the organisation location.")
    start = data.get("lost_at_start", r.lost_at_start)
    end = data.get("lost_at_end", r.lost_at_end)
    if start and end and end < start:
        raise ApiError(400, "VALIDATION_ERROR", "Some fields are invalid.", {"fields": [{
            "loc": ["body", "lost_at_end"], "message": "lost_at_end must be after lost_at_start",
            "type": "value_error"}]})
    image_ids = data.pop("image_ids", None)
    images = own_images(user, image_ids) if image_ids is not None else None

    if images is not None:
        _attach_images(r, images)
    if place:
        r.location_label, r.latitude, r.longitude = place["label"], place.get("latitude"), place.get("longitude")
    for key, value in data.items():
        setattr(r, key, value)
    r.updated_at = now()
    if r.status in {"processing", "active"}:
        emit("report.process", "report", r.id, r.organisation_id, {"report_id": str(r.id), "rematch_only": True})
    return r


def withdraw(user: User, report_id: UUID) -> Report:
    r = require_report_editor(user, report_id)
    if r.status in {"resolved", "withdrawn"}:
        raise ApiError(409, "REPORT_CLOSED", "This report is already closed.")
    if any(c.status in ACTIVE_CLAIM for c in claims_for_report(r)):
        raise ApiError(409, "REPORT_HAS_ACTIVE_CLAIM", "Resolve the open claim before withdrawing.")
    r.status = "withdrawn"
    audit(user, r.organisation_id, "report.withdrawn", f"{r.report_type}_report", r.id)
    return r


def my_reports(user: User, type_: str | None, status: str | None) -> list[Report]:
    q = select(Report).where(or_(Report.owner_user_id == user.id, Report.created_by_user_id == user.id))
    if type_:
        q = q.where(Report.report_type == type_)
    if status:
        q = q.where(Report.status == status)
    return list(db().scalars(q.order_by(Report.created_at.desc())))


# ---------------------------------------------------------------- extraction ----

def request_extraction(user: User, report_id: UUID) -> Report:
    r = require_report_editor(user, report_id)
    r.extraction_status = "processing"
    db().flush()
    emit("report.extract", "report", r.id, r.organisation_id, {"report_id": str(r.id)})
    return r


def run_extraction(r: Report) -> None:
    """Worker: call the extractor and store suggestions. Never overwrites the user's fields."""
    images = [(i.content_type, read_image(i)) for i in report_images(r)
              if i.visibility == "public_safe" and i.content_type.startswith("image/")]
    result = ai.extract(ai.ExtractionInput(r.item_label, r.description, images))
    r.extraction = {k: [v, c] for k, (v, c) in result.fields.items()}
    r.extraction_provider = result.provider
    r.extraction_is_fallback = result.is_fallback
    r.extraction_status = "completed"
    r.extraction_updated_at = now()
