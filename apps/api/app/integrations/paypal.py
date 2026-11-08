"""PayPal REST client: OAuth, Orders v2 and webhook verification (docs/07 §7.2).

Credentials and access tokens stay on the backend and are never logged (CLAUDE.md rule 7).
Every retry-sensitive call sends a PayPal-Request-Id so PayPal deduplicates it.
"""

from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from ..core import config


class PayPalError(Exception):
    """PayPal returned an error we can't act on, or was unreachable. Reconcile later."""


class OrderNotApproved(Exception):
    """The buyer hasn't approved the order (PayPal issue ORDER_NOT_APPROVED)."""


class OrderAlreadyCaptured(Exception):
    """PayPal says the order was captured already (e.g. a retried capture)."""


# ISO 4217 minor-unit exponents that differ from 2. Only USD is used in the demo (docs/11 §1).
_EXPONENT = {"JPY": 0, "KRW": 0, "HUF": 0, "TWD": 0}


def to_value(amount_minor: int, currency: str) -> str:
    exp = _EXPONENT.get(currency, 2)
    return str(amount_minor) if exp == 0 else f"{amount_minor // 10**exp}.{amount_minor % 10**exp:0{exp}d}"


def to_minor(value: str, currency: str) -> int | None:
    try:
        d = Decimal(value) * (10 ** _EXPONENT.get(currency, 2))
    except (InvalidOperation, TypeError):
        return None
    return int(d) if d == d.to_integral_value() else None

# Tests replace this to avoid network calls.
transport: httpx.BaseTransport | None = None
_token: tuple[str, float] | None = None  # (access_token, expires_at)

SIGNATURE_HEADERS = {
    "auth_algo": "paypal-auth-algo",
    "cert_url": "paypal-cert-url",
    "transmission_id": "paypal-transmission-id",
    "transmission_sig": "paypal-transmission-sig",
    "transmission_time": "paypal-transmission-time",
}


def _client() -> httpx.Client:
    return httpx.Client(base_url=config.settings.paypal_base_url, timeout=15, transport=transport)


def access_token() -> str:
    global _token
    if _token and _token[1] > time.time() + 60:
        return _token[0]
    s = config.settings
    try:
        with _client() as c:
            r = c.post("/v1/oauth2/token", data={"grant_type": "client_credentials"},
                       auth=(s.paypal_client_id, s.paypal_client_secret))
    except httpx.HTTPError as exc:
        raise PayPalError(f"oauth network error: {type(exc).__name__}") from exc
    if r.status_code != 200:
        raise PayPalError(f"oauth HTTP {r.status_code}")  # body may echo request details; not logged
    body = r.json()
    _token = (body["access_token"], time.time() + int(body.get("expires_in", 300)))
    return _token[0]


def reset_token_cache() -> None:
    global _token
    _token = None


def _issue(r: httpx.Response) -> str:
    try:
        details = r.json().get("details") or []
        return str(details[0].get("issue", "")) if details else ""
    except ValueError:
        return ""


def _call(method: str, path: str, *, request_id: str | None = None, json: Any = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token()}", "Prefer": "return=representation"}
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    try:
        with _client() as c:
            r = c.request(method, path, json=json, headers=headers)
    except httpx.HTTPError as exc:
        raise PayPalError(f"network error: {type(exc).__name__}") from exc
    if r.status_code == 422:
        issue = _issue(r)
        if issue == "ORDER_NOT_APPROVED":
            raise OrderNotApproved()
        if issue == "ORDER_ALREADY_CAPTURED":
            raise OrderAlreadyCaptured()
        raise PayPalError(f"HTTP 422 {issue}".strip())
    if r.status_code >= 300:
        raise PayPalError(f"HTTP {r.status_code} {_issue(r)}".strip())
    return r.json()


def create_order(*, amount_minor: int, currency: str, reference_id: str, custom_id: str, request_id: str,
                 return_url: str, cancel_url: str) -> dict[str, Any]:
    """Orders v2 create (intent CAPTURE). Amount always comes from the stored quote."""
    return _call("POST", "/v2/checkout/orders", request_id=request_id, json={
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": reference_id,
            "custom_id": custom_id,
            "description": "Reclaim item delivery fee",
            "amount": {"currency_code": currency, "value": to_value(amount_minor, currency)},
        }],
        "payment_source": {"paypal": {"experience_context": {
            "brand_name": "Reclaim", "user_action": "PAY_NOW", "shipping_preference": "NO_SHIPPING",
            "return_url": return_url, "cancel_url": cancel_url,
        }}},
    })


def approval_link(order: dict[str, Any]) -> str | None:
    for link in order.get("links") or []:
        if link.get("rel") in {"payer-action", "approve"}:
            return link.get("href")
    return None


def capture_order(order_id: str, request_id: str) -> dict[str, Any]:
    return _call("POST", f"/v2/checkout/orders/{order_id}/capture", request_id=request_id, json={})


def get_order(order_id: str) -> dict[str, Any]:
    return _call("GET", f"/v2/checkout/orders/{order_id}")


def first_capture(order: dict[str, Any]) -> dict[str, Any] | None:
    for unit in order.get("purchase_units") or []:
        captures = (unit.get("payments") or {}).get("captures") or []
        if captures:
            return captures[0]
    return None


def verify_webhook(headers: dict[str, str], event: dict[str, Any]) -> bool:
    """True only if PayPal confirms the signature for our configured webhook id."""
    lower = {k.lower(): v for k, v in headers.items()}
    if any(h not in lower for h in SIGNATURE_HEADERS.values()):
        return False
    payload = {k: lower[h] for k, h in SIGNATURE_HEADERS.items()}
    payload["webhook_id"] = config.settings.paypal_webhook_id
    payload["webhook_event"] = event
    with _client() as c:
        r = c.post("/v1/notifications/verify-webhook-signature", json=payload,
                   headers={"Authorization": f"Bearer {access_token()}"})
    if r.status_code != 200:
        return False
    return r.json().get("verification_status") == "SUCCESS"
