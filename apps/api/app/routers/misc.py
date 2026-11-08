"""Notifications, uploads, health and dev-only helpers."""

from __future__ import annotations

from html import escape
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..core.config import settings
from ..core.envelope import Envelope, ok
from ..core.errors import not_found
from ..deps import CurrentUser, Page
from ..schemas.common import ImageOut, ImageVisibility
from ..schemas.misc import DemoAccount, HealthOut, NotificationOut, UnreadCountOut
from ..schemas.recoveries import RecoveryOut
from ..stub import presenters as P, services as svc
from ..stub.seed import load_seed
from ..stub.store import db

router = APIRouter()


# ---- notifications ----
@router.get("/notifications", response_model=Envelope[list[NotificationOut]], tags=["notifications"])
async def notifications(user: CurrentUser, page: Page, unread_only: Annotated[bool, Query()] = False):
    items, nxt = page.apply(svc.my_notifications(user, unread_only))
    return ok([P.notification(n) for n in items], nxt)


@router.get("/notifications/unread-count", response_model=Envelope[UnreadCountOut], tags=["notifications"])
async def unread_count(user: CurrentUser):
    return ok(UnreadCountOut(unread=len(svc.my_notifications(user, True))))


@router.post("/notifications/{notification_id}/read", response_model=Envelope[UnreadCountOut],
             tags=["notifications"])
async def mark_read(notification_id: UUID, user: CurrentUser):
    svc.mark_read(user, notification_id)
    return ok(UnreadCountOut(unread=len(svc.my_notifications(user, True))))


@router.post("/notifications/read-all", response_model=Envelope[UnreadCountOut], tags=["notifications"])
async def mark_all_read(user: CurrentUser):
    svc.mark_read(user, None)
    return ok(UnreadCountOut(unread=0))


# ---- uploads ----
@router.post("/uploads", response_model=Envelope[ImageOut], status_code=201, tags=["uploads"],
             summary="Upload an image (JPEG/PNG/WebP) or PDF evidence, max 8 MB; pass the id in image_ids")
async def upload(
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    visibility: Annotated[ImageVisibility, Form()] = "public_safe",
):
    data = await file.read(settings.max_upload_bytes + 1)
    img = svc.save_upload(user, file.content_type or "", data, visibility)
    return ok(P.image(img))


@router.get("/uploads/{image_id}/content", tags=["uploads"], response_class=Response,
            responses={200: {"content": {"image/*": {}, "application/pdf": {}}}})
async def upload_content(image_id: UUID, user: CurrentUser):
    img = db.images.get(image_id)
    if not img or not svc.can_view_image(user, img):
        raise not_found("image")
    return Response(img.data, media_type=img.content_type, headers={"Cache-Control": "private, max-age=300"})


# ---- health ----
@router.get("/health", response_model=HealthOut, tags=["health"])
async def health():
    return HealthOut(status="ok", mode="stub")


# ---- dev / demo helpers (stub only) ----
@router.post("/dev/reset", response_model=Envelope[list[DemoAccount]], tags=["dev"],
             summary="Wipe all data and reload the demo seed (signs everyone out)")
async def reset():
    load_seed()
    return ok(db.demo_accounts)


@router.get("/dev/demo-accounts", response_model=Envelope[list[DemoAccount]], tags=["dev"])
async def demo_accounts():
    return ok(db.demo_accounts)


@router.post("/dev/recoveries/{recovery_id}/advance-courier", response_model=Envelope[RecoveryOut], tags=["dev"],
             summary="Move a dispatched delivery to in_transit now (otherwise automatic after ~20s)")
async def advance_courier(recovery_id: UUID, user: CurrentUser):
    svc.advance_courier(recovery_id)
    rec, role = svc.get_recovery(user, recovery_id)
    return ok(P.recovery(user, rec, role))


@router.get("/dev/mock-paypal/checkout", response_class=HTMLResponse, include_in_schema=False)
async def mock_checkout(token: str):
    p = svc.payment_by_order(token)
    if not p:
        raise not_found("payment")
    t = escape(token)
    amount = f"{p.amount_minor / 100:.2f} {escape(p.currency)}"
    return HTMLResponse(f"""<!doctype html><html><head><meta name="viewport" content="width=device-width">
<title>Mock PayPal Sandbox</title><style>body{{font-family:system-ui;max-width:420px;margin:60px auto;padding:0 16px}}
.b{{display:block;padding:12px;margin:10px 0;text-align:center;border-radius:8px;text-decoration:none}}
.a{{background:#0070ba;color:#fff}}.c{{border:1px solid #999;color:#333}}.w{{background:#fff3cd;padding:10px;border-radius:6px}}</style>
</head><body><p class="w"><b>MOCK</b> PayPal Sandbox checkout served by the stub API. No real payment.</p>
<h2>Pay {amount}</h2><p>Order {t}</p>
<a class="b a" href="/api/v1/dev/mock-paypal/approve?token={t}">Approve payment</a>
<a class="b c" href="/api/v1/dev/mock-paypal/cancel?token={t}">Cancel and return</a></body></html>""")


@router.get("/dev/mock-paypal/approve", include_in_schema=False)
async def mock_approve(token: str):
    p = svc.mock_approve(token)
    return RedirectResponse(
        f"{settings.app_base_url}/checkout/paypal/return?token={p.provider_order_id}&recovery_id={p.recovery_id}",
        status_code=303)


@router.get("/dev/mock-paypal/cancel", include_in_schema=False)
async def mock_cancel(token: str):
    p = svc.payment_by_order(token)
    if not p:
        raise not_found("payment")
    return RedirectResponse(
        f"{settings.app_base_url}/checkout/paypal/cancel?token={p.provider_order_id}&recovery_id={p.recovery_id}",
        status_code=303)
