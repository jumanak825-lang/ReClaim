"""docs/reviews/2026-11-09-remaining-setup.md: overview location filter, the CHECKOUT.ORDER.APPROVED
webhook (server-side capture fallback) and the exact Zapier payloads the two demo Zaps read."""

import json

from sqlalchemy import select

from app.core import config

from app.db.models import Location, WebhookEvent
from app.db.session import transaction
from app.workers.outbox import drain

from .test_day3 import delivery_recovery, make_due, pp  # noqa: F401 (fixture)
from .test_demo_flow import data, err
from .test_item5_security import claim_laptop, webhook_headers, zap  # noqa: F401 (fixture)


def hv_ids(c):
    org = next(o["id"] for o in data(c.get("/api/v1/organisations")) if o["slug"] == "harbourview-airport")
    locs = {loc["name"]: loc["id"] for loc in data(c.get(f"/api/v1/organisations/{org}/locations"))}
    return org, locs


# ---- overview location filter ---------------------------------------------------------------------

def test_overview_location_filter_applies_to_every_count(login):
    reviewer = login("reviewer@harbourview.example")  # no location restriction
    org, locs = hv_ids(reviewer)
    url = f"/api/v1/organisations/{org}/overview"
    total = data(reviewer.get(url))
    t1 = data(reviewer.get(f"{url}?location_id={locs['Terminal 1 Lost Property']}"))
    t3 = data(reviewer.get(f"{url}?location_id={locs['Terminal 3 Lost Property']}"))
    counts = ("active_cases", "found_inventory", "pending_claims", "escalated_claims", "recoveries_in_progress")
    for k in counts:
        assert t1[k] + t3[k] == total[k], k
    # Seed: the backpack claim (pending) is at Terminal 3; Terminal 1 holds one laptop.
    assert t3["pending_claims"] == 1 and t1["pending_claims"] == 0
    assert t1["found_inventory"] == 1 and t3["found_inventory"] == 2


def test_overview_location_outside_scope_is_404(login):
    staff = login("staff@harbourview.example")  # limited to Terminal 1 and Terminal 3
    org, _ = hv_ids(staff)
    with transaction() as s:
        extra = Location(organisation_id=org, name="Cargo Office", timezone="Asia/Dubai", country_code="AE")
        s.add(extra)
        s.flush()
        extra_id = extra.id
    gm = login("reviewer@grandmeridian.example")
    gm_org = next(o["id"] for o in data(gm.get("/api/v1/organisations")) if o["slug"] == "grand-meridian-hotel")
    other_org_loc = data(gm.get(f"/api/v1/organisations/{gm_org}/locations"))[0]["id"]

    url = f"/api/v1/organisations/{org}/overview"
    err(staff.get(f"{url}?location_id={extra_id}"), 404, "LOCATION_NOT_FOUND")  # same org, outside their scope
    err(staff.get(f"{url}?location_id={other_org_loc}"), 404, "LOCATION_NOT_FOUND")  # another org's location
    err(staff.get(f"{url}?location_id=00000000-0000-0000-0000-000000000000"), 404, "LOCATION_NOT_FOUND")
    err(staff.get(f"{url}?location_id=not-a-uuid"), 400, "VALIDATION_ERROR")
    # An unrestricted manager can filter to the new location (empty, but allowed).
    mgr = login("manager@harbourview.example")
    assert data(mgr.get(f"{url}?location_id={extra_id}"))["found_inventory"] == 0
    # Non-members still get 403 before any location check.
    err(gm.get(f"{url}?location_id={extra_id}"), 403, "NOT_A_MEMBER")


# ---- CHECKOUT.ORDER.APPROVED ----------------------------------------------------------------------

def approved_event(order_id, event_id="WH-APPROVED-1"):
    return {"id": event_id, "event_type": "CHECKOUT.ORDER.APPROVED", "create_time": "2026-11-09T10:00:00Z",
            "resource": {"id": order_id, "status": "APPROVED", "intent": "CAPTURE",
                         "payer": {"email_address": "buyer@example.com"}}}


def sandbox_order(login, key):
    owner, rec = delivery_recovery(login)
    order = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": key}))
    return owner, rec, order["paypal_order_id"]


def test_order_approved_webhook_captures_when_buyer_never_returns(login, pp):
    owner, rec, oid = sandbox_order(login, "key-approved-1")
    pp.approve(oid)
    out = data(owner.post("/api/v1/payments/paypal/webhook", json=approved_event(oid), headers=webhook_headers()))
    assert out["outcome"] == "processed"
    assert data(owner.get(f"/api/v1/recoveries/{rec['id']}"))["status"] == "awaiting_payment"  # not paid yet
    assert pp.count("POST", f"/v2/checkout/orders/{oid}/capture") == 0  # webhook body is never trusted
    make_due("payment.reconcile")
    drain()
    got = data(owner.get(f"/api/v1/recoveries/{rec['id']}"))
    assert got["status"] == "preparing" and got["payment"]["status"] == "captured"
    assert pp.count("POST", f"/v2/checkout/orders/{oid}/capture") == 1
    with transaction() as s:  # payer details are never stored
        stored = s.scalar(select(WebhookEvent.payload_redacted).where(WebhookEvent.provider_event_id == "WH-APPROVED-1"))
        assert stored["resource"]["order_id"] == oid and "buyer@example.com" not in json.dumps(stored)


def test_order_approved_webhook_then_browser_capture_charges_once(login, pp):
    owner, rec, oid = sandbox_order(login, "key-approved-2")
    pp.approve(oid)
    data(owner.post("/api/v1/payments/paypal/webhook", json=approved_event(oid), headers=webhook_headers()))
    p = data(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": oid}))
    assert p["status"] == "captured"
    make_due("payment.reconcile")
    drain()  # the fallback job finds it captured and stops
    assert pp.count("POST", f"/v2/checkout/orders/{oid}/capture") == 1
    # A duplicate delivery of the same webhook has no effect.
    again = data(owner.post("/api/v1/payments/paypal/webhook", json=approved_event(oid), headers=webhook_headers()))
    assert again["outcome"] == "duplicate"


def test_order_approved_after_cancellation_is_not_captured(login, pp):
    owner, rec, oid = sandbox_order(login, "key-approved-3")
    pp.approve(oid)
    data(owner.post(f"/api/v1/recoveries/{rec['id']}/cancel", json={"reason": "changed my mind"}))
    data(owner.post("/api/v1/payments/paypal/webhook", json=approved_event(oid), headers=webhook_headers()))
    make_due("payment.reconcile")
    drain()
    assert pp.count("POST", f"/v2/checkout/orders/{oid}/capture") == 0  # never take money for a cancelled recovery
    assert data(owner.get(f"/api/v1/recoveries/{rec['id']}"))["status"] == "cancelled"


def test_order_approved_webhook_for_unknown_order_is_ignored(login, pp):
    owner = login("owner@reclaim.example")
    out = data(owner.post("/api/v1/payments/paypal/webhook", json=approved_event("NOT-OURS"), headers=webhook_headers()))
    assert out["outcome"] == "ignored"


# ---- Zapier payloads for the two demo Zaps ----------------------------------------------------------

def test_zap_payload_fields_are_exactly_the_safe_ones(login, zap):
    sent, _ = zap
    claim_laptop(login)
    by_type = {}
    for r in sent:
        env = json.loads(r.content)
        by_type.setdefault(env["event_type"], env)
    assert set(by_type["claim.created"]["data"]) == {"claim_id", "case_reference", "status", "item_label"}
    assert by_type["claim.created"]["data"]["status"] == "pending"
    assert set(by_type["match.high_priority"]["data"]) == {"match_id", "score", "label", "item_label", "category"}
    for env in by_type.values():
        assert set(env) == {"event_id", "event_type", "occurred_at", "organisation_id", "data"}


def test_per_event_hooks_route_each_event_to_its_own_zap(login, zap, monkeypatch):
    sent, state = zap
    from .test_day3 import settings
    settings(monkeypatch, zapier_webhook_url=None,
             zapier_url_match_high_priority="https://hooks.zapier.test/catch/MATCH",
             zapier_url_claim_created="https://hooks.zapier.test/catch/CLAIM")
    claim_laptop(login)
    routed = {(str(r.url).rsplit("/", 1)[-1], json.loads(r.content)["event_type"]) for r in sent}
    assert routed == {("MATCH", "match.high_priority"), ("CLAIM", "claim.created")}

    # The integrations test event reaches both Zaps, and status reports "configured".
    sent.clear()
    mgr = login("manager@harbourview.example")
    org, _ = hv_ids(mgr)
    data(mgr.post("/api/v1/integrations/zapier/test", json={"organisation_id": org}))
    assert sorted(str(r.url).rsplit("/", 1)[-1] for r in sent) == ["CLAIM", "MATCH"]
    status = data(mgr.get(f"/api/v1/organisations/{org}/integrations"))[0]
    assert status["status"] == "configured" and status["last_delivery"]["status"] == "delivered"

    # A failing hook retries the event; the error never contains the hook URL (it is a secret).
    state["status"] = 500
    data(mgr.post("/api/v1/integrations/zapier/test", json={"organisation_id": org}))
    last = data(mgr.get(f"/api/v1/organisations/{org}/integrations"))[0]["last_delivery"]
    assert last["status"] == "failed" and "hook 1/2: HTTP 500" in last["error"] and "zapier.test" not in last["error"]


def test_zapier_not_configured_without_secret(login, monkeypatch):
    from .test_day3 import settings
    settings(monkeypatch, zapier_url_claim_created="https://hooks.zapier.test/catch/CLAIM", zapier_webhook_secret="")
    assert config.settings.zapier_urls_for("claim.created") == [] and not config.settings.zapier_configured
