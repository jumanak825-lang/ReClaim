"""Notifications, uploads, health/readiness and dev-only helpers."""

from __future__ import annotations

from html import escape
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import text

from ..core import config, ratelimit
from ..core.envelope import Envelope, ok
from ..core.errors import ApiError, not_found
from ..db.models import ItemImage
from ..db.session import db, engine, ping
from ..deps import CurrentUser, DbSession, Page
from ..schemas.common import ImageOut, ImageVisibility
from ..schemas.misc import DemoAccount, HealthOut, NotificationOut, ReadyOut, UnreadCountOut
from ..schemas.recoveries import RecoveryOut
from ..services import presenters as P, svc
from .. import seed

router = APIRouter()


# ---- notifications ----
@router.get("/notifications", response_model=Envelope[list[NotificationOut]], tags=["notifications"])
def notifications(user: CurrentUser, page: Page, unread_only: Annotated[bool, Query()] = False):
    items, nxt = page.apply(svc.my_notifications(user, unread_only))
    return ok([P.notification(n) for n in items], nxt)


@router.get("/notifications/unread-count", response_model=Envelope[UnreadCountOut], tags=["notifications"])
def unread_count(user: CurrentUser):
    return ok(UnreadCountOut(unread=svc.unread_count(user)))


@router.post("/notifications/{notification_id}/read", response_model=Envelope[UnreadCountOut],
             tags=["notifications"])
def mark_read(notification_id: UUID, user: CurrentUser):
    svc.mark_read(user, notification_id)
    return ok(UnreadCountOut(unread=svc.unread_count(user)))


@router.post("/notifications/read-all", response_model=Envelope[UnreadCountOut], tags=["notifications"])
def mark_all_read(user: CurrentUser):
    svc.mark_read(user, None)
    return ok(UnreadCountOut(unread=0))


# ---- uploads ----
@router.post("/uploads", response_model=Envelope[ImageOut], status_code=201, tags=["uploads"],
             summary="Upload an image (JPEG/PNG/WebP) or PDF evidence, max 8 MB; pass the id in image_ids. "
                     "Rate limited per user.")
def upload(
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    visibility: Annotated[ImageVisibility, Form()] = "public_safe",
):
    ratelimit.hit("upload", str(user.id), config.settings.rate_limit_upload)
    data = file.file.read(config.settings.max_upload_bytes + 1)
    img = svc.save_upload(user, file.content_type or "", data, visibility)
    return ok(P.image(img))


@router.get("/uploads/{image_id}/content", tags=["uploads"], response_class=Response,
            responses={200: {"content": {"image/*": {}, "application/pdf": {}}}})
def upload_content(image_id: UUID, user: CurrentUser):
    img = db().get(ItemImage, image_id)
    if not img or not svc.can_view_image(user, img):
        raise not_found("image")
    return Response(svc.read_image(img), media_type=img.content_type,
                    headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})


# ---- health ----
@router.get("/health", response_model=HealthOut, tags=["health"], summary="Liveness: the process is up")
def health():
    return HealthOut(status="ok", mode="database")


@router.get("/ready", response_model=ReadyOut, tags=["health"],
            summary="Readiness: database reachable and migrations applied (503 otherwise)")
def ready():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    database = ping()
    head = ScriptDirectory.from_config(Config(str(config.API_ROOT / "alembic.ini"))).get_current_head()
    current = None
    if database:
        try:
            with engine().connect() as conn:
                current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        except Exception:
            current = None
    migrations = "current" if current == head else ("pending" if database else "unknown")
    body = ReadyOut(status="ready" if database and migrations == "current" else "not_ready",
                    database=database, migrations=migrations)  # type: ignore[arg-type]
    return JSONResponse(body.model_dump(), status_code=200 if body.status == "ready" else 503)


# ---- dev / demo helpers (local development only) ----
def require_dev_routes() -> None:
    # Read at request time (not import time) so tests can toggle it.
    if not config.settings.enable_dev_routes:
        raise ApiError(404, "NOT_FOUND", "Not found.")


dev = APIRouter(tags=["dev"], dependencies=[Depends(require_dev_routes)])


@dev.post("/dev/reset", response_model=Envelope[list[DemoAccount]],
          summary="Wipe ALL data and reload the demo seed (signs everyone out). Needs ENABLE_DEV_ROUTES=true")
def reset(_db: DbSession):
    return ok(seed.load_seed())


@dev.get("/dev/demo-accounts", response_model=Envelope[list[DemoAccount]],
         summary="Demo logins. Needs ENABLE_DEV_ROUTES=true")
def demo_accounts():
    return ok(seed.demo_accounts())


@dev.post("/dev/recoveries/{recovery_id}/advance-courier", response_model=Envelope[RecoveryOut],
          summary="Staff: move a dispatched delivery to in_transit now (otherwise automatic after ~20s). "
                  "Needs ENABLE_DEV_ROUTES=true")
def advance_courier(recovery_id: UUID, user: CurrentUser):
    rec = svc.advance_courier(user, recovery_id)
    return ok(P.recovery(user, rec, "staff"))


@dev.get("/dev/mock-paypal/checkout", response_class=HTMLResponse, include_in_schema=False)
def mock_checkout(token: str, user: CurrentUser):
    p = svc.payer_payment(user, token)
    t = escape(token)
    amount = f"{p.amount_minor / 100:.2f} {escape(p.currency)}"
    return HTMLResponse(f"""<!doctype html><html><head><meta name="viewport" content="width=device-width">
<title>Mock PayPal Sandbox</title><style>body{{font-family:system-ui;max-width:420px;margin:60px auto;padding:0 16px}}
.b{{display:block;padding:12px;margin:10px 0;text-align:center;border-radius:8px;text-decoration:none}}
.a{{background:#0070ba;color:#fff}}.c{{border:1px solid #999;color:#333}}.w{{background:#fff3cd;padding:10px;border-radius:6px}}</style>
</head><body><p class="w"><b>MOCK</b> PayPal Sandbox checkout (local development). No real payment.</p>
<h2>Pay {amount}</h2><p>Order {t}</p>
<a class="b a" href="/api/v1/dev/mock-paypal/approve?token={t}">Approve payment</a>
<a class="b c" href="/api/v1/dev/mock-paypal/cancel?token={t}">Cancel and return</a></body></html>""")


@dev.get("/dev/mock-paypal/approve", include_in_schema=False)
def mock_approve(token: str, user: CurrentUser):
    p = svc.mock_approve(user, token)
    return RedirectResponse(
        f"{config.settings.app_base_url}/checkout/paypal/return?token={p.provider_order_id}"
        f"&recovery_id={p.recovery_id}", status_code=303)


@dev.get("/dev/mock-paypal/cancel", include_in_schema=False)
def mock_cancel(token: str, user: CurrentUser):
    p = svc.payer_payment(user, token)
    return RedirectResponse(
        f"{config.settings.app_base_url}/checkout/paypal/cancel?token={p.provider_order_id}"
        f"&recovery_id={p.recovery_id}", status_code=303)

