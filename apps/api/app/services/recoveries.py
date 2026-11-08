"""Recovery state machine (docs/03 §3.8, plus in_transit from docs/11 §1).

Collection pickup codes are stored only as a SHA-256 hash (docs/04 `pickup_token_hash`).
The claimant reveals a fresh code with POST /recoveries/{id}/collection/pickup-token, which
rotates it; the plain code appears only in that response.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from ..core import config
from ..core.errors import ApiError, not_found
from ..db.models import Claim, Location, Match, Payment, Recovery, RecoveryEvent, Report, User, now
from ..db.session import db
from .claims import claim_found, claim_org, get_claim
from .access import report_role
from .events import audit, emit, notify

OPEN = {"created", "awaiting_payment", "preparing", "ready_for_pickup", "dispatched", "in_transit", "received"}
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L


def recovery_for_claim(c: Claim) -> Recovery | None:
    return db().scalar(select(Recovery).where(Recovery.claim_id == c.id))


def events_of(rec: Recovery) -> list[RecoveryEvent]:
    return list(db().scalars(select(RecoveryEvent).where(RecoveryEvent.recovery_id == rec.id)
                             .order_by(RecoveryEvent.created_at, RecoveryEvent.id)))


def _event(rec: Recovery, user: User | None, type_: str, desc: str, simulated: bool = False, at=None) -> None:
    ev = RecoveryEvent(recovery_id=rec.id, event_type=type_, description=desc, is_simulated=simulated,
                       created_by_user_id=user.id if user else None)
    ev.created_at = at or now()
    db().add(ev)
    db().flush()  # keep timeline order stable within one request
    rec.updated_at = now()


def courier_tick(rec_id: UUID) -> None:
    """Worker job `recovery.courier_advance` (SIMULATED courier): dispatched -> in_transit.

    Scheduled at dispatch for SIMULATED_COURIER_SECONDS later. A no-op if the recovery moved on
    (staff used the dev shortcut, or the owner already confirmed receipt).
    """
    rec = db().get(Recovery, rec_id)
    if rec is not None and rec.status == "dispatched":
        _advance_courier(rec)


def _advance_courier(rec: Recovery) -> None:
    rec.status = "in_transit"
    _event(rec, None, "in_transit", "In transit with courier (simulated).", True)
    c = db().get(Claim, rec.claim_id)
    notify(c.claimant_user_id, "recovery.in_transit", "Item in transit",
           "Your item is on its way (simulated courier).", "recovery", rec.id)


def recovery_role(user: User, rec: Recovery) -> str | None:
    c = db().get(Claim, rec.claim_id)
    if c.claimant_user_id == user.id:
        return "claimant"
    if report_role(user, claim_found(c)):  # location-scoped
        return "staff"
    return None


def get_recovery(user: User, rec_id: UUID) -> tuple[Recovery, str]:
    rec = db().get(Recovery, rec_id)
    role = recovery_role(user, rec) if rec else None
    if not rec or not role:
        raise not_found("recovery")
    return rec, role


def advance_courier(user: User, rec_id: UUID) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    if role != "staff":
        raise ApiError(403, "FORBIDDEN", "Only organisation staff can advance the simulated courier.")
    if rec.status != "dispatched":
        raise ApiError(409, "RECOVERY_NOT_DISPATCHED", "Only dispatched recoveries can advance.")
    _advance_courier(rec)
    return rec


def _quote(rec: Recovery) -> None:
    found = claim_found(db().get(Claim, rec.claim_id))
    loc = db().get(Location, found.location_id) if found.location_id else None
    domestic = loc is not None and rec.delivery_address and rec.delivery_address["country_code"] == loc.country_code
    rec.delivery_quote_minor = 1500 if domestic else 4500  # fixed demo prices, USD (docs/11 §1)
    rec.currency = "USD"
    rec.quote_expires_at = now() + timedelta(hours=24)


def _require(rec: Recovery, role: str, needed: str, method: str | None, statuses: set[str]) -> None:
    if role != needed:
        raise ApiError(403, "FORBIDDEN", "You cannot perform this recovery action.")
    if method and rec.method != method:
        raise ApiError(409, "WRONG_RECOVERY_METHOD", f"This action applies to {method} only.")
    if rec.status not in statuses:
        raise ApiError(409, "RECOVERY_INVALID_STATE", "This action is not allowed in the current state.",
                       {"status": rec.status})


def create_recovery(user: User, claim_id: UUID, body) -> Recovery:
    c, role = get_claim(user, claim_id)
    if role != "claimant":
        raise ApiError(403, "FORBIDDEN", "Only the claimant can choose a recovery method.")
    if c.status != "approved":
        raise ApiError(409, "CLAIM_NOT_APPROVED", "Recovery is available only after the claim is approved.")
    if recovery_for_claim(c):
        raise ApiError(409, "RECOVERY_EXISTS", "A recovery already exists for this claim.")
    rec = Recovery(claim_id=c.id, method=body.method, status="created")
    db().add(rec)
    db().flush()
    _event(rec, None, "claim_approved", "Claim approved.", at=c.decided_at)
    if body.method == "collection":
        rec.preferred_window_start, rec.preferred_window_end = body.preferred_window_start, body.preferred_window_end
        _event(rec, user, "method_selected", "Collection selected.")
        rec.status = "preparing"
        _event(rec, None, "preparing", "Staff are preparing the item for collection.")
    else:
        rec.delivery_address = body.address.model_dump()
        _quote(rec)
        _event(rec, user, "method_selected", "Delivery selected.")
        rec.status = "awaiting_payment"
        _event(rec, None, "awaiting_payment", "Waiting for delivery payment.")
        emit("recovery.delivery_requested", "recovery", rec.id, claim_org(c),
             {"recovery_id": str(rec.id), "case_reference": c.reference,
              "country_code": rec.delivery_address["country_code"]})
    audit(user, claim_org(c), "recovery.created", "recovery", rec.id, after={"method": rec.method})
    return rec


def refresh_quote(user: User, rec_id: UUID) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    _require(rec, role, "claimant", "delivery", {"awaiting_payment"})
    _quote(rec)
    return rec


def _hash_token(token: str) -> str:
    norm = token.replace("-", "").replace(" ", "").upper()
    return hashlib.sha256(norm.encode()).hexdigest()


def confirm_collection(user: User, rec_id: UUID) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    _require(rec, role, "staff", "collection", {"preparing"})
    rec.status = "ready_for_pickup"
    rec.pickup_token_hash = None  # the claimant reveals a code when they need it
    rec.pickup_token_expires_at = now() + timedelta(hours=72)
    _event(rec, user, "ready_for_pickup", "Ready for collection.")
    c = db().get(Claim, rec.claim_id)
    notify(c.claimant_user_id, "recovery.ready_for_pickup", "Ready for collection",
           "Your item is ready. Open the recovery page to show your pickup code.", "recovery", rec.id)
    audit(user, claim_org(c), "recovery.ready_for_pickup", "recovery", rec.id)
    return rec


def issue_pickup_token(user: User, rec_id: UUID) -> tuple[Recovery, str]:
    """Claimant: create (or rotate) the one-time pickup code. Only the hash is stored."""
    rec, role = get_recovery(user, rec_id)
    _require(rec, role, "claimant", "collection", {"ready_for_pickup"})
    if rec.pickup_token_expires_at and rec.pickup_token_expires_at < now():
        raise ApiError(409, "PICKUP_TOKEN_EXPIRED", "The collection window has expired. Contact the desk.")
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    token = f"{raw[:4]}-{raw[4:]}"
    rec.pickup_token_hash = _hash_token(token)
    return rec, token


def validate_token(user: User, rec_id: UUID, token: str) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    _require(rec, role, "staff", "collection", {"ready_for_pickup"})
    if rec.pickup_token_expires_at and rec.pickup_token_expires_at < now():
        raise ApiError(409, "PICKUP_TOKEN_EXPIRED", "This pickup code has expired.")
    if not rec.pickup_token_hash or not hmac.compare_digest(_hash_token(token), rec.pickup_token_hash):
        raise ApiError(400, "INVALID_PICKUP_TOKEN", "That pickup code is not valid.")
    rec.pickup_token_hash = None  # one-time use
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
    c = db().get(Claim, rec.claim_id)
    notify(c.claimant_user_id, "recovery.dispatched", "Item dispatched",
           f"Tracking {rec.tracking_reference} (simulated courier).", "recovery", rec.id)
    emit("recovery.dispatched", "recovery", rec.id, claim_org(c),
         {"recovery_id": str(rec.id), "tracking_reference": rec.tracking_reference})
    emit("recovery.courier_advance", "recovery", rec.id, claim_org(c), {"recovery_id": str(rec.id)},
         delay_seconds=config.settings.courier_seconds)
    audit(user, claim_org(c), "recovery.dispatched", "recovery", rec.id)
    return rec


def confirm_received(user: User, rec_id: UUID) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    _require(rec, role, "claimant", "delivery", {"dispatched", "in_transit"})
    rec.status = "received"
    rec.recipient_confirmed_at = now()
    _event(rec, user, "received", "Recipient confirmed the item was received.")
    _complete(user, rec)
    return rec


def _complete(user: User, rec: Recovery) -> None:
    rec.status = "completed"
    _event(rec, None, "completed", "Recovery completed.")
    c = db().get(Claim, rec.claim_id)
    m = db().get(Match, c.match_id)
    m.status = "confirmed"
    for rid in (m.lost_report_id, m.found_report_id):
        db().get(Report, rid).status = "resolved"
    db().get(Report, m.found_report_id).custody_status = "released"
    notify(c.claimant_user_id, "recovery.completed", "Recovery complete", "Your item has been returned.",
           "recovery", rec.id)
    audit(user, claim_org(c), "recovery.completed", "recovery", rec.id)
    emit("recovery.completed", "recovery", rec.id, claim_org(c),
         {"recovery_id": str(rec.id), "case_reference": c.reference})


def captured_payment(rec: Recovery) -> Payment | None:
    return db().scalar(select(Payment).where(Payment.recovery_id == rec.id, Payment.status == "captured"))


def latest_payment(rec: Recovery) -> Payment | None:
    return db().scalar(select(Payment).where(Payment.recovery_id == rec.id)
                       .order_by(Payment.created_at.desc()).limit(1))


def cancel_recovery(user: User, rec_id: UUID, reason: str) -> Recovery:
    rec, role = get_recovery(user, rec_id)
    if rec.status not in {"created", "awaiting_payment", "preparing", "ready_for_pickup"}:
        raise ApiError(409, "RECOVERY_INVALID_STATE", "This recovery can no longer be cancelled.")
    if captured_payment(rec):
        raise ApiError(409, "REFUND_REQUIRED", "A captured payment exists; refunds are not available in the demo.")
    rec.status = "cancelled"
    rec.pickup_token_hash = None
    _event(rec, user, "cancelled", f"Cancelled: {reason}")
    audit(user, claim_org(db().get(Claim, rec.claim_id)), "recovery.cancelled", "recovery", rec.id, reason)
    return rec
