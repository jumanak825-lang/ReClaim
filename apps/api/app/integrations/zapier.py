"""Signed outbound delivery to a Zapier catch hook (docs/07 §7.3).

Zapier never changes Reclaim state: a failed delivery only marks the outbox row for retry.
Signature: X-Reclaim-Signature = "v1=" + hex(HMAC-SHA256(secret, f"{timestamp}.{raw_body}")).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from ..core import config

# Events the two hackathon Zaps subscribe to (docs/11 §2), plus the test event.
SUBSCRIBED_EVENTS = ["match.high_priority", "claim.created", "integration.test"]

# Tests replace this to avoid network calls.
transport: httpx.BaseTransport | None = None


class DeliveryError(Exception):
    pass


def sign(secret: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"v1={mac}"


REPLAY_TOLERANCE_SECONDS = 300


def verify(secret: str, timestamp: str, body: bytes, signature: str, *, now: float | None = None,
           tolerance: int = REPLAY_TOLERANCE_SECONDS) -> bool:
    """Receiver-side check (replay protection, docs/07 §7.3): valid HMAC and a fresh timestamp.

    Receivers should also drop repeated X-Reclaim-Event-Id values: retries reuse the same id.
    """
    try:
        age = abs((time.time() if now is None else now) - int(timestamp))
    except ValueError:
        return False
    return age <= tolerance and hmac.compare_digest(sign(secret, timestamp, body), signature)


def envelope(event_id: str, event_type: str, occurred_at: str, organisation_id: str | None,
             data: dict[str, Any]) -> dict[str, Any]:
    return {"event_id": event_id, "event_type": event_type, "occurred_at": occurred_at,
            "organisation_id": organisation_id, "data": data}


def deliver(env: dict[str, Any]) -> None:
    """POST the signed event to every hook configured for its type.

    If any hook fails the whole event is retried, so a hook can see the same event id twice;
    receivers dedupe on X-Reclaim-Event-Id. Errors never include the URL (it is a secret).
    """
    s = config.settings
    urls = s.zapier_urls_for(env["event_type"])
    if not urls:
        raise DeliveryError("Zapier is not configured")
    body = json.dumps(env, separators=(",", ":"), sort_keys=True).encode()
    ts = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Reclaim-Event-Id": env["event_id"],
        "X-Reclaim-Timestamp": ts,
        "X-Reclaim-Signature": sign(s.zapier_webhook_secret, ts, body),
    }
    with httpx.Client(timeout=10, transport=transport) as c:
        for i, url in enumerate(urls, 1):
            try:
                r = c.post(url, content=body, headers=headers)
            except httpx.HTTPError as exc:
                raise DeliveryError(f"hook {i}/{len(urls)}: network error: {type(exc).__name__}") from exc
            if r.status_code >= 300:
                raise DeliveryError(f"hook {i}/{len(urls)}: HTTP {r.status_code}")
