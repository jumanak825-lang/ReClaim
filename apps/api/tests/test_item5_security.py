"""Review item 5: rate limits, argon2id, hashed tokens, PayPal webhook verification, signed Zapier delivery."""

import dataclasses
import hashlib
import hmac
import json

import httpx
import pytest
from sqlalchemy import func, select

from app.core import config
from app.db.models import OutboxEvent, Payment, Recovery, Session, User
from app.db.session import transaction
from app.integrations import paypal, zapier
from app.workers.outbox import drain

from .fake_paypal import FakePayPal
from .test_demo_flow import data, err


def settings(monkeypatch, **changes):
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, **changes))


def approved_backpack_claim(login):
    owner, reviewer = login("owner@reclaim.example"), login("reviewer@harbourview.example")
    claim = data(owner.get("/api/v1/claims/mine"))[0]
    data(reviewer.post(f"/api/v1/claims/{claim['id']}/review",
                       json={"decision": "approved", "reason": "Contents and zip pull match the record."}))
    return owner, claim


def delivery_order(login):
    owner, claim = approved_backpack_claim(login)
    rec = data(owner.post(f"/api/v1/claims/{claim['id']}/recoveries", json={
        "method": "delivery",
        "address": {"recipient_name": "Dana", "line1": "1 Example St", "city": "Dubai", "country_code": "AE"},
    }), 201)
    order = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": "key-webhook-1"}))
    return owner, rec, order


# ---- rate limits ----------------------------------------------------------------------------------

def test_login_rate_limited_and_failures_count(client, monkeypatch):
    settings(monkeypatch, rate_limits_enabled=True, rate_limit_auth="3/60")
    bad = {"email": "owner@reclaim.example", "password": "wrong-password"}
    for _ in range(3):
        err(client.post("/api/v1/auth/login", json=bad), 401, "INVALID_CREDENTIALS")  # rolled back, still counted
    r = client.post("/api/v1/auth/login", json=bad | {"password": "reclaim-demo"})
    err(r, 429, "RATE_LIMITED")
    assert int(r.headers["Retry-After"]) >= 1 and r.json()["error"]["details"]["retry_after_seconds"] >= 0


def test_login_rate_limit_is_per_email_too(client, monkeypatch):
    settings(monkeypatch, rate_limits_enabled=True, rate_limit_auth="2/60")
    bad = {"email": "owner@reclaim.example", "password": "wrong-password"}
    for ip in ("1.1.1.1", "2.2.2.2"):
        client.post("/api/v1/auth/login", json=bad, headers={"X-Forwarded-For": ip})
    err(client.post("/api/v1/auth/login", json=bad, headers={"X-Forwarded-For": "3.3.3.3"}), 429, "RATE_LIMITED")


def test_upload_rate_limit_per_user(login, monkeypatch):
    owner = login("owner@reclaim.example")
    settings(monkeypatch, rate_limits_enabled=True, rate_limit_upload="1/60")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    data(owner.post("/api/v1/uploads", files={"file": ("a.png", png, "image/png")}), 201)
    err(owner.post("/api/v1/uploads", files={"file": ("a.png", png, "image/png")}), 429, "RATE_LIMITED")


# ---- password and token storage -------------------------------------------------------------------

def test_passwords_argon2id_and_sessions_hashed(client):
    r = client.post("/api/v1/auth/register",
                    json={"email": "hash@example.org", "password": "longenough1", "display_name": "H"})
    cookie = r.cookies["reclaim_session"]
    with transaction() as s:
        user = s.scalar(select(User).where(User.email == "hash@example.org"))
        assert user.password_hash.startswith("$argon2id$")
        stored = s.scalars(select(Session.token_hash).where(Session.user_id == user.id)).all()
    assert stored == [hashlib.sha256(cookie.encode()).hexdigest()]


def test_pickup_token_stored_only_as_hash(login):
    owner, claim = approved_backpack_claim(login)
    reviewer = login("reviewer@harbourview.example")
    rec = data(owner.post(f"/api/v1/claims/{claim['id']}/recoveries", json={"method": "collection"}), 201)
    data(reviewer.post(f"/api/v1/recoveries/{rec['id']}/collection/confirm"))
    token = data(owner.post(f"/api/v1/recoveries/{rec['id']}/collection/pickup-token"))["pickup_token"]
    with transaction() as s:
        stored = s.get(Recovery, rec["id"]).pickup_token_hash
    assert stored and token.replace("-", "") not in stored and len(stored) == 64


# ---- PayPal webhook -------------------------------------------------------------------------------

@pytest.fixture()
def paypal_mock(monkeypatch):
    fake = FakePayPal()
    monkeypatch.setattr(paypal, "transport", fake.transport())
    paypal.reset_token_cache()
    settings(monkeypatch, paypal_client_id="cid", paypal_client_secret="secret", paypal_webhook_id="WH-TEST")
    return fake


def webhook_headers(sig="good-signature"):
    return {"paypal-auth-algo": "SHA256withRSA", "paypal-cert-url": "https://api.sandbox.paypal.com/cert",
            "paypal-transmission-id": "tx-1", "paypal-transmission-sig": sig,
            "paypal-transmission-time": "2026-11-08T10:00:00Z"}


def capture_event(order_id, event_id="WH-EVT-1", value="15.00"):
    return {"id": event_id, "event_type": "PAYMENT.CAPTURE.COMPLETED", "create_time": "2026-11-08T10:00:00Z",
            "resource": {"id": "CAPTURE-123", "status": "COMPLETED",
                         "amount": {"currency_code": "USD", "value": value},
                         "payer": {"email_address": "buyer@example.com"},
                         "supplementary_data": {"related_ids": {"order_id": order_id}}}}


def test_webhook_rejected_when_not_configured(client):
    err(client.post("/api/v1/payments/paypal/webhook", json=capture_event("X"), headers=webhook_headers()),
        503, "WEBHOOK_NOT_CONFIGURED")


def test_webhook_bad_or_missing_signature_rejected(client, paypal_mock):
    err(client.post("/api/v1/payments/paypal/webhook", json=capture_event("X"),
                    headers=webhook_headers("forged")), 400, "INVALID_WEBHOOK_SIGNATURE")
    err(client.post("/api/v1/payments/paypal/webhook", json=capture_event("X")), 400, "INVALID_WEBHOOK_SIGNATURE")


def test_webhook_captures_once_and_dedupes(login, paypal_mock):
    owner, rec, order = delivery_order(login)
    anon = login("other@reclaim.example")  # webhooks carry no session; any client works
    first = data(anon.post("/api/v1/payments/paypal/webhook", json=capture_event(order["paypal_order_id"]),
                           headers=webhook_headers()))
    again = data(anon.post("/api/v1/payments/paypal/webhook", json=capture_event(order["paypal_order_id"]),
                           headers=webhook_headers()))
    assert first["outcome"] == "processed" and again["outcome"] == "duplicate"
    rec = data(owner.get(f"/api/v1/recoveries/{rec['id']}"))
    assert rec["status"] == "preparing" and rec["payment"]["status"] == "captured"
    assert [e["event_type"] for e in rec["timeline"]].count("payment_captured") == 1
    # The browser capture after a webhook is a no-op, not a second charge.
    p = data(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": order["paypal_order_id"]}))
    assert p["status"] == "captured"
    with transaction() as s:
        assert s.scalar(select(func.count()).select_from(Payment)) == 1


# ---- Zapier ---------------------------------------------------------------------------------------

@pytest.fixture()
def zap(monkeypatch):
    sent: list[httpx.Request] = []
    state = {"status": 200}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(state["status"])

    monkeypatch.setattr(zapier, "transport", httpx.MockTransport(handler))
    settings(monkeypatch, zapier_webhook_url="https://hooks.zapier.test/catch/1", zapier_webhook_secret="zsecret")
    return sent, state


def claim_laptop(login):
    owner = login("owner@reclaim.example")
    from .test_demo_flow import lost_laptop_body

    rep = data(owner.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)
    match = data(owner.get(f"/api/v1/reports/{rep['id']}/matches"))[0]
    return owner, data(owner.post(f"/api/v1/matches/{match['id']}/claims", json={
        "statement": "PRIVATE statement text",
        "answers": [{"question_id": "q_marks", "answer": "PRIVATE blue mountain sticker"}]}), 201)


def test_zapier_events_signed_and_free_of_private_data(login, zap):
    sent, _ = zap
    _, claim = claim_laptop(login)
    types = [json.loads(r.content)["event_type"] for r in sent]
    assert "match.high_priority" in types and "claim.created" in types
    req = next(r for r in sent if json.loads(r.content)["event_type"] == "claim.created")
    body = req.content
    ts = req.headers["X-Reclaim-Timestamp"]
    expected = "v1=" + hmac.new(b"zsecret", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    assert hmac.compare_digest(req.headers["X-Reclaim-Signature"], expected)
    env = json.loads(body)
    assert env["data"]["claim_id"] == claim["id"] and env["event_id"] == req.headers["X-Reclaim-Event-Id"]
    assert b"PRIVATE" not in body  # no statement, answers or evidence
    with transaction() as s:
        assert s.scalar(select(OutboxEvent.delivery_status).where(OutboxEvent.event_type == "claim.created",
                                                                   OutboxEvent.last_error.is_(None))) == "delivered"


def test_zapier_failure_retries_then_dead_letters_without_touching_claim(login, zap, monkeypatch):
    sent, state = zap
    state["status"] = 500
    settings(monkeypatch, worker_max_attempts=2)
    owner, claim = claim_laptop(login)
    assert data(owner.get(f"/api/v1/claims/{claim['id']}"))["status"] == "pending"  # core state unaffected
    with transaction() as s:
        ev = s.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "claim.created",
                                                OutboxEvent.aggregate_id == claim["id"]))
        assert ev.delivery_status == "failed" and ev.attempt_count == 1 and "HTTP 500" in ev.last_error
        ev.next_attempt_at = ev.created_at  # make the retry due now
    drain()
    with transaction() as s:
        ev = s.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "claim.created",
                                                OutboxEvent.aggregate_id == claim["id"]))
        assert ev.delivery_status == "dead" and ev.attempt_count == 2


def test_zapier_not_configured_is_skipped(login):
    _, claim = claim_laptop(login)
    with transaction() as s:
        ev = s.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "claim.created",
                                                OutboxEvent.aggregate_id == claim["id"]))
        assert ev.delivery_status == "skipped"


def test_zapier_test_event_endpoint(login, zap):
    sent, _ = zap
    manager = login("manager@harbourview.example")
    hv = next(o["id"] for o in data(manager.get("/api/v1/organisations")) if o["slug"] == "harbourview-airport")
    err(login("reviewer@harbourview.example").post("/api/v1/integrations/zapier/test",
                                                   json={"organisation_id": hv}), 403, "INSUFFICIENT_ROLE")
    data(manager.post("/api/v1/integrations/zapier/test", json={"organisation_id": hv}))
    assert json.loads(sent[-1].content)["event_type"] == "integration.test"
    integ = data(manager.get(f"/api/v1/organisations/{hv}/integrations"))[0]
    assert integ["status"] == "configured" and integ["last_delivery"]["status"] == "delivered"
