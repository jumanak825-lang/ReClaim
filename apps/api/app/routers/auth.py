from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ..core import config, ratelimit
from ..core.envelope import Envelope, ok
from ..core.errors import ApiError
from ..db.models import Organisation, User
from ..db.session import db
from ..deps import CurrentUser, DbSession
from ..schemas.auth import DashboardCounts, DashboardOut, LoginIn, MeOut, MeUpdate, MembershipOut, RegisterIn
from ..services import presenters as P, svc

router = APIRouter(tags=["auth"])


def _me(user: User) -> MeOut:
    ms = []
    for m in svc.memberships_of(user):
        org = db().get(Organisation, m.organisation_id)
        ms.append(MembershipOut(organisation_id=org.id, organisation_name=org.name, organisation_slug=org.slug,
                                role=m.role,  # type: ignore[arg-type]
                                location_ids=svc.scoped_location_ids(user, org.id)))
    return MeOut(id=user.id, email=user.email, display_name=user.display_name, phone_e164=user.phone_e164,
                 created_at=user.created_at, is_staff=bool(ms), memberships=ms)


def _set_cookie(response: Response, token: str) -> None:
    s = config.settings
    response.set_cookie(s.session_cookie_name, token, httponly=True, samesite="lax", secure=s.cookie_secure,
                        max_age=s.session_ttl_hours * 3600, path="/")


@router.post("/auth/register", response_model=Envelope[MeOut], status_code=201,
             summary="Create an account and sign in. Rate limited per IP.")
def register(body: RegisterIn, request: Request, response: Response, _db: DbSession):
    ratelimit.hit("auth-ip", ratelimit.client_ip(request), config.settings.rate_limit_auth)
    user = svc.register(body.email, body.password, body.display_name)
    _set_cookie(response, svc.create_session(user))
    return ok(_me(user))


@router.post("/auth/login", response_model=Envelope[MeOut], summary="Sign in. Rate limited per IP and per email.")
def login(body: LoginIn, request: Request, response: Response, _db: DbSession):
    ratelimit.hit("auth-ip", ratelimit.client_ip(request), config.settings.rate_limit_auth)
    ratelimit.hit("auth-email", body.email.strip().lower(), config.settings.rate_limit_auth)
    user = svc.login(body.email, body.password)
    svc.end_session(request.cookies.get(config.settings.session_cookie_name))  # rotate on login
    _set_cookie(response, svc.create_session(user))
    return ok(_me(user))


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, _db: DbSession):
    svc.end_session(request.cookies.get(config.settings.session_cookie_name))
    response.delete_cookie(config.settings.session_cookie_name, path="/")
    response.status_code = 204
    return response


@router.post("/auth/password/forgot", status_code=501)
def password_forgot():
    raise ApiError(501, "NOT_AVAILABLE_IN_DEMO", "Password reset is not available in the demo.")


@router.post("/auth/password/reset", status_code=501)
def password_reset():
    raise ApiError(501, "NOT_AVAILABLE_IN_DEMO", "Password reset is not available in the demo.")


@router.get("/me", response_model=Envelope[MeOut])
def me(user: CurrentUser):
    return ok(_me(user))


@router.patch("/me", response_model=Envelope[MeOut])
def update_me(body: MeUpdate, user: CurrentUser):
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "display_name" and v is None:
            raise ApiError(400, "VALIDATION_ERROR", "Some fields are invalid.", {"fields": [
                {"loc": ["body", "display_name"], "message": "display_name cannot be null", "type": "value_error"}]})
        setattr(user, k, v)
    return ok(_me(user))


@router.get("/me/dashboard", response_model=Envelope[DashboardOut], summary="Individual dashboard cards + activity")
def dashboard(user: CurrentUser):
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
