"""Side effects recorded in the same transaction as the state change:
in-app notifications, audit log entries and outbox events."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from ..core.envelope import request_id_var
from ..db.models import (
    AuditLog,
    LocationMembership,
    Notification,
    OrganisationMembership,
    OutboxEvent,
    User,
    now,
)
from ..db.session import db
from .access import REVIEW_ROLES  # noqa: F401  (re-exported for callers)

ALL_STAFF_ROLES = {"staff", "reviewer", "manager", "admin"}


def notify(user_id: UUID | None, type_: str, title: str, body: str, entity_type: str | None,
           entity_id: UUID | None) -> None:
    if user_id:
        db().add(Notification(user_id=user_id, type=type_, title=title, body_safe=body,
                              related_entity_type=entity_type, related_entity_id=entity_id))


def notify_org(org_id: UUID | None, location_id: UUID | None, roles: set[str], type_: str, title: str, body: str,
               entity_type: str, entity_id: UUID) -> None:
    """Notify org members with one of `roles` whose location scope covers `location_id`."""
    if org_id is None:
        return
    s = db()
    members = s.scalars(select(OrganisationMembership).where(
        OrganisationMembership.organisation_id == org_id, OrganisationMembership.role.in_(roles))).all()
    for m in members:
        if location_id is not None:
            scoped = set(s.scalars(select(LocationMembership.location_id).where(
                LocationMembership.user_id == m.user_id)).all())
            if scoped and location_id not in scoped:
                continue
        notify(m.user_id, type_, title, body, entity_type, entity_id)


def audit(actor: User | None, org_id: UUID | None, action: str, entity_type: str, entity_id: UUID,
          reason: str | None = None, before: dict[str, Any] | None = None, after: dict[str, Any] | None = None):
    """Append an audit record. `before`/`after` must already be redacted (no private values)."""
    db().add(AuditLog(actor_user_id=actor.id if actor else None, organisation_id=org_id, action=action,
                      entity_type=entity_type, entity_id=entity_id, reason=reason,
                      before_redacted=before or {}, after_redacted=after or {},
                      request_id=request_id_var.get()))


def emit(event_type: str, aggregate_type: str, aggregate_id: UUID, org_id: UUID | None,
         payload: dict[str, Any], delay_seconds: float = 0) -> OutboxEvent:
    """Queue a background job or integration event; the worker delivers it after commit."""
    ev = OutboxEvent(event_type=event_type, aggregate_type=aggregate_type, aggregate_id=aggregate_id,
                     organisation_id=org_id, payload=payload,
                     next_attempt_at=now() + timedelta(seconds=delay_seconds))
    db().add(ev)
    return ev


def emit_detached(event_type: str, aggregate_type: str, aggregate_id: UUID, org_id: UUID | None,
                  payload: dict[str, Any], delay_seconds: float = 0) -> None:
    """Queue a job in its own transaction, so it survives the current request rolling back.

    Used for reconciliation after an uncertain provider outcome, where the request itself fails.
    """
    from ..db.session import transaction

    with transaction():
        emit(event_type, aggregate_type, aggregate_id, org_id, payload, delay_seconds)
