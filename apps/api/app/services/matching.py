"""Candidate matching and match access (docs/06). Scores are advisory, never proof of ownership."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select

from ..core.errors import ApiError, not_found
from ..db.models import Claim, Location, Match, Organisation, Report, User
from ..db.session import db
from . import matcher
from .access import report_role
from .events import REVIEW_ROLES, emit, notify, notify_org
from .reports import ACTIVE_CLAIM, get_report, run_extraction

VISIBLE = {"active", "resolved"}


def process_report(report_id: UUID, rematch_only: bool = False) -> None:
    """Worker job `report.process`: extraction (if not done), matching, then activate."""
    r = db().get(Report, report_id)
    if r is None or r.status in {"draft", "withdrawn"}:
        return
    if not rematch_only and r.extraction_status == "not_started":
        run_extraction(r)
    run_matching(r)
    if r.status == "processing":
        r.status = "active"


def _found_location_text(found: Report) -> str:
    if found.location_id:
        loc = db().get(Location, found.location_id)
        org = db().get(Organisation, loc.organisation_id) if loc else None
        if loc and org:
            return f"{loc.name}, {org.name}"
    return found.location_label


def run_matching(r: Report) -> None:
    other_type = "found" if r.report_type == "lost" else "lost"
    # Candidate retrieval: every open report of the other type. Fine at demo scale; filter by
    # category/time window/geography before this grows.
    others = db().scalars(select(Report).where(
        Report.report_type == other_type, Report.status.in_(["processing", "active"]), Report.id != r.id))
    r.matching_version = matcher.MATCHER_VERSION
    for o in others:
        lost, found = (r, o) if r.report_type == "lost" else (o, r)
        if lost.owner_user_id and lost.owner_user_id == found.owner_user_id:
            continue
        score, comps, why = matcher.score_pair(lost, found, _found_location_text(found))
        existing = db().scalar(select(Match).where(
            Match.lost_report_id == lost.id, Match.found_report_id == found.id,
            Match.matcher_version == matcher.MATCHER_VERSION))
        if existing:
            existing.score, existing.score_components, existing.explanation_public = score, comps, why
            continue
        if score < matcher.SURFACE_THRESHOLD:
            continue
        m = Match(lost_report_id=lost.id, found_report_id=found.id, score=score, score_components=comps,
                  explanation_public=why, matcher_version=matcher.MATCHER_VERSION)
        db().add(m)
        db().flush()
        notify(lost.owner_user_id, "match.found", "Potential match found",
               f"A found {found.item_label.lower()} may match your report. Review it privately.", "match", m.id)
        notify_org(found.organisation_id, found.location_id, REVIEW_ROLES, "match.found", "New candidate match",
                   f"A lost report may match found item: {found.item_label}.", "match", m.id)
        if score >= matcher.STRONG_THRESHOLD and found.organisation_id:
            emit("match.high_priority", "match", m.id, found.organisation_id,
                 {"match_id": str(m.id), "score": score, "label": matcher.label_for(score),
                  "item_label": found.item_label, "category": found.category})


def match_visible(m: Match) -> bool:
    lost, found = db().get(Report, m.lost_report_id), db().get(Report, m.found_report_id)
    return bool(lost and found) and lost.status in VISIBLE and found.status in VISIBLE


def match_access(user: User, m: Match) -> str | None:
    lost, found = db().get(Report, m.lost_report_id), db().get(Report, m.found_report_id)
    if lost.owner_user_id == user.id:
        return "owner"
    if report_role(user, found):
        return "custodian"
    if user.id in (found.owner_user_id, found.created_by_user_id):
        return "finder"
    return None


def get_match(user: User, match_id: UUID) -> Match:
    m = db().get(Match, match_id)
    if not m or not match_access(user, m) or not match_visible(m):
        raise not_found("match")
    return m


def matches_for_report(user: User, report_id: UUID) -> list[Match]:
    r, access = get_report(user, report_id)
    if access == "public":
        return []
    ms = db().scalars(select(Match).where(or_(Match.lost_report_id == r.id, Match.found_report_id == r.id))
                      .order_by(Match.score.desc()))
    return [m for m in ms if match_visible(m) and not (m.status == "dismissed" and access == "owner")]


def my_matches(user: User) -> list[Match]:
    ms = db().scalars(select(Match).join(Report, Report.id == Match.lost_report_id)
                      .where(Report.owner_user_id == user.id, Match.status != "dismissed")
                      .order_by(Match.score.desc()))
    return [m for m in ms if match_visible(m)]


def dismiss_match(user: User, match_id: UUID) -> Match:
    m = get_match(user, match_id)
    if match_access(user, m) != "owner":
        raise ApiError(403, "FORBIDDEN", "Only the owner of the lost report can dismiss a match.")
    if m.status != "candidate":
        raise ApiError(409, "MATCH_NOT_DISMISSABLE", "This match has an active claim.")
    m.status = "dismissed"
    return m


def active_claim_for(m: Match) -> Claim | None:
    return db().scalar(select(Claim).where(Claim.match_id == m.id, Claim.status.in_(ACTIVE_CLAIM)))


QUESTIONS = [
    ("q_marks", "Describe any distinctive marks, stickers, damage or engravings on the item."),
    ("q_contents", "What was inside, attached to or stored with the item (case, accessories, contents)?"),
    ("q_when_where", "When and where exactly do you think you lost it?"),
    ("q_other", "Is there anything else only the owner would know about this item?"),
]


def verification_questions(user: User, match_id: UUID) -> list[tuple[str, str]]:
    m = get_match(user, match_id)
    if match_access(user, m) != "owner":
        raise ApiError(403, "FORBIDDEN", "Only the owner of the lost report can claim this item.")
    return QUESTIONS
