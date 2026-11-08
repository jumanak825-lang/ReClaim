from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update

from ..core.errors import not_found
from ..db.models import Notification, User, now
from ..db.session import db


def my_notifications(user: User, unread_only: bool) -> list[Notification]:
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    return list(db().scalars(q.order_by(Notification.created_at.desc(), Notification.id)))


def unread_count(user: User) -> int:
    return db().scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None))) or 0


def mark_read(user: User, nid: UUID | None) -> None:
    if nid is not None:
        n = db().get(Notification, nid)
        if not n or n.user_id != user.id:
            raise not_found("notification")
        if n.read_at is None:
            n.read_at = now()
        return
    db().execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
                 .values(read_at=now()))
