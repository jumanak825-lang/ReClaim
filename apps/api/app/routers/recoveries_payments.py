from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Request

from ..core.envelope import Envelope, ok
from ..deps import CurrentUser, DbSession
from ..schemas.misc import CaptureOrderIn, CreateOrderIn, CreateOrderOut, WebhookAck
from ..schemas.recoveries import CancelIn, DeliveryQuoteOut, PaymentOut, RecoveryCreate, RecoveryOut, ValidateTokenIn
from ..services import presenters as P, svc

router = APIRouter()


def _out(user, rec):
    _, role = svc.get_recovery(user, rec.id)
    return ok(P.recovery(user, rec, role))


# ---- recoveries ----
@router.post("/claims/{claim_id}/recoveries", response_model=Envelope[RecoveryOut], status_code=201,
             tags=["recoveries"])
def create_recovery(claim_id: UUID, body: RecoveryCreate, user: CurrentUser):
    return _out(user, svc.create_recovery(user, claim_id, body))


@router.get("/recoveries/{recovery_id}", response_model=Envelope[RecoveryOut], tags=["recoveries"])
def get_recovery(recovery_id: UUID, user: CurrentUser):
    rec, role = svc.get_recovery(user, recovery_id)
    return ok(P.recovery(user, rec, role))


@router.post("/recoveries/{recovery_id}/collection/confirm", response_model=Envelope[RecoveryOut],
             tags=["recoveries"], summary="Staff: mark ready for pickup (issues pickup code)")
def confirm_collection(recovery_id: UUID, user: CurrentUser):
    return _out(user, svc.confirm_collection(user, recovery_id))


@router.post("/recoveries/{recovery_id}/collection/pickup-token", response_model=Envelope[RecoveryOut],
             tags=["recoveries"],
             summary="Claimant: reveal a one-time pickup code (rotates any previous code). The code is "
                     "returned only in this response; the server stores just its hash.")
def pickup_token(recovery_id: UUID, user: CurrentUser):
    rec, token = svc.issue_pickup_token(user, recovery_id)
    return ok(P.recovery(user, rec, "claimant", pickup_token=token))


@router.post("/recoveries/{recovery_id}/collection/validate-token", response_model=Envelope[RecoveryOut],
             tags=["recoveries"], summary="Staff: validate pickup code and hand over")
def validate_token(recovery_id: UUID, body: ValidateTokenIn, user: CurrentUser):
    return _out(user, svc.validate_token(user, recovery_id, body.token))


@router.post("/recoveries/{recovery_id}/delivery/quote", response_model=Envelope[DeliveryQuoteOut],
             tags=["recoveries"], summary="Claimant: refresh the delivery quote")
def quote(recovery_id: UUID, user: CurrentUser):
    rec = svc.refresh_quote(user, recovery_id)
    out = P.recovery(user, rec, "claimant").delivery_quote
    return ok(out)


@router.post("/recoveries/{recovery_id}/delivery/dispatch", response_model=Envelope[RecoveryOut],
             tags=["recoveries"], summary="Staff: dispatch (simulated courier)")
def dispatch(recovery_id: UUID, user: CurrentUser):
    return _out(user, svc.dispatch(user, recovery_id))


@router.post("/recoveries/{recovery_id}/confirm-received", response_model=Envelope[RecoveryOut],
             tags=["recoveries"], summary="Claimant: confirm delivery received")
def confirm_received(recovery_id: UUID, user: CurrentUser):
    return _out(user, svc.confirm_received(user, recovery_id))


@router.post("/recoveries/{recovery_id}/cancel", response_model=Envelope[RecoveryOut], tags=["recoveries"])
def cancel(recovery_id: UUID, body: CancelIn, user: CurrentUser):
    return _out(user, svc.cancel_recovery(user, recovery_id, body.reason))


# ---- payments ----
@router.post("/payments/paypal/create-order", response_model=Envelope[CreateOrderOut], tags=["payments"],
             summary="Create order from the stored quote; redirect browser to approval_url")
def create_order(body: CreateOrderIn, user: CurrentUser):
    p = svc.create_order(user, body.recovery_id, body.idempotency_key)
    return ok(CreateOrderOut(payment_id=p.id, paypal_order_id=p.provider_order_id,
                             approval_url=svc.approval_url(p), status=p.status))  # type: ignore[arg-type]


@router.post("/payments/paypal/capture-order", response_model=Envelope[PaymentOut], tags=["payments"],
             summary="Call from the return page with ?token=<paypal_order_id>. Idempotent.")
def capture_order(body: CaptureOrderIn, user: CurrentUser):
    return ok(P.payment(svc.capture_order(user, body.paypal_order_id)))


@router.post("/payments/paypal/webhook", response_model=Envelope[WebhookAck], tags=["payments"],
             summary="PayPal webhook. Signature verified with PayPal; duplicates are acknowledged and ignored.")
def webhook(request: Request, event: Annotated[dict[str, Any], Body()], _db: DbSession):
    outcome = svc.handle_webhook(dict(request.headers), event)
    return ok(WebhookAck(received=True, outcome=outcome))  # type: ignore[arg-type]


@router.get("/payments/{payment_id}", response_model=Envelope[PaymentOut], tags=["payments"])
def get_payment(payment_id: UUID, user: CurrentUser):
    return ok(P.payment(svc.get_payment(user, payment_id)))
