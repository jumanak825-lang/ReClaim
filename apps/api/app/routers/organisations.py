from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from ..core import config
from ..core.envelope import Envelope, ok
from ..core.errors import not_found
from ..db.models import AuditLog, Location, Match, Organisation, OutboxEvent, Report, User
from ..db.session import db
from ..deps import CurrentUser, Page
from ..integrations import zapier
from ..schemas.claims import ClaimListItem
from ..schemas.common import Category, ClaimStatus, ReportStatus
from ..schemas.misc import (
    AuditLogOut,
    CaseDetailOut,
    CaseRow,
    IntegrationOut,
    LastDelivery,
    LocationOut,
    OrganisationOut,
    OrgOverviewOut,
    ZapierTestIn,
    ZapierTestOut,
)
from ..schemas.reports import ReportOut
from ..services import presenters as P, svc

router = APIRouter(tags=["organisations"])

ZAPIER_EVENTS = [e for e in zapier.SUBSCRIBED_EVENTS if e != "integration.test"]


@router.get("/organisations", response_model=Envelope[list[OrganisationOut]],
            summary="Participating organisations (for the found-report wizard and org switcher)")
def list_orgs(user: CurrentUser, page: Page):
    orgs = list(db().scalars(select(Organisation).where(Organisation.status == "active").order_by(Organisation.name)))
    items, nxt = page.apply(orgs)
    return ok([P.organisation(o) for o in items], nxt)


@router.get("/organisations/{org_id}", response_model=Envelope[OrganisationOut])
def get_org(org_id: UUID, user: CurrentUser):
    org = db().get(Organisation, org_id)
    if not org:
        raise not_found("organisation")
    return ok(P.organisation(org))


@router.get("/organisations/{org_id}/locations", response_model=Envelope[list[LocationOut]])
def list_locations(org_id: UUID, user: CurrentUser):
    if not db().get(Organisation, org_id):
        raise not_found("organisation")
    locs = db().scalars(select(Location).where(Location.organisation_id == org_id, Location.is_active)
                        .order_by(Location.name))
    return ok([P.location(loc) for loc in locs])


def _org_found(user: User, org_id: UUID) -> list[Report]:
    """Found reports of the org, limited to the caller's locations."""
    svc.require_member(user, org_id)
    q = select(Report).where(Report.report_type == "found", Report.organisation_id == org_id,
                             Report.status != "draft")
    allowed = svc.scoped_location_ids(user, org_id)
    if allowed:
        q = q.where(Report.location_id.in_(allowed))
    return list(db().scalars(q))


def _case_row(r: Report) -> CaseRow:
    ms = [m for m in db().scalars(select(Match).where(Match.found_report_id == r.id, Match.status != "dismissed"))
          if svc.match_visible(m)]
    best = max(ms, key=lambda m: m.score, default=None)
    claims = sorted(svc.claims_for_report(r), key=lambda c: c.created_at)
    claim = claims[-1] if claims else None
    rec = svc.recovery_for_claim(claim) if claim else None
    loc = db().get(Location, r.location_id) if r.location_id else None
    if (claim and claim.status in {"pending", "escalated"}) or (rec and rec.status in {"preparing", "ready_for_pickup"}):
        priority = "high"
    elif best and best.score >= 85:
        priority = "medium"
    else:
        priority = "low"
    stamps = [r.updated_at] + ([claim.updated_at] if claim else []) + ([rec.updated_at] if rec else [])
    return CaseRow(
        id=r.id, case_reference="RC-" + r.id.hex[:6].upper(), item_label=r.item_label,
        category=r.category, report_type="found", report_status=r.status,  # type: ignore[arg-type]
        candidate_match_id=best.id if best else None, ai_relevance=float(best.score) if best else None,
        location_id=r.location_id, location_name=loc.name if loc else None,
        reported_at=r.found_at or r.created_at,
        claim_id=claim.id if claim else None, claim_status=claim.status if claim else None,  # type: ignore[arg-type]
        recovery_id=rec.id if rec else None, recovery_status=rec.status if rec else None,  # type: ignore[arg-type]
        priority=priority, updated_at=max(stamps),  # type: ignore[arg-type]
    )


SORTS = {
    "updated_at": (lambda c: c.updated_at, False),
    "-updated_at": (lambda c: c.updated_at, True),
    "reported_at": (lambda c: c.reported_at, False),
    "-reported_at": (lambda c: c.reported_at, True),
    "-ai_relevance": (lambda c: c.ai_relevance or 0, True),
    "priority": (lambda c: {"high": 0, "medium": 1, "low": 2}[c.priority], False),
}


@router.get("/organisations/{org_id}/overview", response_model=Envelope[OrgOverviewOut],
            summary="Organisation overview cards")
def overview(org_id: UUID, user: CurrentUser):
    found = _org_found(user, org_id)
    rows = [_case_row(r) for r in found]
    claims = svc.org_claims(user, org_id, None)  # location-scoped
    recent = [P.activity(n) for n in svc.my_notifications(user, False)[:10]]
    return ok(OrgOverviewOut(
        active_cases=sum(1 for r in rows if r.report_status in {"active", "processing"}),
        found_inventory=sum(1 for r in found if r.custody_status in {"organisation_holds", "transferred"}),
        pending_claims=sum(1 for c in claims if c.status == "pending"),
        escalated_claims=sum(1 for c in claims if c.status == "escalated"),
        recoveries_in_progress=sum(1 for r in rows if r.recovery_status in svc.OPEN_RECOVERY),
        recent_activity=recent,
        is_seeded_demo_data=any(r.is_seed for r in found),
    ))


@router.get("/organisations/{org_id}/cases", response_model=Envelope[list[CaseRow]],
            summary="Operations table rows (AG Grid). Scoped to the caller's locations.")
def cases(
    org_id: UUID,
    user: CurrentUser,
    page: Page,
    status: Annotated[ReportStatus | None, Query()] = None,
    claim_status: Annotated[ClaimStatus | None, Query()] = None,
    category: Annotated[Category | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[Literal["updated_at", "-updated_at", "reported_at", "-reported_at", "-ai_relevance",
                            "priority"], Query()] = "-updated_at",
):
    rows = [_case_row(r) for r in _org_found(user, org_id)]
    if status:
        rows = [r for r in rows if r.report_status == status]
    if claim_status:
        rows = [r for r in rows if r.claim_status == claim_status]
    if category:
        rows = [r for r in rows if r.category == category]
    if location_id:
        rows = [r for r in rows if r.location_id == location_id]
    if date_from:
        rows = [r for r in rows if r.reported_at >= date_from]
    if date_to:
        rows = [r for r in rows if r.reported_at <= date_to]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r.item_label.lower() or ql in r.case_reference.lower()]
    key, rev = SORTS[sort]
    rows.sort(key=key, reverse=rev)
    items, nxt = page.apply(rows)
    return ok(items, nxt)


@router.get("/organisations/{org_id}/cases/{case_id}", response_model=Envelope[CaseDetailOut])
def case_detail(org_id: UUID, case_id: UUID, user: CurrentUser):
    found = next((r for r in _org_found(user, org_id) if r.id == case_id), None)
    if not found:
        raise not_found("case")
    matches = [m for m in db().scalars(select(Match).where(Match.found_report_id == found.id)
                                       .order_by(Match.score.desc())) if svc.match_visible(m)]
    claims = svc.claims_for_report(found)
    approved = next((c for c in claims if c.status == "approved"), None)
    rec = svc.recovery_for_claim(approved) if approved else None
    return ok(CaseDetailOut(
        case_reference="RC-" + found.id.hex[:6].upper(),
        found_report=P.report(user, found, "custodian"),
        matches=[P.match(user, m) for m in matches],
        claims=[P.claim_item(user, c) for c in claims],
        recovery=P.recovery(user, rec, "staff") if rec else None,
    ))


@router.get("/organisations/{org_id}/found-reports", response_model=Envelope[list[ReportOut]],
            summary="Found inventory")
def found_inventory(org_id: UUID, user: CurrentUser, page: Page,
                    status: Annotated[ReportStatus | None, Query()] = None):
    rows = sorted((r for r in _org_found(user, org_id) if not status or r.status == status),
                  key=lambda r: r.created_at, reverse=True)
    items, nxt = page.apply(rows)
    return ok([P.report(user, r, "custodian") for r in items], nxt)


@router.get("/organisations/{org_id}/claims", response_model=Envelope[list[ClaimListItem]], tags=["claims"],
            summary="Claim review queue")
def org_claims(org_id: UUID, user: CurrentUser, page: Page,
               status: Annotated[ClaimStatus | None, Query()] = None):
    items, nxt = page.apply(svc.org_claims(user, org_id, status))
    return ok([P.claim_item(user, c) for c in items], nxt)


@router.get("/organisations/{org_id}/audit-logs", response_model=Envelope[list[AuditLogOut]])
def audit_logs(org_id: UUID, user: CurrentUser, page: Page):
    svc.require_member(user, org_id, svc.REVIEW_ROLES)
    logs = list(db().scalars(select(AuditLog).where(AuditLog.organisation_id == org_id)
                             .order_by(AuditLog.created_at.desc())))
    items, nxt = page.apply(logs)
    out = []
    for a in items:
        actor = db().get(User, a.actor_user_id) if a.actor_user_id else None
        out.append(AuditLogOut(id=a.id, actor_display_name=actor.display_name if actor else None,
                               action=a.action, entity_type=a.entity_type, entity_id=a.entity_id, reason=a.reason,
                               request_id=a.request_id, created_at=a.created_at))
    return ok(out, nxt)


# ---- integrations ----
@router.get("/organisations/{org_id}/integrations", response_model=Envelope[list[IntegrationOut]],
            tags=["integrations"], summary="Read-only Zapier status (managers/admins)")
def integrations(org_id: UUID, user: CurrentUser):
    svc.require_member(user, org_id, svc.ADMIN_ROLES)
    s = config.settings
    last = db().scalar(select(OutboxEvent).where(OutboxEvent.organisation_id == org_id,
                                                 OutboxEvent.event_type.in_(zapier.SUBSCRIBED_EVENTS),
                                                 OutboxEvent.attempt_count > 0)
                       .order_by(OutboxEvent.created_at.desc()).limit(1))
    configured = bool(s.zapier_webhook_url and s.zapier_webhook_secret)
    return ok([IntegrationOut(
        provider="zapier",
        status="configured" if configured else "not_configured",
        enabled_events=ZAPIER_EVENTS,
        last_delivery=LastDelivery(event_type=last.event_type, status=last.delivery_status,
                                   attempted_at=last.delivered_at or last.created_at,
                                   error=last.last_error) if last else None,
        note="Configured from server environment (ZAPIER_WEBHOOK_URL, ZAPIER_WEBHOOK_SECRET). "
             "Events are HMAC-signed and retried from the outbox.",
    )])


@router.post("/integrations/zapier/test", response_model=Envelope[ZapierTestOut], tags=["integrations"])
def zapier_test(body: ZapierTestIn, user: CurrentUser):
    svc.require_member(user, body.organisation_id, svc.ADMIN_ROLES)
    ev = svc.emit("integration.test", "organisation", body.organisation_id, body.organisation_id,
                  {"test": True, "organisation_id": str(body.organisation_id)})
    db().flush()
    return ok(ZapierTestOut(outbox_event_id=ev.id, status=ev.delivery_status,
                            note="Queued. The worker signs and sends it; check last_delivery on the "
                                 "integrations endpoint for the result."))
