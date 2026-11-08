from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from ..core.config import settings
from ..core.envelope import Envelope, ok
from ..core.errors import ApiError, not_found
from ..deps import CurrentUser, Page
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
from ..stub import presenters as P, services as svc
from ..stub.models import Report, User
from ..stub.store import db

router = APIRouter(tags=["organisations"])

ZAPIER_EVENTS = ["match.high_priority", "claim.created"]


@router.get("/organisations", response_model=Envelope[list[OrganisationOut]],
            summary="Participating organisations (for the found-report wizard and org switcher)")
async def list_orgs(user: CurrentUser, page: Page):
    items, nxt = page.apply(sorted(db.organisations.values(), key=lambda o: o.name))
    return ok([P.organisation(o) for o in items], nxt)


@router.get("/organisations/{org_id}", response_model=Envelope[OrganisationOut])
async def get_org(org_id: UUID, user: CurrentUser):
    org = db.organisations.get(org_id)
    if not org:
        raise not_found("organisation")
    return ok(P.organisation(org))


@router.get("/organisations/{org_id}/locations", response_model=Envelope[list[LocationOut]])
async def list_locations(org_id: UUID, user: CurrentUser):
    if org_id not in db.organisations:
        raise not_found("organisation")
    return ok([P.location(loc) for loc in db.locations.values() if loc.organisation_id == org_id])


def _visible_locations(user: User, org_id: UUID) -> set[UUID] | None:
    m = next(m for m in db.memberships if m.user_id == user.id and m.organisation_id == org_id)
    return set(m.location_ids) or None  # None = all


def _org_found(user: User, org_id: UUID) -> list[Report]:
    svc.require_member(user, org_id)
    locs = _visible_locations(user, org_id)
    out = []
    for r in db.reports.values():
        if r.report_type == "found" and r.organisation_id == org_id and r.status != "draft":
            if locs is None or r.location_id in locs:
                out.append(svc.refresh_report(r))
    return out


def _case_row(r: Report) -> CaseRow:
    ms = [m for m in db.matches.values() if m.found_report_id == r.id and m.status != "dismissed"
          and svc.match_visible(m)]
    best = max(ms, key=lambda m: m.score, default=None)
    claims = sorted(svc.claims_for_report(r), key=lambda c: c.created_at)
    claim = claims[-1] if claims else None
    rec = svc.recovery_for_claim(claim) if claim else None
    if rec:
        svc.refresh_recovery(rec)
    loc = db.locations.get(r.location_id) if r.location_id else None
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
        candidate_match_id=best.id if best else None, ai_relevance=best.score if best else None,
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
async def overview(org_id: UUID, user: CurrentUser):
    found = _org_found(user, org_id)
    rows = [_case_row(r) for r in found]
    claims = [c for c in db.claims.values() if svc.claim_org(c) == org_id]
    recent = [P.activity(n) for n in svc.my_notifications(user, False)][:10]
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
async def cases(
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
async def case_detail(org_id: UUID, case_id: UUID, user: CurrentUser):
    found = next((r for r in _org_found(user, org_id) if r.id == case_id), None)
    if not found:
        raise not_found("case")
    matches = [m for m in db.matches.values() if m.found_report_id == found.id and svc.match_visible(m)]
    claims = svc.claims_for_report(found)
    approved = next((c for c in claims if c.status == "approved"), None)
    rec = svc.recovery_for_claim(approved) if approved else None
    return ok(CaseDetailOut(
        case_reference="RC-" + found.id.hex[:6].upper(),
        found_report=P.report(user, found, "custodian"),
        matches=[P.match(user, m) for m in sorted(matches, key=lambda m: m.score, reverse=True)],
        claims=[P.claim_item(user, c) for c in claims],
        recovery=P.recovery(user, rec, "staff") if rec else None,
    ))


@router.get("/organisations/{org_id}/found-reports", response_model=Envelope[list[ReportOut]],
            summary="Found inventory")
async def found_inventory(org_id: UUID, user: CurrentUser, page: Page,
                          status: Annotated[ReportStatus | None, Query()] = None):
    rows = sorted((r for r in _org_found(user, org_id) if not status or r.status == status),
                  key=lambda r: r.created_at, reverse=True)
    items, nxt = page.apply(rows)
    return ok([P.report(user, r, "custodian") for r in items], nxt)


@router.get("/organisations/{org_id}/claims", response_model=Envelope[list[ClaimListItem]], tags=["claims"],
            summary="Claim review queue")
async def org_claims(org_id: UUID, user: CurrentUser, page: Page,
                     status: Annotated[ClaimStatus | None, Query()] = None):
    items, nxt = page.apply(svc.org_claims(user, org_id, status))
    return ok([P.claim_item(user, c) for c in items], nxt)


@router.get("/organisations/{org_id}/audit-logs", response_model=Envelope[list[AuditLogOut]])
async def audit_logs(org_id: UUID, user: CurrentUser, page: Page):
    svc.require_member(user, org_id, svc.REVIEW_ROLES)
    logs = sorted((a for a in db.audit_logs if a.organisation_id == org_id), key=lambda a: a.created_at, reverse=True)
    items, nxt = page.apply(logs)
    return ok([
        AuditLogOut(id=a.id, actor_display_name=db.users[a.actor_user_id].display_name if a.actor_user_id else None,
                    action=a.action, entity_type=a.entity_type, entity_id=a.entity_id, reason=a.reason,
                    request_id=a.request_id, created_at=a.created_at)
        for a in items
    ], nxt)


# ---- integrations ----
@router.get("/organisations/{org_id}/integrations", response_model=Envelope[list[IntegrationOut]],
            tags=["integrations"], summary="Read-only Zapier status (managers/admins)")
async def integrations(org_id: UUID, user: CurrentUser):
    svc.require_member(user, org_id, svc.ADMIN_ROLES)
    last = next((e for e in reversed(db.outbox) if e.organisation_id == org_id), None)
    return ok([IntegrationOut(
        provider="zapier",
        status="configured" if settings.zapier_webhook_url else "not_configured",
        enabled_events=ZAPIER_EVENTS,
        last_delivery=LastDelivery(event_type=last.event_type, status=last.delivery_status,
                                   attempted_at=last.created_at, error=None) if last else None,
        note="Configured from server environment. Stub API records events but does not send them.",
    )])


@router.post("/integrations/zapier/test", response_model=Envelope[ZapierTestOut], tags=["integrations"])
async def zapier_test(body: ZapierTestIn, user: CurrentUser):
    svc.require_member(user, body.organisation_id, svc.ADMIN_ROLES)
    svc.emit("integration.test", "organisation", body.organisation_id, body.organisation_id, {"test": True})
    ev = db.outbox[-1]
    return ok(ZapierTestOut(outbox_event_id=ev.id, status=ev.delivery_status,
                            note="Stub: event recorded in the outbox, not sent to Zapier."))
