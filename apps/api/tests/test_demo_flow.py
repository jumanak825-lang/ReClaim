"""End-to-end demo path against the stub, plus docs/05 §5.12 permission checks."""

from datetime import datetime, timedelta, timezone

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def data(r, status=200):
    assert r.status_code == status, r.text
    return r.json()["data"]


def err(r, status, code):
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code, r.text


def iso(dt):
    return dt.isoformat()


def lost_laptop_body(as_draft=False):
    t = datetime.now(timezone.utc)
    return {
        "category": "electronics",
        "item_label": "Laptop",
        "description": "Silver laptop with a small sticker near the keyboard.",
        "lost_at_start": iso(t - timedelta(hours=23)),
        "lost_at_end": iso(t - timedelta(hours=21)),
        "last_location": {"label": "Terminal 1, airport"},
        "attributes_public": {"colour": "silver"},
        "attributes_private": {"distinctive_mark": "small dent on left corner"},
        "as_draft": as_draft,
    }


def org_id(c, slug):
    return next(o["id"] for o in data(c.get("/api/v1/organisations")) if o["slug"] == slug)


def test_unauthenticated(client):
    err(client.get("/api/v1/me"), 401, "UNAUTHENTICATED")


def test_register_login_me(client):
    me = data(client.post("/api/v1/auth/register",
                          json={"email": "New@Example.org", "password": "longenough", "display_name": "New"}), 201)
    assert me["email"] == "new@example.org" and me["is_staff"] is False
    assert data(client.get("/api/v1/me"))["id"] == me["id"]
    assert client.post("/api/v1/auth/logout").status_code == 204
    err(client.get("/api/v1/me"), 401, "UNAUTHENTICATED")
    err(client.post("/api/v1/auth/login", json={"email": "new@example.org", "password": "wrong-pass"}),
        401, "INVALID_CREDENTIALS")


def test_validation_error_envelope(login):
    owner = login("owner@reclaim.example")
    r = owner.post("/api/v1/reports/lost", json={"category": "nope"})
    err(r, 400, "VALIDATION_ERROR")
    assert r.json()["error"]["details"]["fields"]


def test_full_delivery_flow(client, login):
    owner = login("owner@reclaim.example")
    staff = login("staff@harbourview.example")
    reviewer = login("reviewer@harbourview.example")
    other = login("other@reclaim.example")
    gm = login("reviewer@grandmeridian.example")

    # wizard: upload -> draft -> extract -> submit
    img = data(owner.post("/api/v1/uploads", files={"file": ("a.png", PNG, "image/png")}), 201)
    body = lost_laptop_body(as_draft=True) | {"image_ids": [img["id"]]}
    rep = data(owner.post("/api/v1/reports/lost", json=body), 201)
    assert rep["status"] == "draft" and "submit" in rep["available_actions"]
    ex = data(owner.post(f"/api/v1/reports/{rep['id']}/extract"), 202)
    ex = data(owner.get(f"/api/v1/reports/{rep['id']}/extraction"))
    assert ex["status"] == "completed" and ex["colour"]["value"] == "silver" and ex["is_fallback"]
    rep = data(owner.post(f"/api/v1/reports/{rep['id']}/submit"))
    rep = data(owner.get(f"/api/v1/reports/{rep['id']}"))
    assert rep["status"] == "active" and rep["attributes_private"]

    # matcher surfaces the seeded laptop first, as a strong match
    matches = data(owner.get(f"/api/v1/reports/{rep['id']}/matches"))
    top = matches[0]
    assert top["found_item"]["approximate_location"] == "Terminal 1 Lost Property"
    assert top["score"] >= 85 and top["label"] == "Strong potential match"
    assert all(m["score"] <= top["score"] for m in matches)
    assert "start_claim" in top["available_actions"]

    # found report public view hides private fields
    found = data(owner.get(f"/api/v1/reports/{top['found_item']['report_id']}"))
    assert found["viewer_access"] == "public"
    assert found["attributes_private"] is None and found["storage_reference"] is None
    err(other.get(f"/api/v1/reports/{rep['id']}"), 404, "REPORT_NOT_FOUND")

    # claim
    qs = data(owner.get(f"/api/v1/matches/{top['id']}/verification-questions"))
    claim = data(owner.post(f"/api/v1/matches/{top['id']}/claims", json={
        "statement": "It's mine, I left it at gate B12.",
        "answers": [{"question_id": qs[0]["id"], "answer": "A blue mountain sticker by the trackpad and a dent."}],
    }), 201)
    err(owner.post(f"/api/v1/matches/{top['id']}/claims", json={"statement": "again"}), 409, "CLAIM_ALREADY_ACTIVE")

    # privacy + permissions
    err(other.get(f"/api/v1/claims/{claim['id']}"), 404, "CLAIM_NOT_FOUND")
    err(gm.get(f"/api/v1/claims/{claim['id']}"), 404, "CLAIM_NOT_FOUND")
    as_staff = data(staff.get(f"/api/v1/claims/{claim['id']}"))
    assert as_staff["viewer_role"] == "staff" and as_staff["answers"] == [] and as_staff["statement"] is None
    err(staff.post(f"/api/v1/claims/{claim['id']}/review",
                   json={"decision": "approved", "reason": "looks right to me"}), 403, "NOT_A_REVIEWER")
    as_rev = data(reviewer.get(f"/api/v1/claims/{claim['id']}"))
    assert as_rev["ai_assist"] and "approve" in as_rev["available_actions"]
    err(reviewer.post(f"/api/v1/claims/{claim['id']}/review", json={"decision": "approved", "reason": "short"}),
        400, "VALIDATION_ERROR")
    data(reviewer.post(f"/api/v1/claims/{claim['id']}/review",
                       json={"decision": "approved", "reason": "Correctly described the private sticker and dent."}))
    err(reviewer.post(f"/api/v1/claims/{claim['id']}/review",
                      json={"decision": "rejected", "reason": "changed my mind entirely"}), 409, "CLAIM_NOT_REVIEWABLE")

    # recovery: delivery
    claim = data(owner.get(f"/api/v1/claims/{claim['id']}"))
    assert claim["available_actions"] == ["choose_recovery"]
    rec = data(owner.post(f"/api/v1/claims/{claim['id']}/recoveries", json={
        "method": "delivery",
        "address": {"recipient_name": "Dana", "line1": "1 Example St", "city": "Dubai", "country_code": "AE"},
    }), 201)
    assert rec["status"] == "awaiting_payment" and rec["delivery_quote"]["amount_minor"] == 1500
    staff_view = data(staff.get(f"/api/v1/recoveries/{rec['id']}"))
    assert staff_view["delivery_address"]["line1"] is None

    # payment: idempotent create, cannot capture before approval, idempotent capture
    order = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": "key-12345678"}))
    again = data(owner.post("/api/v1/payments/paypal/create-order",
                            json={"recovery_id": rec["id"], "idempotency_key": "key-12345678"}))
    assert again["payment_id"] == order["payment_id"]
    err(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": order["paypal_order_id"]}),
        409, "PAYMENT_NOT_APPROVED")
    r = owner.get(f"/api/v1/dev/mock-paypal/approve?token={order['paypal_order_id']}", follow_redirects=False)
    assert r.status_code == 303 and "/checkout/paypal/return?token=" in r.headers["location"]
    p1 = data(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": order["paypal_order_id"]}))
    p2 = data(owner.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": order["paypal_order_id"]}))
    assert p1["status"] == p2["status"] == "captured" and p1["amount_minor"] == 1500
    err(other.post("/api/v1/payments/paypal/capture-order", json={"paypal_order_id": order["paypal_order_id"]}),
        404, "PAYMENT_NOT_FOUND")

    # dispatch -> in_transit -> received -> completed
    rec = data(staff.post(f"/api/v1/recoveries/{rec['id']}/delivery/dispatch"))
    assert rec["status"] == "dispatched" and rec["tracking_reference"].startswith("SIM-")
    err(owner.post(f"/api/v1/dev/recoveries/{rec['id']}/advance-courier"), 403, "FORBIDDEN")
    rec = data(staff.post(f"/api/v1/dev/recoveries/{rec['id']}/advance-courier"))
    assert rec["status"] == "in_transit"
    rec = data(owner.post(f"/api/v1/recoveries/{rec['id']}/confirm-received"))
    assert rec["status"] == "completed"
    assert data(owner.get(f"/api/v1/reports/{rep['id']}"))["status"] == "resolved"

    # notifications + org views
    assert data(owner.get("/api/v1/notifications/unread-count"))["unread"] > 0
    hv = org_id(staff, "harbourview-airport")
    rows = data(staff.get(f"/api/v1/organisations/{hv}/cases"))
    assert any(r["recovery_status"] == "completed" for r in rows)
    err(gm.get(f"/api/v1/organisations/{hv}/cases"), 403, "NOT_A_MEMBER")
    assert data(reviewer.get(f"/api/v1/organisations/{hv}/audit-logs"))


def test_collection_flow(login):
    owner = login("owner@reclaim.example")
    reviewer = login("reviewer@harbourview.example")
    claim = data(owner.get("/api/v1/claims/mine"))[0]  # seeded backpack claim
    data(reviewer.post(f"/api/v1/claims/{claim['id']}/review",
                       json={"decision": "approved", "reason": "Contents and zip pull match the record."}))
    rec = data(owner.post(f"/api/v1/claims/{claim['id']}/recoveries", json={"method": "collection"}), 201)
    assert rec["status"] == "preparing" and rec["collection"]["opening_hours"]
    err(owner.post(f"/api/v1/recoveries/{rec['id']}/collection/confirm"), 403, "FORBIDDEN")
    staff_rec = data(reviewer.post(f"/api/v1/recoveries/{rec['id']}/collection/confirm"))
    assert staff_rec["pickup_token"] is None  # staff never see the code
    # The code is only stored hashed: GET never returns it; the claimant reveals (rotates) it on demand.
    assert data(owner.get(f"/api/v1/recoveries/{rec['id']}"))["pickup_token"] is None
    assert "show_pickup_code" in data(owner.get(f"/api/v1/recoveries/{rec['id']}"))["available_actions"]
    err(reviewer.post(f"/api/v1/recoveries/{rec['id']}/collection/pickup-token"), 403, "FORBIDDEN")
    first = data(owner.post(f"/api/v1/recoveries/{rec['id']}/collection/pickup-token"))["pickup_token"]
    token = data(owner.post(f"/api/v1/recoveries/{rec['id']}/collection/pickup-token"))["pickup_token"]
    assert first and token and first != token
    err(reviewer.post(f"/api/v1/recoveries/{rec['id']}/collection/validate-token", json={"token": first}),
        400, "INVALID_PICKUP_TOKEN")  # rotated out
    err(reviewer.post(f"/api/v1/recoveries/{rec['id']}/collection/validate-token", json={"token": "WRONG-CODE"}),
        400, "INVALID_PICKUP_TOKEN")
    done = data(reviewer.post(f"/api/v1/recoveries/{rec['id']}/collection/validate-token",
                              json={"token": token.lower()}))  # case/format-insensitive
    assert done["status"] == "completed"
    err(owner.post(f"/api/v1/recoveries/{rec['id']}/collection/pickup-token"), 409, "RECOVERY_INVALID_STATE")


def test_found_report_rules(login):
    owner = login("owner@reclaim.example")
    staff = login("staff@harbourview.example")
    hv = org_id(owner, "harbourview-airport")
    loc = data(owner.get(f"/api/v1/organisations/{hv}/locations"))[0]["id"]
    base = {"category": "phone", "item_label": "Phone", "description": "Black phone"}
    err(owner.post("/api/v1/reports/found", json=base | {
        "custody_status": "organisation_holds", "organisation_id": hv, "location_id": loc}), 403, "NOT_A_MEMBER")
    r = data(owner.post("/api/v1/reports/found", json=base | {
        "custody_status": "finder_holds", "found_location": {"label": "Bus stop"}}), 201)
    assert r["viewer_access"] == "owner"
    r = data(staff.post("/api/v1/reports/found", json=base | {
        "custody_status": "organisation_holds", "organisation_id": hv, "location_id": loc,
        "storage_reference": "Shelf 9"}), 201)
    assert r["storage_reference"] == "Shelf 9"


def test_upload_rejects_bad_signature(login):
    owner = login("owner@reclaim.example")
    err(owner.post("/api/v1/uploads", files={"file": ("a.png", b"not a png", "image/png")}),
        415, "FILE_SIGNATURE_MISMATCH")
