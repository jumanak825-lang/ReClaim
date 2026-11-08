"""Deterministic matcher (no embeddings for the hackathon).

Follows docs/06 §6.5: weighted 0-1 features x 100, visual similarity
weight redistributed (no image embeddings for the hackathon). Scores are
illustrative demo values, not validated thresholds.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ..db.models import Report

MATCHER_VERSION = "rules-0.1"
SURFACE_THRESHOLD = 65.0
STRONG_THRESHOLD = 85.0

WEIGHTS = {"category": 0.25, "description": 0.25, "attributes": 0.20, "location": 0.15, "time": 0.15}

RELATED_CATEGORIES = {frozenset({"electronics", "phone"}), frozenset({"bag", "wallet"})}

STOP = {
    "the", "and", "with", "near", "found", "lost", "small", "large", "left", "right", "item", "has",
    "was", "from", "this", "that", "there", "some", "one", "for", "inside", "outside", "area", "very",
}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOP}


def _public_text_tokens(r: Report) -> set[str]:
    parts = [r.item_label, r.description, r.brand or "", r.model or "", *r.attributes_public.values()]
    return _tokens(" ".join(parts))


def _aware(dt: datetime | None) -> datetime | None:
    """Treat naive timestamps as UTC so naive/aware comparisons can't crash scoring."""
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def score_pair(lost: Report, found: Report, found_location_text: str) -> tuple[float, dict[str, float], list[str]]:
    comps: dict[str, float] = {}
    why: list[str] = []

    # category
    if lost.category == found.category:
        comps["category"] = 1.0
        why.append(f"Both reports are in the same category ({lost.category}).")
    elif frozenset({lost.category, found.category}) in RELATED_CATEGORIES:
        comps["category"] = 0.5
        why.append("The item categories are related.")
    else:
        comps["category"] = 0.0

    # description (public text only, so explanations never leak private values)
    a, b = _public_text_tokens(lost), _public_text_tokens(found)
    shared = sorted(a & b)
    overlap = len(shared) / max(1, min(len(a), len(b)))
    comps["description"] = round(min(1.0, overlap * 1.5), 3)
    if shared:
        why.append("Both descriptions mention: " + ", ".join(shared[:4]) + ".")

    # visible attributes (+ brand)
    la = {k.lower(): v.lower().strip() for k, v in lost.attributes_public.items()}
    fa = {k.lower(): v.lower().strip() for k, v in found.attributes_public.items()}
    if lost.brand and found.brand:
        la["brand"], fa["brand"] = lost.brand.lower(), found.brand.lower()
    common = set(la) & set(fa)
    if common:
        same = [k for k in common if la[k] == fa[k]]
        comps["attributes"] = round(len(same) / len(common), 3)
        if same:
            why.append("Matching visible attributes: " + ", ".join(f"{k} ({la[k]})" for k in sorted(same)) + ".")
    else:
        comps["attributes"] = 0.5  # missing data is not a mismatch

    # location (text only)
    lt, ft = _tokens(lost.location_label), _tokens(found_location_text)
    if lt and ft:
        comps["location"] = 1.0 if lt & ft else 0.2
        if lt & ft:
            why.append(f"The reported locations overlap ({found_location_text}).")
    else:
        comps["location"] = 0.5

    # time
    found_at, lost_start, lost_end = _aware(found.found_at), _aware(lost.lost_at_start), _aware(lost.lost_at_end)
    if found_at and (lost_start or lost_end):
        start = lost_start or lost_end
        end = (lost_end or lost_start) + timedelta(hours=72)  # type: ignore[operator]
        if start - timedelta(hours=2) <= found_at <= end:  # type: ignore[operator]
            comps["time"] = 1.0
            why.append("The item was found within the reported time window.")
        else:
            gap = min(abs((found_at - start).total_seconds()), abs((found_at - end).total_seconds()))
            comps["time"] = round(max(0.0, 1 - gap / (14 * 86400)), 3)
    else:
        comps["time"] = 0.5

    total = round(sum(WEIGHTS[k] * comps[k] for k in WEIGHTS) * 100, 1)
    return total, comps, why


def label_for(score: float) -> str:
    return "Strong potential match" if score >= STRONG_THRESHOLD else "Possible match"
