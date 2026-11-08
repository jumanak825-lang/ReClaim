"""In-process fake of the PayPal REST endpoints Reclaim uses (OAuth, Orders v2, webhook verification).

Behaviour mirrors the documented API closely enough for our flows: PayPal-Request-Id makes create
and capture idempotent; capturing an unapproved order returns 422 ORDER_NOT_APPROVED; capturing a
completed order returns 422 ORDER_ALREADY_CAPTURED.
"""

from __future__ import annotations

import itertools
import json

import httpx


class FakePayPal:
    def __init__(self):
        self.orders: dict[str, dict] = {}
        self.by_request_id: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []
        self.capture_override: dict | None = None  # e.g. a different amount, to test mismatches
        self.fail_next: int | None = None  # HTTP status for the next orders call
        self._ids = itertools.count(1)

    # test helpers
    def approve(self, order_id: str) -> None:
        self.orders[order_id]["status"] = "APPROVED"

    def complete(self, order_id: str) -> None:
        """Capture on PayPal's side without telling Reclaim (a lost capture response)."""
        order = self.orders[order_id]
        order["status"] = "COMPLETED"
        order["purchase_units"][0]["payments"] = {"captures": [
            {"id": f"CAP-{order_id}", "status": "COMPLETED", "amount": order["purchase_units"][0]["amount"]}]}

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def count(self, method: str, prefix: str) -> int:
        return sum(1 for m, p in self.calls if m == method and p.startswith(prefix))

    def handle(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        self.calls.append((method, path))
        if path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "fake-token", "expires_in": 3600})
        if request.headers.get("Authorization") != "Bearer fake-token":
            return httpx.Response(401)
        if path == "/v1/notifications/verify-webhook-signature":
            body = json.loads(request.content)
            good = body["transmission_sig"] == "good-signature" and body["webhook_id"] == "WH-TEST"
            return httpx.Response(200, json={"verification_status": "SUCCESS" if good else "FAILURE"})
        if path.startswith("/v2/checkout/orders") and self.fail_next:
            status, self.fail_next = self.fail_next, None
            return httpx.Response(status, json={"name": "INTERNAL_SERVICE_ERROR"})
        rid = request.headers.get("PayPal-Request-Id")
        if rid and rid in self.by_request_id:
            return httpx.Response(200, json=self.by_request_id[rid])
        if path == "/v2/checkout/orders" and method == "POST":
            body = json.loads(request.content)
            oid = f"FAKE{next(self._ids):06d}"
            order = {"id": oid, "status": "PAYER_ACTION_REQUIRED", "purchase_units": body["purchase_units"],
                     "request": body,
                     "links": [{"rel": "payer-action", "href": f"https://www.sandbox.paypal.com/checkoutnow?token={oid}"}]}
            self.orders[oid] = order
            self.by_request_id[rid] = order
            return httpx.Response(201, json=order)
        if path.endswith("/capture") and method == "POST":
            oid = path.split("/")[-2]
            order = self.orders.get(oid)
            if order is None:
                return httpx.Response(404)
            if order["status"] == "COMPLETED":
                return httpx.Response(422, json={"details": [{"issue": "ORDER_ALREADY_CAPTURED"}]})
            if order["status"] != "APPROVED":
                return httpx.Response(422, json={"details": [{"issue": "ORDER_NOT_APPROVED"}]})
            amount = order["purchase_units"][0]["amount"]
            capture = self.capture_override or {"id": f"CAP-{oid}", "status": "COMPLETED", "amount": amount}
            order["status"] = "COMPLETED"
            order["purchase_units"][0]["payments"] = {"captures": [capture]}
            self.by_request_id[rid] = order
            return httpx.Response(201, json=order)
        if path.startswith("/v2/checkout/orders/") and method == "GET":
            order = self.orders.get(path.split("/")[-1])
            return httpx.Response(200, json=order) if order else httpx.Response(404)
        return httpx.Response(404)
