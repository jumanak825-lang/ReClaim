"""Outbox worker (docs/03 §3.7): persistent jobs with retries and a dead-letter state.

Each event is claimed with SELECT ... FOR UPDATE SKIP LOCKED, so several workers (or the
embedded API worker plus `python -m app.workers`) never process the same row twice.
Handler work runs in a savepoint: if it fails, its partial writes roll back but the
attempt count and error are still recorded.

delivery_status: pending | failed (retrying) -> delivered | skipped | dead
"""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from ..core import config
from ..core.envelope import request_id_var
from ..db.models import OutboxEvent, Report, now
from ..db.session import db, transaction
from ..integrations import zapier
from ..services import matching, payments, recoveries, reports

log = logging.getLogger("reclaim.worker")


class Skip(Exception):
    """Handler decided there is nothing to deliver (e.g. Zapier not configured)."""


def _handle(ev: OutboxEvent) -> None:
    if ev.event_type == "report.process":
        matching.process_report(UUID(ev.payload["report_id"]), bool(ev.payload.get("rematch_only")))
        return
    if ev.event_type == "report.extract":
        r = db().get(Report, UUID(ev.payload["report_id"]))
        if r is not None:
            reports.run_extraction(r)
        return
    if ev.event_type == "payment.reconcile":
        payments.reconcile(UUID(ev.payload["payment_id"]))
        return
    if ev.event_type == "recovery.courier_advance":
        recoveries.courier_tick(UUID(ev.payload["recovery_id"]))
        return
    if ev.event_type in zapier.SUBSCRIBED_EVENTS:
        s = config.settings
        if not (s.zapier_webhook_url and s.zapier_webhook_secret):
            raise Skip("Zapier not configured")
        zapier.deliver(zapier.envelope(str(ev.id), ev.event_type, ev.created_at.isoformat(),
                                       str(ev.organisation_id) if ev.organisation_id else None, ev.payload))
        return
    raise Skip("no subscriber")


def backoff(attempt: int) -> timedelta:
    return timedelta(seconds=min(300, 2 ** attempt))


def process_one() -> bool:
    """Process the next due event. Returns False when nothing is due."""
    token = request_id_var.set("worker")
    try:
        with transaction() as s:
            ev = s.scalar(
                select(OutboxEvent)
                .where(OutboxEvent.delivery_status.in_(["pending", "failed"]), OutboxEvent.next_attempt_at <= now())
                .order_by(OutboxEvent.next_attempt_at, OutboxEvent.created_at)
                .limit(1)
                .with_for_update(skip_locked=True))
            if ev is None:
                return False
            ev.attempt_count += 1
            try:
                with s.begin_nested():
                    _handle(ev)
                ev.delivery_status, ev.delivered_at, ev.last_error = "delivered", now(), None
            except Skip as exc:
                ev.delivery_status, ev.last_error = "skipped", str(exc)
            except Exception as exc:  # retry with backoff, then dead-letter
                ev.last_error = f"{type(exc).__name__}: {exc}"[:500]
                if ev.attempt_count >= config.settings.worker_max_attempts:
                    ev.delivery_status = "dead"
                    log.error("outbox event dead id=%s type=%s error=%s", ev.id, ev.event_type, ev.last_error)
                else:
                    ev.delivery_status = "failed"
                    ev.next_attempt_at = now() + backoff(ev.attempt_count)
                    log.warning("outbox event failed id=%s type=%s attempt=%s", ev.id, ev.event_type,
                                ev.attempt_count)
            return True
    finally:
        request_id_var.reset(token)


def drain(max_events: int = 500) -> int:
    """Process due events until none are left (or the cap is hit). Returns how many ran."""
    n = 0
    while n < max_events and process_one():
        n += 1
    return n
