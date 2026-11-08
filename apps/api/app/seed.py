"""Demo seed loader and reset script (docs/11: content in seed/demo_seed.json, loader is backend).

    python -m app.seed            # wipe every table and uploaded file, then load the seed

Destroys all data in DATABASE_URL. Refuses to run against a database whose name doesn't
contain "reclaim" as a guard against pointing it at the wrong server.
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import text
from sqlalchemy.engine import make_url

from .core import config
from .db.models import (
    Base,
    Location,
    LocationMembership,
    Match,
    Organisation,
    OrganisationMembership,
    Report,
    User,
    now,
)
from .db.session import db, transaction
from .integrations.storage import storage
from .services import matching
from .services.auth import hash_password
from .services.claims import create_claim

SEED_FILE = config.API_ROOT / "seed" / "demo_seed.json"


def wipe() -> None:
    name = make_url(config.settings.database_url).database or ""
    if "reclaim" not in name:
        raise RuntimeError(f"Refusing to wipe database {name!r}: name must contain 'reclaim'.")
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    db().execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    storage().clear_all()


def load_seed(path: Path = SEED_FILE) -> list[dict[str, str]]:
    """Wipe and load. Must run inside transaction(). Returns the demo accounts."""
    wipe()
    data = json.loads(path.read_text(encoding="utf-8"))
    s = db()
    t0 = now()
    pw_hash = hash_password(data["password"])
    users: dict[str, User] = {}
    for u in data["users"]:
        users[u["key"]] = User(email=u["email"].lower(), password_hash=pw_hash, display_name=u["display_name"])
        s.add(users[u["key"]])

    orgs: dict[str, Organisation] = {}
    locs: dict[str, Location] = {}
    for o in data["organisations"]:
        orgs[o["key"]] = org = Organisation(name=o["name"], slug=o["slug"], organisation_type=o["type"],
                                            description=o.get("description"))
        s.add(org)
        s.flush()
        for lo in o["locations"]:
            locs[lo["key"]] = Location(
                organisation_id=org.id, name=lo["name"], timezone=lo["timezone"], country_code=lo["country_code"],
                address_public=lo.get("address_public"), latitude=lo.get("latitude"),
                longitude=lo.get("longitude"), opening_hours=lo.get("opening_hours"),
                collection_instructions=lo.get("collection_instructions"))
            s.add(locs[lo["key"]])
    s.flush()

    for m in data["memberships"]:
        s.add(OrganisationMembership(organisation_id=orgs[m["organisation"]].id, user_id=users[m["user"]].id,
                                     role=m["role"]))
        for lk in m.get("locations", []):
            s.add(LocationMembership(location_id=locs[lk].id, user_id=users[m["user"]].id))

    reports: dict[str, Report] = {}
    for f in data["found_reports"]:
        org, loc = orgs.get(f.get("organisation", "")), locs.get(f.get("location", ""))
        creator = users[f.get("created_by") or f["reporter"]]
        found_at = t0 - timedelta(hours=f["found_hours_ago"])
        reports[f["key"]] = r = Report(
            report_type="found", category=f["category"], item_label=f["item_label"],
            description=f["description"], brand=f.get("brand"),
            owner_user_id=None if org else creator.id, created_by_user_id=creator.id,
            organisation_id=org.id if org else None, location_id=loc.id if loc else None, found_at=found_at,
            location_label=f"{loc.name}, {org.name}" if loc and org else f["found_location"],
            latitude=loc.latitude if loc else None, longitude=loc.longitude if loc else None,
            custody_status=f["custody"], status="active", image_ids=[],
            attributes_public=f.get("attributes_public", {}), attributes_private=f.get("attributes_private", {}),
            storage_reference=f.get("storage_reference"), is_seed=True, created_at=found_at, updated_at=found_at)
        s.add(r)

    for lr in data["lost_reports"]:
        end = t0 - timedelta(hours=lr["lost_hours_ago_end"])
        reports[lr["key"]] = r = Report(
            report_type="lost", category=lr["category"], item_label=lr["item_label"],
            description=lr["description"], brand=lr.get("brand"),
            owner_user_id=users[lr["owner"]].id, created_by_user_id=users[lr["owner"]].id,
            lost_at_start=t0 - timedelta(hours=lr["lost_hours_ago_start"]), lost_at_end=end,
            location_label=lr["last_location"], status="active", image_ids=[],
            attributes_public=lr.get("attributes_public", {}), attributes_private=lr.get("attributes_private", {}),
            is_seed=True, created_at=end, updated_at=end)
        s.add(r)
    s.flush()
    for r in reports.values():
        if r.report_type == "lost":
            matching.run_matching(r)
    s.flush()

    for c in data.get("claims", []):
        lost, found = reports[c["lost"]], reports[c["found"]]
        m = s.query(Match).filter_by(lost_report_id=lost.id, found_report_id=found.id).one_or_none()
        if not m:
            raise RuntimeError(f"Seed claim {c['lost']}->{c['found']} has no match; adjust the seed content.")
        body = SimpleNamespace(
            statement=c["statement"], evidence_image_ids=[],
            answers=[SimpleNamespace(question_id=k, answer=v) for k, v in c.get("answers", {}).items()])
        create_claim(users[c["claimant"]], m.id, body, at=t0 - timedelta(hours=2))

    # Seed-time notifications and integration events would flood the demo: mark them done.
    s.flush()
    s.execute(text("UPDATE notifications SET read_at = :t"), {"t": t0})
    s.execute(text("UPDATE outbox_events SET delivery_status = 'skipped', last_error = 'seed'"))
    return demo_accounts(data)


def demo_accounts(data: dict | None = None) -> list[dict[str, str]]:
    data = data or json.loads(SEED_FILE.read_text(encoding="utf-8"))
    return [{"email": u["email"], "password": data["password"], "display_name": u["display_name"],
             "persona": u.get("persona", "")} for u in data["users"]]


def is_empty() -> bool:
    return db().scalar(text("SELECT NOT EXISTS (SELECT 1 FROM organisations)"))


def main() -> None:
    with transaction():
        accounts = load_seed()
    print(f"Seeded {len(accounts)} demo accounts (password: {accounts[0]['password']}).")


if __name__ == "__main__":
    sys.exit(main())
