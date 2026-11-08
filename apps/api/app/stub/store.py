"""Process-local in-memory state for the STUB backend.

Data is lost on restart and reseeded on start / POST /dev/reset.
Not safe for multiple workers: run uvicorn with a single process.
"""

from __future__ import annotations

from uuid import UUID

from .models import (
    AuditLog,
    Claim,
    Image,
    Location,
    Match,
    Membership,
    Notification,
    Organisation,
    OutboxEvent,
    Payment,
    Recovery,
    Report,
    Session,
    User,
)


class Store:
    def __init__(self) -> None:
        self.clear()

    def clear(self) -> None:
        self.users: dict[UUID, User] = {}
        self.sessions: dict[str, Session] = {}
        self.organisations: dict[UUID, Organisation] = {}
        self.locations: dict[UUID, Location] = {}
        self.memberships: list[Membership] = []
        self.images: dict[UUID, Image] = {}
        self.reports: dict[UUID, Report] = {}
        self.matches: dict[UUID, Match] = {}
        self.claims: dict[UUID, Claim] = {}
        self.recoveries: dict[UUID, Recovery] = {}
        self.payments: dict[UUID, Payment] = {}
        self.notifications: list[Notification] = []
        self.audit_logs: list[AuditLog] = []
        self.outbox: list[OutboxEvent] = []
        self.demo_accounts: list[dict[str, str]] = []

    def user_by_email(self, email: str) -> User | None:
        email = email.strip().lower()
        return next((u for u in self.users.values() if u.email == email), None)


db = Store()
