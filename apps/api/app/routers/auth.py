from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ..core.config import settings
from ..core.envelope import Envelope, ok
from ..core.errors import ApiError
from ..deps import CurrentUser
from ..schemas.auth import DashboardCounts, DashboardOut, LoginIn, MeOut, MeUpdate, MembershipOut, RegisterIn
from ..stub import presenters as P, services as svc
from ..stub.models import User
from ..stub.store import db

router = APIRouter(tags=["auth"])


def _me(user: User) -> MeOut:
    ms = []
    for m in svc.memberships_of(user):
        org = db.organisations[m.organisation_id]
        ms.append(MembershipOut(organisation_id=org.id, organisation_name=org.name, organisation_slug=org.slug,
                                role=m.role, location_ids=m.location_ids))  # type: ignore[arg-type]
    return MeOut(id=user.id, email=user.email, display_name=user.display_name, phone_e164=user.phone_e164,
                 created_at=user.created_at, is_staff=bool(ms), memberships=ms)


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(settings.session_cookie_name, token, httponly=True, samesite="lax",
                        secure=settings.cookie_secure, max_age=settings.session_ttl_hours * 3600, path="/")


@router.post("/auth/register", response_model=Envelope[MeOut], status_code=201)
async def register(body: RegisterIn, request: Request, response: Response):
    user = svc.register(body.email, body.password, body.display_name)
    _set_cookie(response, svc.create_session(user))
    return ok(_me(user))


@router.post("/auth/login", response_model=Envelope[MeOut])
async def login(body: LoginIn, request: Request, response: Response):
    user = svc.login(body.email, body.password)
    svc.end_session(request.cookies.get(settings.session_cookie_name))  # rotate on login
    _set_cookie(response, svc.create_session(user))
    return ok(_me(user))


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response):
    svc.end_session(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.status_code = 204
    return response


@router.post("/auth/password/forgot", status_code=501)
async def password_forgot():
    raise ApiError(501, "NOT_AVAILABLE_IN_DEMO", "Password reset is not available in the demo.")


@router.post("/auth/password/reset", status_code=501)
async def password_reset():
    raise ApiError(501, "NOT_AVAILABLE_IN_DEMO", "Password reset is not available in the demo.")


@router.get("/me", response_model=Envelope[MeOut])
async def me(user: CurrentUser):
    return ok(_me(user))


@router.patch("/me", response_model=Envelope[MeOut])
async def update_me(body: MeUpdate, user: CurrentUser):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    return ok(_me(user))


@router.get("/me/dashboard", response_model=Envelope[DashboardOut], summary="Individual dashboard cards + activity")
async def dashboard(user: CurrentUser):
    reports = svc.my_reports(user, None, None)
    claims = svc.my_claims(user)
    recs = [svc.recovery_for_claim(c) for c in claims]
    counts = DashboardCounts(
        active_lost_reports=sum(1 for r in reports if r.report_type == "lost" and r.status in {"processing", "active"}),
        active_found_reports=sum(1 for r in reports if r.report_type == "found" and r.status in {"processing", "active"}),
        potential_matches=sum(1 for m in svc.my_matches(user) if m.status == "candidate"),
        claims_awaiting_review=sum(1 for c in claims if c.status in {"pending", "escalated"}),
        active_recoveries=sum(1 for r in recs if r and r.status in svc.OPEN_RECOVERY),
    )
    recent = [P.activity(n) for n in svc.my_notifications(user, False)[:10]]
    return ok(DashboardOut(counts=counts, recent_activity=recent))
