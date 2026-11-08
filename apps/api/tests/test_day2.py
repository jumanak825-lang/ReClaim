"""Day 2: async processing via the outbox, extraction providers, matcher ranking, FR-019 backstop."""

import dataclasses
import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import config
from app.db.models import Claim, Report
from app.db.session import transaction
from app.integrations import ai
from app.main import app
from app.services import matcher
from app.workers.outbox import drain

from .test_demo_flow import PNG, data, lost_laptop_body


def settings(monkeypatch, **changes):
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, **changes))


def test_report_is_processing_until_worker_runs(client):
    plain = TestClient(app)  # does not drain the outbox
    plain.post("/api/v1/auth/login", json={"email": "owner@reclaim.example", "password": "reclaim-demo"})
    rep = data(plain.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)
    assert rep["status"] == "processing" and rep["processing_status"] == "processing"
    assert data(plain.get(f"/api/v1/reports/{rep['id']}/matches")) == []
    assert drain() >= 1
    rep = data(plain.get(f"/api/v1/reports/{rep['id']}"))
    assert rep["status"] == "active" and rep["processing_status"] == "completed"
    assert data(plain.get(f"/api/v1/reports/{rep['id']}/matches"))


def test_submit_runs_fallback_extraction_when_not_requested(login):
    owner = login("owner@reclaim.example")
    rep = data(owner.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)
    ex = data(owner.get(f"/api/v1/reports/{rep['id']}/extraction"))
    assert ex["status"] == "completed" and ex["is_fallback"] and ex["provider"] == "deterministic-fallback"
    assert ex["category"]["value"] == "electronics"


def grok_transport(content: dict, captured: list):
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})
    return httpx.MockTransport(handler)


def test_grok_extraction_used_when_configured(login, monkeypatch):
    captured: list = []
    reply = {"category": {"value": "electronics", "confidence": 0.93}, "item_label": {"value": "Laptop", "confidence": 0.9},
             "brand": {"value": None, "confidence": 0.1}, "model": {"value": None, "confidence": 0.0},
             "colour": {"value": "silver", "confidence": 0.88}}
    monkeypatch.setattr(ai, "transport", grok_transport(reply, captured))
    settings(monkeypatch, ai_api_key="test-key", ai_vision_model="grok-test-model")
    owner = login("owner@reclaim.example")
    img = data(owner.post("/api/v1/uploads", files={"file": ("a.png", PNG, "image/png")}), 201)
    rep = data(owner.post("/api/v1/reports/lost", json=lost_laptop_body(as_draft=True) | {"image_ids": [img["id"]]}), 201)
    data(owner.post(f"/api/v1/reports/{rep['id']}/extract"), 202)
    ex = data(owner.get(f"/api/v1/reports/{rep['id']}/extraction"))
    assert ex["provider"] == "xai" and not ex["is_fallback"]
    assert ex["colour"] == {"value": "silver", "confidence": 0.88}
    req = captured[0]
    assert req["model"] == "grok-test-model" and req["response_format"]["type"] == "json_schema"
    assert any(part["type"] == "image_url" for part in req["messages"][1]["content"])  # public image sent


def test_grok_outage_falls_back(login, monkeypatch):
    monkeypatch.setattr(ai, "transport", httpx.MockTransport(lambda r: httpx.Response(503)))
    settings(monkeypatch, ai_api_key="test-key", ai_vision_model="grok-test-model")
    owner = login("owner@reclaim.example")
    rep = data(owner.post("/api/v1/reports/lost", json=lost_laptop_body(as_draft=True)), 201)
    data(owner.post(f"/api/v1/reports/{rep['id']}/extract"), 202)
    ex = data(owner.get(f"/api/v1/reports/{rep['id']}/extraction"))
    assert ex["status"] == "completed" and ex["is_fallback"] and ex["colour"]["value"] == "silver"


def test_grok_rejects_invalid_category(monkeypatch):
    reply = {f: {"value": "spaceship" if f == "category" else None, "confidence": 2} for f in ai.FIELDS}
    monkeypatch.setattr(ai, "transport", grok_transport(reply, []))
    settings(monkeypatch, ai_api_key="k", ai_vision_model="m")
    out = ai.extract(ai.ExtractionInput("Thing", "A thing"))
    assert out.fields["category"] == (None, 1.0)


def test_matcher_ranks_seeded_pair_above_hard_negatives(login):
    owner = login("owner@reclaim.example")
    rep = data(owner.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)
    ms = data(owner.get(f"/api/v1/reports/{rep['id']}/matches"))
    labels = [(m["found_item"]["item_label"], m["found_item"]["approximate_location"]) for m in ms]
    assert labels[0] == ("Laptop", "Terminal 1 Lost Property")
    assert ("Laptop", "Terminal 3 Lost Property") not in labels  # black laptop: below the surface threshold
    assert all(m["matcher_version"] == matcher.MATCHER_VERSION for m in ms)


def test_matcher_handles_missing_data():
    lost = Report(report_type="lost", category="other", item_label="", description="", attributes_public={},
                  location_label="")
    found = Report(report_type="found", category="toy", item_label="", description="", attributes_public={},
                   location_label="", found_at=datetime.now(timezone.utc))
    score, comps, why = matcher.score_pair(lost, found, "")
    assert 0 <= score <= 100 and comps["time"] == 0.5 and comps["attributes"] == 0.5 and isinstance(why, list)


def test_one_approved_owner_enforced_by_database(login):
    owner = login("owner@reclaim.example")
    rep = data(owner.post("/api/v1/reports/lost", json=lost_laptop_body()), 201)
    match = data(owner.get(f"/api/v1/reports/{rep['id']}/matches"))[0]
    claim = data(owner.post(f"/api/v1/matches/{match['id']}/claims", json={"statement": "Mine"}), 201)
    with pytest.raises(IntegrityError):
        with transaction() as s:
            c = s.get(Claim, claim["id"])
            c.status = "approved"
            seeded = s.scalar(select(Claim).where(Claim.id != c.id))
            seeded.found_report_id, seeded.status = c.found_report_id, "approved"


def test_matcher_tolerates_naive_datetimes():
    naive = datetime(2026, 11, 7, 9, 0)
    lost = Report(report_type="lost", category="bag", item_label="Bag", description="Black bag",
                  attributes_public={}, location_label="Gate", lost_at_start=naive, lost_at_end=naive)
    found = Report(report_type="found", category="bag", item_label="Bag", description="Black bag",
                   attributes_public={}, location_label="Gate", found_at=datetime(2026, 11, 7, 10, tzinfo=timezone.utc))
    assert matcher.score_pair(lost, found, "Gate")[1]["time"] == 1.0
