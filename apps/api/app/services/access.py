"""Organisation and location scope checks (FR-017, FR-029, docs/08 §8.11).

A user's role for a record comes from their organisation membership. If the user has
any location_memberships rows in that organisation, the role applies to those
locations only; otherwise it covers every location.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from ..core.errors import ApiError, not_found
from ..db.models import Location, LocationMembership, Organisation, OrganisationMembership, Report, User
from ..db.session import db

REVIEW_ROLES = {"reviewer", "manager", "admin"}
ADMIN_ROLES = {"manager", "admin"}


def memberships_of(user: User) -> list[OrganisationMembership]:
    return list(db().scalars(select(OrganisationMembership).where(OrganisationMembership.user_id == user.id)))


def scoped_location_ids(user: User, org_id: UUID) -> list[UUID]:
    """Location ids the user is limited to within `org_id`. Empty = all locations."""
    return list(db().scalars(
        select(LocationMembership.location_id)
        .join(Location, Location.id == LocationMembership.location_id)
        .where(LocationMembership.user_id == user.id, Location.organisation_id == org_id)))


def role_in(user: User, org_id: UUID | None) -> str | None:
    """Org-level role, ignoring location scope. Use only for org-wide checks."""
    if org_id is None:
        return None
    return db().scalar(select(OrganisationMembership.role).where(
        OrganisationMembership.user_id == user.id, OrganisationMembership.organisation_id == org_id))


def scoped_role(user: User, org_id: UUID | None, location_id: UUID | None) -> str | None:
    role = role_in(user, org_id)
    if role is None:
        return None
    allowed = scoped_location_ids(user, org_id)  # type: ignore[arg-type]
    if allowed and location_id is not None and location_id not in allowed:
        return None
    return role


def report_role(user: User, r: Report) -> str | None:
    return scoped_role(user, r.organisation_id, r.location_id)


def require_member(user: User, org_id: UUID, roles: set[str] | None = None) -> str:
    if db().get(Organisation, org_id) is None:
        raise not_found("organisation")
    role = role_in(user, org_id)
    if role is None:
        raise ApiError(403, "NOT_A_MEMBER", "You are not a member of this organisation.")
    if roles and role not in roles:
        raise ApiError(403, "INSUFFICIENT_ROLE", "Your role does not allow this action.")
    return role
