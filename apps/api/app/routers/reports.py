from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from ..core.envelope import Envelope, ok
from ..deps import CurrentUser, Page
from ..schemas.common import ReportStatus
from ..schemas.matches import MatchOut
from ..schemas.reports import ExtractionOut, FoundReportCreate, LostReportCreate, ReportOut, ReportUpdate
from ..stub import presenters as P, services as svc

router = APIRouter(tags=["reports"])


@router.post("/reports/lost", response_model=Envelope[ReportOut], status_code=201)
async def create_lost(body: LostReportCreate, user: CurrentUser):
    r = svc.create_lost(user, body)
    return ok(P.report(user, r, "owner"))


@router.post("/reports/found", response_model=Envelope[ReportOut], status_code=201)
async def create_found(body: FoundReportCreate, user: CurrentUser):
    r = svc.create_found(user, body)
    _, access = svc.get_report(user, r.id)
    return ok(P.report(user, r, access))


@router.get("/reports/mine", response_model=Envelope[list[ReportOut]])
async def my_reports(
    user: CurrentUser,
    page: Page,
    type: Annotated[Literal["lost", "found"] | None, Query()] = None,
    status: Annotated[ReportStatus | None, Query()] = None,
):
    items, nxt = page.apply(svc.my_reports(user, type, status))
    return ok([P.report(user, r, "owner") for r in items], nxt)


@router.get("/reports/{report_id}", response_model=Envelope[ReportOut])
async def get_report(report_id: UUID, user: CurrentUser):
    r, access = svc.get_report(user, report_id)
    return ok(P.report(user, r, access))


@router.patch("/reports/{report_id}", response_model=Envelope[ReportOut])
async def update_report(report_id: UUID, body: ReportUpdate, user: CurrentUser):
    r = svc.update_report(user, report_id, body)
    _, access = svc.get_report(user, r.id)
    return ok(P.report(user, r, access))


@router.post("/reports/{report_id}/submit", response_model=Envelope[ReportOut],
             summary="Submit a draft report (wizard final step)")
async def submit_report(report_id: UUID, user: CurrentUser):
    r = svc.require_report_editor(user, report_id)
    svc.submit(user, r)
    _, access = svc.get_report(user, r.id)
    return ok(P.report(user, r, access))


@router.post("/reports/{report_id}/withdraw", response_model=Envelope[ReportOut])
async def withdraw_report(report_id: UUID, user: CurrentUser):
    r = svc.withdraw(user, report_id)
    _, access = svc.get_report(user, r.id)
    return ok(P.report(user, r, access))


@router.post("/reports/{report_id}/extract", response_model=Envelope[ExtractionOut], status_code=202,
             summary="Queue AI extraction; poll GET .../extraction")
async def extract(report_id: UUID, user: CurrentUser):
    r = svc.start_extraction(user, report_id)
    return ok(P.extraction(r))


@router.get("/reports/{report_id}/extraction", response_model=Envelope[ExtractionOut])
async def get_extraction(report_id: UUID, user: CurrentUser):
    r = svc.require_report_editor(user, report_id)
    return ok(P.extraction(r))


@router.get("/reports/{report_id}/matches", response_model=Envelope[list[MatchOut]])
async def report_matches(report_id: UUID, user: CurrentUser, page: Page):
    items, nxt = page.apply(svc.matches_for_report(user, report_id))
    return ok([P.match(user, m) for m in items], nxt)
