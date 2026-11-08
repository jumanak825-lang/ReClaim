"""Convert database rows into public DTOs with per-viewer privacy filtering (docs/04 §4.5)."""

from __future__ import annotations

from typing import Any

from ..core import config
from ..db.models import (
    Claim,
    ItemImage,
    Location,
    Match,
    Notification,
    Organisation,
    Payment,
    Recovery,
    Report,
    User,
)
from ..db.session import db
from ..schemas.claims import AiAssistOut, ClaimListItem, ClaimOut, ConsistencyFlag
from ..schemas.common import ActivityItem, ImageOut
from ..schemas.matches import MatchItemSummary, MatchOut
from ..schemas.misc import LocationOut, NotificationOut, OrganisationOut
from ..schemas.recoveries import (
    AddressOut,
    CollectionInfo,
    DeliveryQuoteOut,
    PaymentOut,
    RecoveryEventOut,
    RecoveryOut,
)
from ..schemas.reports import ExtractedField, ExtractionOut, ReportOut
from . import matcher, svc


def image(img: ItemImage) -> ImageOut:
    return ImageOut(id=img.id, url=f"/api/v1/uploads/{img.id}/content", content_type=img.content_type,
                    size_bytes=img.size_bytes, visibility=img.visibility)  # type: ignore[arg-type]


def organisation(o: Organisation) -> OrganisationOut:
    return OrganisationOut(id=o.id, name=o.name, slug=o.slug, organisation_type=o.organisation_type,  # type: ignore[arg-type]
                           description=o.description)


def location(loc: Location) -> LocationOut:
    return LocationOut(id=loc.id, organisation_id=loc.organisation_id, name=loc.name,
                       address_public=loc.address_public, latitude=loc.latitude, longitude=loc.longitude,
                       timezone=loc.timezone, country_code=loc.country_code, opening_hours=loc.opening_hours)


def _org_loc(r: Report) -> tuple[Organisation | None, Location | None]:
    org = db().get(Organisation, r.organisation_id) if r.organisation_id else None
    loc = db().get(Location, r.location_id) if r.location_id else None
    return org, loc


def report(user: User, r: Report, access: str) -> ReportOut:
    private = access in {"owner", "custodian"}
    imgs = svc.report_images(r)
    if not private:
        imgs = [i for i in imgs if i.visibility == "public_safe"]
    org, loc = _org_loc(r)
    actions: list[str] = []
    if private:
        if r.status == "draft":
            actions = ["edit", "extract", "submit", "withdraw"]
        elif r.status in {"processing", "active"}:
            actions = ["edit", "extract", "withdraw", "view_matches"]
        elif r.status == "resolved":
            actions = ["view_matches"]
    match_count = 0
    if private:
        col = Match.lost_report_id if r.report_type == "lost" else Match.found_report_id
        match_count = sum(1 for m in db().query(Match).filter(col == r.id, Match.status != "dismissed")
                          if svc.match_visible(m))
    # Public viewers never get an individual's exact coordinates; organisation locations are public.
    lat, lng = (r.latitude, r.longitude) if private or org else (None, None)
    custodian = access == "custodian" or (access == "owner" and svc.report_role(user, r) is not None)
    return ReportOut(
        id=r.id, report_type=r.report_type, status=r.status,  # type: ignore[arg-type]
        processing_status=svc.processing_status(r),  # type: ignore[arg-type]
        category=r.category, item_label=r.item_label, description=r.description,  # type: ignore[arg-type]
        brand=r.brand, model=r.model, lost_at_start=r.lost_at_start, lost_at_end=r.lost_at_end,
        found_at=r.found_at, location_label=r.location_label, latitude=lat, longitude=lng,
        organisation={"id": org.id, "name": org.name} if org else None,  # type: ignore[arg-type]
        location={"id": loc.id, "name": loc.name} if loc else None,  # type: ignore[arg-type]
        custody_status=r.custody_status,  # type: ignore[arg-type]
        attributes_public=r.attributes_public, images=[image(i) for i in imgs], match_count=match_count,
        created_at=r.created_at, updated_at=r.updated_at, viewer_access=access,  # type: ignore[arg-type]
        attributes_private=r.attributes_private if private else None,
        storage_reference=r.storage_reference if custodian else None,
        available_actions=actions,
    )


def extraction(r: Report) -> ExtractionOut:
    fields: dict[str, Any] = r.extraction if r.extraction_status == "completed" and r.extraction else {}

    def f(name: str) -> ExtractedField:
        value, conf = fields.get(name, (None, 0.0))
        return ExtractedField(value=value, confidence=conf)

    colour = fields.get("colour", (None, 0))[0]
    fallback = r.extraction_is_fallback
    return ExtractionOut(
        report_id=r.id, status=r.extraction_status,  # type: ignore[arg-type]
        provider=r.extraction_provider or "pending", is_fallback=fallback,
        category=f("category"), item_label=f("item_label"), brand=f("brand"), model=f("model"), colour=f("colour"),
        suggested_attributes_public={"colour": colour} if colour else {},
        disclaimer="Suggestions only. Check and edit before submitting."
                   + (" (Keyword-based fallback, not AI.)" if fallback else " (AI-generated; may be wrong.)"),
        updated_at=r.extraction_updated_at if r.extraction_status == "completed" else None,
    )


def _summary(r: Report) -> MatchItemSummary:
    org, loc = _org_loc(r)
    thumb = next((image(i).url for i in svc.report_images(r) if i.visibility == "public_safe"), None)
    start, end = (r.found_at, r.found_at) if r.report_type == "found" else (r.lost_at_start, r.lost_at_end)
    return MatchItemSummary(
        report_id=r.id, report_type=r.report_type, item_label=r.item_label,  # type: ignore[arg-type]
        category=r.category,  # type: ignore[arg-type]
        approximate_location=loc.name if loc else r.location_label,
        organisation_name=org.name if org else None, date_start=start, date_end=end,
        thumbnail_url=thumb, attributes_public=r.attributes_public,
    )


def match(user: User, m: Match) -> MatchOut:
    access = svc.match_access(user, m)
    active = svc.active_claim_for(m)
    actions: list[str] = []
    if access == "owner":
        if m.status == "candidate" and not active:
            actions = ["start_claim", "dismiss"]
        if active and active.claimant_user_id == user.id:
            actions = ["view_claim"]
    elif access == "custodian" and active:
        actions = ["view_claim"]
    show_claim = active and (active.claimant_user_id == user.id or access == "custodian")
    return MatchOut(
        id=m.id, score=float(m.score), label=matcher.label_for(float(m.score)),
        explanation=list(m.explanation_public), score_components=m.score_components,  # type: ignore[arg-type]
        status=m.status, matcher_version=m.matcher_version, created_at=m.created_at,  # type: ignore[arg-type]
        lost_item=_summary(db().get(Report, m.lost_report_id)),
        found_item=_summary(db().get(Report, m.found_report_id)),
        active_claim_id=active.id if show_claim else None, available_actions=actions,
    )


def claim(user: User, c: Claim, role: str) -> ClaimOut:
    private = role in {"claimant", "reviewer"}
    rec = svc.recovery_for_claim(c)
    actions: list[str] = []
    if role == "claimant":
        if c.status in {"pending", "escalated"}:
            actions.append("add_evidence")
        if c.status == "approved":
            actions.append("view_recovery" if rec else "choose_recovery")
    elif role == "reviewer" and c.claimant_user_id != user.id:
        if c.status == "pending":
            actions = ["approve", "reject", "escalate"]
        elif c.status == "escalated":
            actions = ["approve", "reject"]
        if svc.other_approved_claim(c):
            actions = [a for a in actions if a != "approve"]
    assist = None
    if role == "reviewer":
        summary, flags = svc.ai_assist(c)
        assist = AiAssistOut(summary=summary, flags=[ConsistencyFlag(severity=s, message=t) for s, t in flags])  # type: ignore[arg-type]
    claimant = db().get(User, c.claimant_user_id)
    m = db().get(Match, c.match_id)
    history = []
    for a in svc.history_of(c):
        actor = db().get(User, a.actor_user_id) if a.actor_user_id else None
        history.append({"action": a.action, "from_status": a.after_redacted.get("from"),
                        "to_status": a.after_redacted.get("to"), "reason": a.reason,
                        "actor_display_name": actor.display_name if actor else None, "created_at": a.created_at})
    evidence = []
    if private:
        for e in svc.evidence_of(c):
            img = svc.image_of(e)
            evidence.append({"id": e.id, "evidence_type": e.evidence_type, "image": image(img) if img else None,
                             "text": e.text_value, "created_at": e.created_at})
    return ClaimOut(
        id=c.id, reference=c.reference, status=c.status,  # type: ignore[arg-type]
        created_at=c.created_at, updated_at=c.updated_at, decided_at=c.decided_at,
        decision_reason=c.decision_reason, match=match(user, m), viewer_role=role,  # type: ignore[arg-type]
        claimant_display_name=claimant.display_name if role in {"reviewer", "staff"} else None,
        statement=c.statement if private else None,
        answers=list(c.verification_answers) if private else [],  # type: ignore[arg-type]
        evidence=evidence,  # type: ignore[arg-type]
        ai_assist=assist, history=history,  # type: ignore[arg-type]
        recovery_id=rec.id if rec else None, available_actions=actions,
    )


def claim_item(user: User, c: Claim) -> ClaimListItem:
    m = db().get(Match, c.match_id)
    found = db().get(Report, c.found_report_id)
    loc = db().get(Location, found.location_id) if found.location_id else None
    rec = svc.recovery_for_claim(c)
    staff = svc.report_role(user, found) is not None
    return ClaimListItem(
        id=c.id, reference=c.reference, status=c.status,  # type: ignore[arg-type]
        item_label=found.item_label, category=found.category,  # type: ignore[arg-type]
        location_name=loc.name if loc else None,
        claimant_display_name=db().get(User, c.claimant_user_id).display_name if staff else None,
        score=float(m.score), recovery_id=rec.id if rec else None,
        created_at=c.created_at, updated_at=c.updated_at,
    )


def payment(p: Payment) -> PaymentOut:
    return PaymentOut(id=p.id, recovery_id=p.recovery_id, provider="paypal", paypal_order_id=p.provider_order_id,
                      status=p.status, amount_minor=p.amount_minor, currency=p.currency,  # type: ignore[arg-type]
                      # mock and Sandbox are both "not real money"; a live base URL makes this false
                      is_sandbox=p.provider_mode == "mock" or config.settings.paypal_is_sandbox,
                      captured_at=p.captured_at, created_at=p.created_at)


def recovery(user: User, rec: Recovery, role: str, pickup_token: str | None = None) -> RecoveryOut:
    c = db().get(Claim, rec.claim_id)
    found = db().get(Report, c.found_report_id)
    org, loc = _org_loc(found)
    p = svc.latest_payment(rec)
    actions: list[str] = []
    if role == "claimant":
        if rec.status == "awaiting_payment":
            actions = ["pay_with_paypal", "cancel"]
        elif rec.status in {"dispatched", "in_transit"}:
            actions = ["confirm_received"]
        elif rec.status == "ready_for_pickup":
            actions = ["show_pickup_code", "cancel"]
        elif rec.status == "preparing" and not svc.captured_payment(rec):
            actions = ["cancel"]
    else:
        if rec.method == "collection" and rec.status == "preparing":
            actions = ["mark_ready_for_pickup", "cancel"]
        elif rec.method == "collection" and rec.status == "ready_for_pickup":
            actions = ["validate_pickup_token", "cancel"]
        elif rec.method == "delivery" and rec.status == "preparing":
            actions = ["dispatch"]
    addr: dict[str, Any] | None = None
    if rec.delivery_address:
        addr = dict(rec.delivery_address)
        if role != "claimant":  # minimum needed for fulfilment visibility (docs/05 §5.7)
            addr.update(line1=None, line2=None, region=None, postal_code=None)
    ready = rec.status == "ready_for_pickup"
    return RecoveryOut(
        id=rec.id, claim_id=c.id, claim_reference=c.reference, item_label=found.item_label,
        method=rec.method, status=rec.status, viewer_role=role,  # type: ignore[arg-type]
        collection=CollectionInfo(
            location_name=loc.name, organisation_name=org.name, address_public=loc.address_public,
            opening_hours=loc.opening_hours, instructions=loc.collection_instructions,
            preferred_window_start=rec.preferred_window_start, preferred_window_end=rec.preferred_window_end,
        ) if rec.method == "collection" and loc and org else None,
        delivery_address=AddressOut(**addr) if addr else None,
        delivery_quote=DeliveryQuoteOut(
            amount_minor=rec.delivery_quote_minor, currency=rec.currency, is_estimate=False,
            service_description="Tracked courier delivery (simulated). Fixed demo price.",
            expires_at=rec.quote_expires_at,
        ) if rec.delivery_quote_minor is not None and rec.currency and rec.quote_expires_at else None,
        payment=payment(p) if p else None,
        pickup_token=pickup_token if role == "claimant" and ready else None,
        pickup_token_expires_at=rec.pickup_token_expires_at if ready else None,
        tracking_reference=rec.tracking_reference, courier_is_simulated=True,
        timeline=[RecoveryEventOut(event_type=e.event_type, description=e.description,
                                   is_simulated=e.is_simulated, created_at=e.created_at) for e in svc.events_of(rec)],
        available_actions=actions, created_at=rec.created_at, updated_at=rec.updated_at,
    )


def notification(n: Notification) -> NotificationOut:
    return NotificationOut(id=n.id, type=n.type, title=n.title, body=n.body_safe,
                           related_entity_type=n.related_entity_type,  # type: ignore[arg-type]
                           related_entity_id=n.related_entity_id, read_at=n.read_at, created_at=n.created_at)


def activity(n: Notification) -> ActivityItem:
    return ActivityItem(type=n.type, title=n.title, body=n.body_safe, related_entity_type=n.related_entity_type,
                        related_entity_id=n.related_entity_id, created_at=n.created_at.isoformat())

