"""Day 3: PayPal Orders v2 (against a fake PayPal), simulated courier via the worker, Zapier replay
protection, the docs/08 §8.11 security checklist, log redaction and the cases API."""

import dataclasses
import logging
import time
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.core import config
from app.db.models import AuditLog, OutboxEvent, Payment, Recovery, now
from app.db.session import transaction
from app.integrations import paypal, zapier
from app.workers.outbox import drain

from .fake_paypal import FakePayPal
from .test_demo_flow import PNG, data, err, lost_laptop_body
from .test_item5_security import approved_backpack_claim, capture_event, webhook_headers


def settings(monkeypatch, **changes):
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, **changes))


@pytest.fixture()
def pp(monkeypatch):
    fake = FakePayPal()
    monkeypatch.setattr(paypal, "transport", fake.transport())
    paypal.reset_token_cache()
    settings(monkeypatch, paypal_client_id="cid", paypal_client_secret="secret", paypal_webhook_id="WH-TEST")
    assert config.settings.paypal_mode == "sandbox"
    return fake


def delivery_recovery(login):
    owner, claim = approved_backpack_claim(login)
    rec = data(owner.post(f"/api/v1/claims/{claim['id']}/recoveries", json={
        "method": "delivery",
        "address": {"recipient_name": "Dana", "line1": "1 Example St", "city": "Dubai", "country_code": "AE"},
    }), 201)
    return owner, rec


def make_due(event_type):
    with transaction() as s:
        s.execute(update(OutboxEvent).where(OutboxEvent.event_type == event_type)
                  .values(next_attempt_at=now() - timedelta(seconds=1)))


# ---- PayPal Orders v2 -----------------------------------------------------------------------------

def test_create_order_uses_quote_and_is_idempotent(login, pp):
    owner, rec = delivery_recovery(login)
    body = {"recovery_id": rec["id"], "idempotency_key": "key-sandbox-1"}
    order = data(owner.post("/api/v1/payments/paypal/create-order", json=body))
    again = data(owner.post("/api/v1/payments/paypal/create-order", json=body))
    assert order == again and pp.count("POST", "/v2/checkout/orders") == 1
    assert order["approval_url"].startswith("https://www.sandbox.paypal.com/checkoutnow?token=")
    sent = pp.orders[order["paypal_order_id"]]["request"]
    assert sent["purchase_units"][0]["amount"] == {"currency_code": "USD", "value": "15.00"}  # from the quote
    ctx = sent["payment_source"]["paypal"]["experience_context"]
    assert ctx["return_url"] == f"{config.settings.app_base_url}/checkout/paypal/return?recovery_id={rec['id']}"
    assert ctx["cancel_url"].endswith(f"/checkout/paypal/cancel?recovery_id={rec['id']}")


def test_client_cannot_set_amount(login, pp):
    owner, rec = delivery_recovery(login)
    err(owner.post("/api/v1/payments/paypal/create-order",
                   json={"recovery_id": rec["id"], "idempotency_key": "key-sandbox-2", "amount_minor": 1}),
        400, "VALIDATION_ERROR")


def test_capture_requires_approval_then_captures_once(login, pp):
    owner, rec = delivery_recovery(login)
    order = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": "key-sandbox-3"}))
    oid = order["paypal_order_id"]
    err(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": oid}), 409, "PAYMENT_NOT_APPROVED")
    assert data(owner.get(f"/api/v1/recoveries/{rec['id']}"))["status"] == "awaiting_payment"
    err(owner.get(f"/api/v1/dev/mock-paypal/approve?token={oid}", follow_redirects=False), 404, "PAYMENT_NOT_FOUND")

    pp.approve(oid)  # buyer approves on PayPal
    p1 = data(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": oid}))
    p2 = data(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": oid}))
    assert p1["status"] == p2["status"] == "captured" and p1["is_sandbox"]
    assert pp.count("POST", f"/v2/checkout/orders/{oid}/capture") == 2  # the not-approved try + one capture
    rec = data(owner.get(f"/api/v1/recoveries/{rec['id']}"))
    assert rec["status"] == "preparing"
    assert any(e["description"] == "Delivery payment confirmed (PayPal Sandbox)." for e in rec["timeline"])


def test_capture_amount_mismatch_never_advances(login, pp):
    owner, rec = delivery_recovery(login)
    order = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": "key-sandbox-4"}))
    pp.approve(order["paypal_order_id"])
    pp.capture_override = {"id": "CAP-X", "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "1.00"}}
    p = data(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": order["paypal_order_id"]}))
    assert p["status"] == "unknown"
    assert data(owner.get(f"/api/v1/recoveries/{rec['id']}"))["status"] == "awaiting_payment"
    with transaction() as s:
        assert s.scalar(select(AuditLog.reason).where(AuditLog.action == "payment.amount_mismatch"))


def test_lost_capture_response_is_reconciled_by_worker(login, pp):
    owner, rec = delivery_recovery(login)
    order = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": "key-sandbox-5"}))
    oid = order["paypal_order_id"]
    pp.approve(oid)
    pp.fail_next = 500
    err(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": oid}),
        502, "PAYMENT_PROVIDER_UNAVAILABLE")
    with transaction() as s:  # the reconcile job survived the failed request's rollback
        job = s.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "payment.reconcile"))
        assert job and job.next_attempt_at > now()
    pp.complete(oid)  # it actually went through at PayPal
    make_due("payment.reconcile")
    drain()
    rec = data(owner.get(f"/api/v1/recoveries/{rec['id']}"))
    assert rec["status"] == "preparing" and rec["payment"]["status"] == "captured"


def test_create_order_provider_outage(login, pp):
    owner, rec = delivery_recovery(login)
    pp.fail_next = 503
    err(owner.post("/api/v1/payments/paypal/create-order",
                   json={"recovery_id": rec["id"], "idempotency_key": "key-sandbox-6"}),
        502, "PAYMENT_PROVIDER_UNAVAILABLE")
    with transaction() as s:
        assert s.scalar(select(Payment).where(Payment.recovery_id == rec["id"])) is None


def test_webhook_after_cancellation_flags_refund(login, pp):
    owner, rec = delivery_recovery(login)
    order = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": "key-sandbox-7"}))
    data(owner.post(f"/api/v1/recoveries/{rec['id']}/cancel", json={"reason": "changed my mind"}))
    out = data(owner.post("/api/v1/payments/paypal/webhook", json=capture_event(order["paypal_order_id"]),
                          headers=webhook_headers()))
    assert out["outcome"] == "processed"
    rec = data(owner.get(f"/api/v1/recoveries/{rec['id']}"))
    assert rec["status"] == "cancelled" and rec["payment"]["status"] == "captured"
    with transaction() as s:
        assert s.scalar(select(AuditLog).where(AuditLog.action == "payment.captured_needs_refund"))


def test_webhook_amount_mismatch_not_applied(login, pp):
    owner, rec = delivery_recovery(login)
    order = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": "key-sandbox-8"}))
    data(owner.post("/api/v1/payments/paypal/webhook", json=capture_event(order["paypal_order_id"], value="0.01"),
                    headers=webhook_headers()))
    rec = data(owner.get(f"/api/v1/recoveries/{rec['id']}"))
    assert rec["status"] == "awaiting_payment" and rec["payment"]["status"] == "unknown"


def test_money_conversion():
    assert paypal.to_value(1500, "USD") == "15.00" and paypal.to_value(5, "USD") == "0.05"
    assert paypal.to_minor("15.00", "USD") == 1500 and paypal.to_minor("15.001", "USD") is None
    assert paypal.to_value(1500, "JPY") == "1500" and paypal.to_minor("abc", "USD") is None


# ---- simulated courier ------------------------------------------------------------------------------

def test_courier_advances_via_worker(login):
    owner, rec = delivery_recovery(login)
    staff = login("staff@harbourview.example")
    order = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": "key-courier-1"}))
    owner.get(f"/api/v1/dev/mock-paypal/approve?token={order['paypal_order_id']}", follow_redirects=False)
    data(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": order["paypal_order_id"]}))
    data(staff.post(f"/api/v1/recoveries/{rec['id']}/delivery/dispatch"))
    assert data(owner.get(f"/api/v1/recoveries/{rec['id']}"))["status"] == "dispatched"  # not due yet
    make_due("recovery.courier_advance")
    drain()
    rec = data(owner.get(f"/api/v1/recoveries/{rec['id']}"))
    assert rec["status"] == "in_transit" and rec["timeline"][-1]["is_simulated"]
    types = [n["type"] for n in data(owner.get("/api/v1/notifications"))]
    assert "recovery.in_transit" in types


# ---- Zapier replay protection -------------------------------------------------------------------------

def test_zapier_signature_verification():
    body, ts = b'{"event_id":"e1"}', str(int(time.time()))
    sig = zapier.sign("secret", ts, body)
    assert zapier.verify("secret", ts, body, sig)
    assert not zapier.verify("secret", ts, body + b" ", sig)  # tampered
    assert not zapier.verify("other", ts, body, sig)  # wrong key
    assert not zapier.verify("secret", ts, body, sig, now=time.time() + 3600)  # replayed later
    assert not zapier.verify("secret", "not-a-number", body, sig)


# ---- security checklist (docs/08 §8.11) -----------------------------------------------------------------

def test_disguised_executable_rejected(login):
    owner = login("owner@reclaim.example")
    exe = b"MZ\x90\x00" + b"\x00" * 60
    for ctype in ("image/png", "image/jpeg", "image/webp", "application/pdf"):
        r = owner.post("/api/v1/uploads", files={"file": ("photo.png", exe, ctype)},
                       data={"visibility": "private_evidence"})
        err(r, 415, "FILE_SIGNATURE_MISMATCH")
    err(owner.post("/api/v1/uploads", files={"file": ("x.exe", exe, "application/x-msdownload")}),
        415, "UNSUPPORTED_FILE_TYPE")


def test_expired_pickup_token_rejected(login):
    owner, claim = approved_backpack_claim(login)
    reviewer = login("reviewer@harbourview.example")
    rec = data(owner.post(f"/api/v1/claims/{claim['id']}/recoveries", json={"method": "collection"}), 201)
    data(reviewer.post(f"/api/v1/recoveries/{rec['id']}/collection/confirm"))
    token = data(owner.post(f"/api/v1/recoveries/{rec['id']}/collection/pickup-token"))["pickup_token"]
    with transaction() as s:
        s.get(Recovery, rec["id"]).pickup_token_expires_at = now() - timedelta(minutes=1)
    err(reviewer.post(f"/api/v1/recoveries/{rec['id']}/collection/validate-token", json={"token": token}),
        409, "PICKUP_TOKEN_EXPIRED")
    err(owner.post(f"/api/v1/recoveries/{rec['id']}/collection/pickup-token"), 409, "PICKUP_TOKEN_EXPIRED")


def test_extraction_never_overwrites_user_fields(login):
    owner = login("owner@reclaim.example")
    body = lost_laptop_body(as_draft=True) | {"item_label": "My work machine", "category": "other"}
    rep = data(owner.post("/api/v1/reports/lost", json=body), 201)
    data(owner.post(f"/api/v1/reports/{rep['id']}/extract"), 202)
    assert data(owner.get(f"/api/v1/reports/{rep['id']}/extraction"))["category"]["value"] == "electronics"
    after = data(owner.get(f"/api/v1/reports/{rep['id']}"))
    assert after["item_label"] == "My work machine" and after["category"] == "other"


def test_public_match_and_found_views_exclude_private_values(login):
    owner = login("owner@reclaim.example")
    rep = data(owner.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)
    raw = owner.get(f"/api/v1/reports/{rep['id']}/matches").text + owner.get("/api/v1/matches/mine").text
    found_id = data(owner.get(f"/api/v1/reports/{rep['id']}/matches"))[0]["found_item"]["report_id"]
    raw += owner.get(f"/api/v1/reports/{found_id}").text
    for secret in ("blue mountain sticker", "small dent", "Cage 2", "shelf L-04", "7731"):
        assert secret not in raw


def test_logs_contain_no_secrets(login, caplog, monkeypatch, pp):
    settings(monkeypatch, zapier_webhook_url="https://hooks.zapier.test/catch/SECRETPATH",
             zapier_webhook_secret="zap-secret-value", paypal_client_id="PP-CLIENT-ID-XYZ",
             paypal_client_secret="PP-CLIENT-SECRET-XYZ")
    monkeypatch.setattr(zapier, "transport", pp.transport())  # 404s: forces failure logging paths
    caplog.set_level(logging.DEBUG)
    owner = login("owner@reclaim.example")
    rep = data(owner.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)
    match = data(owner.get(f"/api/v1/reports/{rep['id']}/matches"))[0]
    data(owner.post(f"/api/v1/matches/{match['id']}/claims", json={
        "statement": "PRIVATE-STATEMENT", "answers": [{"question_id": "q_marks", "answer": "PRIVATE-ANSWER"}]}), 201)
    owner.post("/api/v1/auth/login", json={"email": "owner@reclaim.example", "password": "reclaim-demo"})
    text = caplog.text
    assert "reclaim.access" in text and "path=/api/v1/auth/login" in text  # access logging works
    for secret in ("reclaim-demo", "PRIVATE-STATEMENT", "PRIVATE-ANSWER", "SECRETPATH", "zap-secret-value",
                   "fake-token", "PP-CLIENT-ID-XYZ", "PP-CLIENT-SECRET-XYZ", owner.cookies.get("reclaim_session")):
        assert secret not in text, secret


# ---- cases API ----------------------------------------------------------------------------------------------

def test_cases_filters_sort_pagination_and_scope(login):
    staff = login("staff@harbourview.example")
    hv = next(o["id"] for o in data(staff.get("/api/v1/organisations")) if o["slug"] == "harbourview-airport")
    page1 = staff.get(f"/api/v1/organisations/{hv}/cases?limit=2&sort=reported_at")
    rows = data(page1)
    cursor = page1.json()["meta"]["next_cursor"]
    rows2 = data(staff.get(f"/api/v1/organisations/{hv}/cases?limit=2&sort=reported_at&cursor={cursor}"))
    assert len(rows) == 2 and rows2 and {r["id"] for r in rows}.isdisjoint({r["id"] for r in rows2})
    assert [r["reported_at"] for r in rows] == sorted(r["reported_at"] for r in rows)
    pending = data(staff.get(f"/api/v1/organisations/{hv}/cases?claim_status=pending"))
    assert [r["item_label"] for r in pending] == ["Backpack"] and pending[0]["priority"] == "high"
    assert [r["item_label"] for r in data(staff.get(f"/api/v1/organisations/{hv}/cases?q=lapt"))] == ["Laptop", "Laptop"]
    err(staff.get(f"/api/v1/organisations/{hv}/cases?sort=storage_reference"), 400, "VALIDATION_ERROR")
    gm = login("reviewer@grandmeridian.example")
    err(gm.get(f"/api/v1/organisations/{hv}/cases"), 403, "NOT_A_MEMBER")
    assert all("storage_reference" not in r for r in rows)
