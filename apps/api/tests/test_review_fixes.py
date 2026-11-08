"""Regression tests for the 2026-11-08 API stub review, items 1-4."""

import dataclasses
from uuid import UUID

import pytest

from app.core import config
from app.db.models import LocationMembership, OrganisationMembership
from app.db.session import transaction
from app.services.auth import user_by_email

from .test_demo_flow import data, err, lost_laptop_body, org_id


def harbourview_locations(c):
    hv = org_id(c, "harbourview-airport")
    locs = {loc["name"]: loc["id"] for loc in data(c.get(f"/api/v1/organisations/{hv}/locations"))}
    return hv, locs


def claim_top_match(c, report_id, statement="It is mine."):
    match = data(c.get(f"/api/v1/reports/{report_id}/matches"))[0]
    return data(c.post(f"/api/v1/matches/{match['id']}/claims", json={"statement": statement}), 201)


# ---- 1. PATCH with null required fields ----------------------------------------------------------

@pytest.mark.parametrize("field", ["category", "item_label", "description", "last_location"])
def test_patch_null_required_field_is_400_and_report_unchanged(login, field):
    owner = login("owner@reclaim.example")
    rep = data(owner.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)
    r = owner.patch(f"/api/v1/reports/{rep['id']}", json={field: None})
    err(r, 400, "VALIDATION_ERROR")
    assert r.json()["error"]["details"]["fields"][0]["loc"] == ["body", field]
    after = data(owner.get(f"/api/v1/reports/{rep['id']}"))
    assert after["category"] == "electronics" and after["location_label"] == "Terminal 1, airport"


def test_patch_optional_field_can_be_cleared(login):
    owner = login("owner@reclaim.example")
    rep = data(owner.post("/api/v1/reports/lost", json=lost_laptop_body() | {"brand": "Example"}), 201)
    assert data(owner.patch(f"/api/v1/reports/{rep['id']}", json={"brand": None}))["brand"] is None


def test_patch_rejects_inverted_lost_window(login):
    owner = login("owner@reclaim.example")
    body = lost_laptop_body()
    rep = data(owner.post("/api/v1/reports/lost", json=body), 201)
    # Both in the request body.
    err(owner.patch(f"/api/v1/reports/{rep['id']}", json={
        "lost_at_start": body["lost_at_end"], "lost_at_end": body["lost_at_start"]}), 400, "VALIDATION_ERROR")
    # Only the end, earlier than the stored start.
    r = owner.patch(f"/api/v1/reports/{rep['id']}", json={"lost_at_end": "2000-01-01T00:00:00Z"})
    err(r, 400, "VALIDATION_ERROR")
    assert r.json()["error"]["details"]["fields"][0]["loc"] == ["body", "lost_at_end"]
    assert data(owner.get(f"/api/v1/reports/{rep['id']}"))["lost_at_end"] is not None


# ---- 2. One approved owner per found item (FR-019) ---------------------------------------------

def test_second_approval_on_same_found_item_is_409(login):
    owner, other = login("owner@reclaim.example"), login("other@reclaim.example")
    reviewer = login("reviewer@harbourview.example")
    first = claim_top_match(owner, data(owner.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)["id"])
    second = claim_top_match(other, data(other.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)["id"])
    assert first["match"]["found_item"]["report_id"] == second["match"]["found_item"]["report_id"]

    reason = {"reason": "Described the private sticker correctly."}
    data(reviewer.post(f"/api/v1/claims/{first['id']}/review", json={"decision": "approved"} | reason))
    r = reviewer.post(f"/api/v1/claims/{second['id']}/review", json={"decision": "approved"} | reason)
    err(r, 409, "FOUND_ITEM_ALREADY_CLAIMED")
    assert r.json()["error"]["details"]["approved_claim_reference"] == first["reference"]

    # The losing claim stays pending for a human decision, without an approve action.
    pending = data(reviewer.get(f"/api/v1/claims/{second['id']}"))
    assert pending["status"] == "pending"
    assert "approve" not in pending["available_actions"] and "reject" in pending["available_actions"]
    assert any(f["severity"] == "warning" and first["reference"] in f["message"]
               for f in pending["ai_assist"]["flags"])
    data(reviewer.post(f"/api/v1/claims/{second['id']}/review",
                       json={"decision": "rejected", "reason": "Item already returned to the approved claimant."}))


# ---- 3. Location scope (FR-017, FR-029, docs/08 §8.11) -----------------------------------------

def test_reviewer_limited_to_one_location(client, login):
    owner = login("owner@reclaim.example")
    hv, locs = harbourview_locations(owner)
    data(client.post("/api/v1/auth/register", json={
        "email": "t1reviewer@harbourview.example", "password": "reclaim-demo", "display_name": "T1 Only"}), 201)
    with transaction() as s:
        user = user_by_email("t1reviewer@harbourview.example")
        s.add(OrganisationMembership(organisation_id=UUID(hv), user_id=user.id, role="reviewer"))
        s.add(LocationMembership(location_id=UUID(locs["Terminal 1 Lost Property"]), user_id=user.id))
    t1 = login("t1reviewer@harbourview.example")

    # Seeded backpack claim is at Terminal 3: invisible and undecidable.
    t3_claim = data(owner.get("/api/v1/claims/mine"))[0]
    err(t1.get(f"/api/v1/claims/{t3_claim['id']}"), 404, "CLAIM_NOT_FOUND")
    err(t1.post(f"/api/v1/claims/{t3_claim['id']}/review",
                json={"decision": "approved", "reason": "Out of scope attempt."}), 404, "CLAIM_NOT_FOUND")
    assert all(c["id"] != t3_claim["id"] for c in data(t1.get(f"/api/v1/organisations/{hv}/claims")))
    t3_found = data(owner.get(f"/api/v1/claims/{t3_claim['id']}"))["match"]["found_item"]["report_id"]
    err(t1.get(f"/api/v1/reports/{t3_found}"), 404, "REPORT_NOT_FOUND")
    err(t1.post("/api/v1/reports/found", json={
        "category": "phone", "item_label": "Phone", "description": "Black phone",
        "custody_status": "organisation_holds", "organisation_id": hv,
        "location_id": locs["Terminal 3 Lost Property"]}), 403, "LOCATION_OUT_OF_SCOPE")

    # A Terminal 1 claim is in scope: visible, listed, decidable.
    t1_claim = claim_top_match(owner, data(owner.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)["id"])
    assert any(c["id"] == t1_claim["id"] for c in data(t1.get(f"/api/v1/organisations/{hv}/claims")))
    data(t1.post(f"/api/v1/claims/{t1_claim['id']}/review",
                 json={"decision": "approved", "reason": "Described the private sticker correctly."}))

    # Recoveries follow the same scope.
    reviewer = login("reviewer@harbourview.example")
    data(reviewer.post(f"/api/v1/claims/{t3_claim['id']}/review",
                       json={"decision": "approved", "reason": "Contents and zip pull match the record."}))
    rec = data(owner.post(f"/api/v1/claims/{t3_claim['id']}/recoveries", json={"method": "collection"}), 201)
    err(t1.get(f"/api/v1/recoveries/{rec['id']}"), 404, "RECOVERY_NOT_FOUND")
    err(t1.post(f"/api/v1/recoveries/{rec['id']}/collection/confirm"), 404, "RECOVERY_NOT_FOUND")


# ---- 4. Dev routes -------------------------------------------------------------------------------

@pytest.fixture()
def dev_routes_off(monkeypatch):
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, enable_dev_routes=False))


def test_dev_routes_404_when_disabled(client, dev_routes_off):
    err(client.post("/api/v1/dev/reset"), 404, "NOT_FOUND")
    err(client.get("/api/v1/dev/demo-accounts"), 404, "NOT_FOUND")
    err(client.get("/api/v1/dev/mock-paypal/approve?token=x"), 404, "NOT_FOUND")


def test_mock_paypal_requires_payers_session(client, login):
    owner, other = login("owner@reclaim.example"), login("other@reclaim.example")
    reviewer = login("reviewer@harbourview.example")
    claim = data(owner.get("/api/v1/claims/mine"))[0]
    data(reviewer.post(f"/api/v1/claims/{claim['id']}/review",
                       json={"decision": "approved", "reason": "Contents and zip pull match the record."}))
    rec = data(owner.post(f"/api/v1/claims/{claim['id']}/recoveries", json={
        "method": "delivery",
        "address": {"recipient_name": "Dana", "line1": "1 Example St", "city": "Dubai", "country_code": "AE"},
    }), 201)
    order = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": "key-abcdefgh"}))
    assert order["approval_url"].startswith(config.settings.app_base_url + "/api/v1/dev/mock-paypal/checkout")
    tok = order["paypal_order_id"]

    err(client.get(f"/api/v1/dev/mock-paypal/approve?token={tok}", follow_redirects=False), 401, "UNAUTHENTICATED")
    for path in ("checkout", "approve", "cancel"):
        err(other.get(f"/api/v1/dev/mock-paypal/{path}?token={tok}", follow_redirects=False), 404, "PAYMENT_NOT_FOUND")
    assert data(owner.get(f"/api/v1/payments/{order['payment_id']}"))["status"] == "created"
    assert owner.get(f"/api/v1/dev/mock-paypal/checkout?token={tok}").status_code == 200
    assert owner.get(f"/api/v1/dev/mock-paypal/approve?token={tok}", follow_redirects=False).status_code == 303
    assert data(owner.get(f"/api/v1/payments/{order['payment_id']}"))["status"] == "approved"
