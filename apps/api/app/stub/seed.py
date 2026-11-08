"""Load apps/api/seed/demo_seed.json into the in-memory store."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from .models import Location, Membership, Organisation, Report, User, now
from .services import create_claim, hash_password, run_matching
from .store import db

SEED_FILE = Path(__file__).resolve().parents[2] / "seed" / "demo_seed.json"


def load_seed(path: Path = SEED_FILE) -> None:
    db.clear()
    data = json.loads(path.read_text(encoding="utf-8"))
    t0 = now()
    pw_hash = hash_password(data["password"])
    users: dict[str, User] = {}
    for u in data["users"]:
        user = User(email=u["email"].lower(), password_hash=pw_hash, display_name=u["display_name"])
        users[u["key"]] = db.users[user.id] = user
        db.demo_accounts.append({"email": user.email, "password": data["password"],
                                 "display_name": user.display_name, "persona": u.get("persona", "")})

    orgs: dict[str, Organisation] = {}
    locs: dict[str, Location] = {}
    for o in data["organisations"]:
        org = Organisation(o["name"], o["slug"], o["type"], o.get("description"))
        orgs[o["key"]] = db.organisations[org.id] = org
        for lo in o["locations"]:
            loc = Location(organisation_id=org.id, name=lo["name"], timezone=lo["timezone"],
                           country_code=lo["country_code"], address_public=lo.get("address_public"),
                           latitude=lo.get("latitude"), longitude=lo.get("longitude"),
                           opening_hours=lo.get("opening_hours"),
                           collection_instructions=lo.get("collection_instructions"))
            locs[lo["key"]] = db.locations[loc.id] = loc

    for m in data["memberships"]:
        db.memberships.append(Membership(orgs[m["organisation"]].id, users[m["user"]].id, m["role"],
                                         [locs[k].id for k in m.get("locations", [])]))

    reports: dict[str, Report] = {}
    for f in data["found_reports"]:
        org, loc = orgs.get(f.get("organisation", "")), locs.get(f.get("location", ""))
        creator = users[f.get("created_by") or f["reporter"]]
        r = Report(
            report_type="found", category=f["category"], item_label=f["item_label"],
            description=f["description"], brand=f.get("brand"),
            owner_user_id=None if org else creator.id, created_by_user_id=creator.id,
            organisation_id=org.id if org else None, location_id=loc.id if loc else None,
            found_at=t0 - timedelta(hours=f["found_hours_ago"]),
            location_label=f"{loc.name}, {org.name}" if loc and org else f["found_location"],
            latitude=loc.latitude if loc else None, longitude=loc.longitude if loc else None,
            custody_status=f["custody"], status="active",
            attributes_public=f.get("attributes_public", {}), attributes_private=f.get("attributes_private", {}),
            storage_reference=f.get("storage_reference"), is_seed=True,
        )
        r.created_at = r.updated_at = r.found_at  # type: ignore[assignment]
        reports[f["key"]] = db.reports[r.id] = r

    for lr in data["lost_reports"]:
        owner = users[lr["owner"]]
        r = Report(
            report_type="lost", category=lr["category"], item_label=lr["item_label"],
            description=lr["description"], brand=lr.get("brand"),
            owner_user_id=owner.id, created_by_user_id=owner.id,
            lost_at_start=t0 - timedelta(hours=lr["lost_hours_ago_start"]),
            lost_at_end=t0 - timedelta(hours=lr["lost_hours_ago_end"]),
            location_label=lr["last_location"], status="active",
            attributes_public=lr.get("attributes_public", {}), attributes_private=lr.get("attributes_private", {}),
            is_seed=True,
        )
        r.created_at = r.updated_at = r.lost_at_end  # type: ignore[assignment]
        reports[lr["key"]] = db.reports[r.id] = r
        run_matching(r)

    for c in data.get("claims", []):
        lost, found = reports[c["lost"]], reports[c["found"]]
        m = next((m for m in db.matches.values()
                  if m.lost_report_id == lost.id and m.found_report_id == found.id), None)
        if not m:
            raise RuntimeError(f"Seed claim {c['lost']}->{c['found']} has no match; adjust the seed content.")
        body = SimpleNamespace(
            statement=c["statement"],
            answers=[SimpleNamespace(question_id=k, answer=v) for k, v in c.get("answers", {}).items()],
            evidence_image_ids=[],
        )
        create_claim(users[c["claimant"]], m.id, body, at=t0 - timedelta(hours=2))

    # Seed noise shouldn't flood the demo: mark seed-time notifications as read.
    for n in db.notifications:
        n.read_at = t0
