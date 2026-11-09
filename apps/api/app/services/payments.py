"""Delivery payments with PayPal Orders v2 (docs/05 §5.8, docs/07 §7.2).

Modes (PAYPAL_MODE, see config): "sandbox" calls PayPal; "mock" uses the local mock checkout
behind the dev routes. A payment remembers the mode that created it.

Rules enforced here:
- Amount and currency come from the stored quote, never from the client.
- The order must belong to the current recovery and user.
- Capture verifies PayPal's status, amount and currency before the recovery advances.
- Never mark paid from a redirect: only a server-side capture or a verified webhook does.
- Idempotency: client key on create, PayPal-Request-Id on create/capture, unique capture id,
  webhook dedup on (provider, event id).
- Uncertain outcomes (network errors) queue a `payment.reconcile` job that asks PayPal.
- A buyer who approves on PayPal but never comes back to the site: the CHECKOUT.ORDER.APPROVED
  webhook queues the same job, which captures server-side, only while the recovery is still
  awaiting payment.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ..core import config
from ..core.errors import ApiError, not_found
from ..db.models import Claim, Payment, Recovery, User, WebhookEvent, now
from ..db.session import db
from ..integrations import paypal
from .claims import claim_found, claim_org
from .events import ALL_STAFF_ROLES, audit, emit, emit_detached, notify, notify_org
from .recoveries import _event, _quote, _require, get_recovery

log = logging.getLogger("reclaim.payments")
RECONCILE_DELAY_SECONDS = 30


def payment_by_order(order_id: str, lock: bool = False) -> Payment | None:
    """`lock=True` takes a row lock, so a browser capture, a webhook and the reconcile job
    touching the same payment run one after another and the capture is applied once."""
    q = select(Payment).where(Payment.provider_order_id == order_id)
    return db().scalar(q.with_for_update() if lock else q)


def _return_urls(rec: Recovery) -> tuple[str, str]:
    base = config.settings.app_base_url
    return (f"{base}/checkout/paypal/return?recovery_id={rec.id}",
            f"{base}/checkout/paypal/cancel?recovery_id={rec.id}")


def create_order(user: User, recovery_id: UUID, idem_key: str) -> Payment:
    existing = db().scalar(select(Payment).where(Payment.idempotency_key == idem_key))
    if existing:
        if existing.user_id != user.id or existing.recovery_id != recovery_id:
            raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "This idempotency key was used for another request.")
        return existing
    rec, role = get_recovery(user, recovery_id)
    _require(rec, role, "claimant", "delivery", {"awaiting_payment"})
    if not rec.quote_expires_at or rec.quote_expires_at < now():
        _quote(rec)
    mode = config.settings.paypal_mode
    # Inserted only once the order id is known (provider_order_id is unique).
    p = Payment(id=uuid.uuid4(), recovery_id=rec.id, user_id=user.id, provider_mode=mode,
                amount_minor=rec.delivery_quote_minor or 0, currency=rec.currency or "USD",  # server-derived
                idempotency_key=idem_key)
    if mode == "mock":
        p.provider_order_id = "MOCK-" + secrets.token_hex(8).upper()
        p.approval_url = (f"{config.settings.app_base_url}/api/v1/dev/mock-paypal/checkout"
                          f"?token={p.provider_order_id}")
        db().add(p)
        _event(rec, user, "payment_pending", "Payment started (mock checkout, local development).")
        return p
    return_url, cancel_url = _return_urls(rec)
    try:
        order = paypal.create_order(amount_minor=p.amount_minor, currency=p.currency, reference_id=str(rec.id),
                                    custom_id=str(p.id), request_id=f"create-{p.id}",
                                    return_url=return_url, cancel_url=cancel_url)
    except paypal.PayPalError as exc:
        log.warning("paypal create order failed payment=%s: %s", p.id, exc)
        raise ApiError(502, "PAYMENT_PROVIDER_UNAVAILABLE", "PayPal is unavailable. Try again shortly.")
    link = paypal.approval_link(order)
    if not order.get("id") or not link:
        raise ApiError(502, "PAYMENT_PROVIDER_UNAVAILABLE", "PayPal returned an unexpected response.")
    p.provider_order_id, p.approval_url = order["id"], link
    db().add(p)
    _event(rec, user, "payment_pending", "Payment started (PayPal Sandbox).")
    return p


def approval_url(p: Payment) -> str:
    return p.approval_url or ""


def payer_payment(user: User, order_id: str) -> Payment:
    """The payment for this order, only if `user` is the payer (404 otherwise, so ids don't leak)."""
    p = payment_by_order(order_id)
    if not p or p.user_id != user.id:
        raise not_found("payment")
    return p


def mock_approve(user: User, order_id: str) -> Payment:
    p = payer_payment(user, order_id)
    if p.provider_mode != "mock":
        raise not_found("payment")  # real orders are approved on PayPal, never here
    if p.status == "created":
        p.status = "approved"
    return p


# --------------------------------------------------------------------- capture ----

def _apply_capture(p: Payment, actor: User | None, capture_id: str) -> None:
    """Mark captured and advance the recovery. Safe to call once per payment."""
    rec = db().get(Recovery, p.recovery_id)
    c = db().get(Claim, rec.claim_id)
    org = claim_org(c)
    p.status = "captured"
    p.provider_capture_id = capture_id
    p.captured_at = now()
    if rec.status != "awaiting_payment":
        # Captured after the recovery moved on (e.g. cancelled mid-checkout): money was taken,
        # so record it and flag for a manual refund rather than refusing the provider's truth.
        audit(actor, org, "payment.captured_needs_refund", "payment", p.id,
              reason=f"Captured while recovery was {rec.status}", after={"status": "captured"})
        notify_org(org, claim_found(c).location_id, {"manager", "admin"}, "payment.needs_refund",
                   "Payment needs a refund", f"Claim {c.reference}: payment captured after cancellation.",
                   "payment", p.id)
        return
    rec.status = "preparing"
    sandbox = p.provider_mode == "sandbox"
    _event(rec, actor, "payment_captured",
           "Delivery payment confirmed (PayPal Sandbox)." if sandbox else "Delivery payment confirmed (mock).")
    _event(rec, None, "preparing", "Staff are preparing the item for dispatch.")
    notify(p.user_id, "payment.captured", "Payment confirmed", "Delivery payment received.", "recovery", rec.id)
    notify_org(org, claim_found(c).location_id, ALL_STAFF_ROLES, "payment.captured", "Delivery paid",
               f"Claim {c.reference} is ready to dispatch.", "recovery", rec.id)
    audit(actor, org, "payment.captured", "payment", p.id, after={"status": "captured"})
    emit("payment.captured", "payment", p.id, org,
         {"payment_id": str(p.id), "recovery_id": str(rec.id), "amount_minor": p.amount_minor,
          "currency": p.currency})


def _apply_paypal_capture(p: Payment, actor: User | None, capture: dict[str, Any] | None) -> str:
    """Verify a PayPal capture object against the stored payment and apply it.

    Returns "captured", "pending", "failed", "mismatch" or "none".
    """
    if not capture:
        return "none"
    status = capture.get("status")
    amount = capture.get("amount") or {}
    if status == "COMPLETED":
        currency = amount.get("currency_code")
        if currency != p.currency or paypal.to_minor(amount.get("value"), p.currency) != p.amount_minor:
            p.status = "unknown"
            audit(actor, claim_org(db().get(Claim, db().get(Recovery, p.recovery_id).claim_id)),
                  "payment.amount_mismatch", "payment", p.id,
                  reason=f"PayPal captured {amount.get('value')} {currency}; expected "
                         f"{paypal.to_value(p.amount_minor, p.currency)} {p.currency}")
            return "mismatch"
        _apply_capture(p, actor, str(capture.get("id"))[:64])
        return "captured"
    if status == "PENDING":
        p.status = "approved"  # funds pending at PayPal; the webhook completes it later
        return "pending"
    if status in {"DECLINED", "FAILED"}:
        p.status = "failed"
        return "failed"
    return "none"


def capture_order(user: User, order_id: str) -> Payment:
    p = payment_by_order(order_id, lock=True)
    if not p or p.user_id != user.id:
        raise not_found("payment")
    if p.status == "captured":
        return p  # idempotent
    rec = db().get(Recovery, p.recovery_id)
    if rec.status != "awaiting_payment":
        raise ApiError(409, "RECOVERY_INVALID_STATE", "This recovery is not awaiting payment.")

    if p.provider_mode == "mock":
        if p.status != "approved":
            raise ApiError(409, "PAYMENT_NOT_APPROVED", "The buyer has not approved this payment yet.")
        _apply_capture(p, user, "MOCKCAP-" + secrets.token_hex(6).upper())
        return p

    try:
        order = paypal.capture_order(order_id, request_id=f"capture-{p.id}")
    except paypal.OrderNotApproved:
        raise ApiError(409, "PAYMENT_NOT_APPROVED", "The buyer has not approved this payment yet.")
    except paypal.OrderAlreadyCaptured:
        order = _get_order_or_reconcile(p)
    except paypal.PayPalError as exc:
        log.warning("paypal capture uncertain payment=%s: %s", p.id, exc)
        _schedule_reconcile(p)
        raise ApiError(502, "PAYMENT_PROVIDER_UNAVAILABLE",
                       "Couldn't confirm the payment with PayPal yet. Its status will update shortly.")
    outcome = _apply_paypal_capture(p, user, paypal.first_capture(order))
    if outcome == "mismatch":
        return p  # status "unknown": never advance on a wrong amount
    if outcome == "none" and order.get("status") != "COMPLETED":
        raise ApiError(409, "PAYMENT_NOT_APPROVED", "The buyer has not approved this payment yet.")
    return p


def _get_order_or_reconcile(p: Payment) -> dict[str, Any]:
    try:
        return paypal.get_order(p.provider_order_id)
    except paypal.PayPalError:
        _schedule_reconcile(p)
        raise ApiError(502, "PAYMENT_PROVIDER_UNAVAILABLE",
                       "Couldn't confirm the payment with PayPal yet. Its status will update shortly.")


def _schedule_reconcile(p: Payment) -> None:
    emit_detached("payment.reconcile", "payment", p.id, None, {"payment_id": str(p.id)},
                  delay_seconds=RECONCILE_DELAY_SECONDS)


def reconcile(payment_id: UUID) -> str:
    """Worker job `payment.reconcile`: ask PayPal for the order and apply what it says.

    Raises on network errors so the worker retries with backoff.
    """
    p = db().get(Payment, payment_id, with_for_update=True)
    if not p or p.provider_mode != "sandbox" or p.status in {"captured", "failed", "refunded"}:
        return "nothing_to_do"
    order = paypal.get_order(p.provider_order_id)
    outcome = _apply_paypal_capture(p, None, paypal.first_capture(order))
    if outcome != "none" or order.get("status") != "APPROVED":
        return outcome
    # Approved at PayPal but never captured (buyer closed the tab, or the capture call was lost).
    if db().get(Recovery, p.recovery_id).status != "awaiting_payment":
        if p.status == "created":
            p.status = "approved"  # recovery moved on (e.g. cancelled): don't take the money
        return "none"
    try:  # same PayPal-Request-Id as the browser capture, so PayPal treats a repeat as one capture
        order = paypal.capture_order(p.provider_order_id, request_id=f"capture-{p.id}")
    except paypal.OrderNotApproved:
        return "none"
    except paypal.OrderAlreadyCaptured:
        order = paypal.get_order(p.provider_order_id)
    return _apply_paypal_capture(p, None, paypal.first_capture(order))


def get_payment(user: User, payment_id: UUID) -> Payment:
    p = db().get(Payment, payment_id)
    if not p:
        raise not_found("payment")
    get_recovery(user, p.recovery_id)  # 404 if no access
    return p


# -------------------------------------------------------------------- webhook ----

def _redact(event: dict[str, Any]) -> dict[str, Any]:
    """Keep ids, statuses and amounts only; drop payer details (never store/log personal data)."""
    res = event.get("resource") or {}
    if str(event.get("event_type", "")).startswith("CHECKOUT.ORDER."):
        order_id = res.get("id")  # the resource is the order itself
    else:
        order_id = ((res.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")
    return {
        "id": event.get("id"), "event_type": event.get("event_type"), "create_time": event.get("create_time"),
        "resource": {"id": res.get("id"), "status": res.get("status"), "amount": res.get("amount"),
                     "order_id": order_id},
    }


def handle_webhook(headers: dict[str, str], event: dict[str, Any]) -> str:
    """Verify, dedupe and reconcile a PayPal webhook. Returns 'processed' | 'duplicate' | 'ignored'."""
    if not config.settings.paypal_webhook_configured:
        raise ApiError(503, "WEBHOOK_NOT_CONFIGURED", "PayPal webhooks are not configured on this server.")
    event_id, event_type = event.get("id"), event.get("event_type")
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        raise ApiError(400, "INVALID_WEBHOOK", "Malformed webhook event.")
    try:
        verified = paypal.verify_webhook(headers, event)
    except Exception:
        raise ApiError(502, "WEBHOOK_VERIFICATION_UNAVAILABLE", "Could not verify the webhook with PayPal.")
    if not verified:
        raise ApiError(400, "INVALID_WEBHOOK_SIGNATURE", "Webhook signature verification failed.")

    redacted = _redact(event)
    inserted = db().execute(
        insert(WebhookEvent).values(provider="paypal", provider_event_id=event_id[:100],
                                    event_type=event_type[:100], verified_at=now(), payload_redacted=redacted)
        .on_conflict_do_nothing(index_elements=["provider", "provider_event_id"])
        .returning(WebhookEvent.id)).scalar()
    if inserted is None:
        return "duplicate"
    row = db().get(WebhookEvent, inserted)

    outcome = "ignored"
    order_id = redacted["resource"]["order_id"]
    p = payment_by_order(order_id, lock=True) if isinstance(order_id, str) else None
    resource = event.get("resource") or {}
    if p and p.status != "captured":
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            if _apply_paypal_capture(p, None, resource) in {"captured", "mismatch"}:
                outcome = "processed"
        elif event_type in {"PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.DECLINED"}:
            p.status = "failed"
            outcome = "processed"
        elif (event_type == "CHECKOUT.ORDER.APPROVED" and p.provider_mode == "sandbox"
              and p.status in {"created", "approved"}):
            # Never trust the webhook body for money: the job re-reads the order from PayPal and
            # captures only if the recovery is still awaiting payment. The delay lets the buyer's
            # own return-page capture finish first; the job then finds it captured and stops.
            p.status = "approved"
            emit("payment.reconcile", "payment", p.id, None, {"payment_id": str(p.id)},
                 delay_seconds=RECONCILE_DELAY_SECONDS)
            outcome = "processed"
    row.processing_status = outcome
    row.processed_at = now()
    return outcome
