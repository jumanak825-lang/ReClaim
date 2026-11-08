"""Attribute extraction behind a provider interface (docs/06, docs/11 §1).

- DeterministicExtractor: keyword rules, always available, used when no AI key is set
  and as the fallback when the AI call fails.
- GrokExtractor: xAI's OpenAI-compatible chat completions API with a JSON schema response.
  The model id comes from AI_VISION_MODEL (docs/11 §7 says to confirm it on docs.x.ai).

Output is advisory: it only pre-fills the wizard's review step. It never changes claim,
payment or ownership state (CLAUDE.md rule 5).
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from ..core import config

log = logging.getLogger("reclaim.ai")

CATEGORIES = ["electronics", "phone", "bag", "wallet", "keys", "documents", "clothing", "jewellery",
              "eyewear", "umbrella", "toy", "other"]
FIELDS = ("category", "item_label", "brand", "model", "colour")


@dataclass
class ExtractionInput:
    item_label: str
    description: str
    images: list[tuple[str, bytes]] = field(default_factory=list)  # (content_type, data), public_safe only


@dataclass
class ExtractionResult:
    provider: str
    is_fallback: bool
    fields: dict[str, tuple[str | None, float]]  # name -> (value, confidence 0..1)


class Extractor(Protocol):
    name: str

    def extract(self, inp: ExtractionInput) -> ExtractionResult: ...


# ---------------------------------------------------------------- deterministic ----

COLOURS = ["black", "white", "silver", "grey", "gray", "gold", "red", "blue", "navy", "green", "brown", "pink",
           "purple", "yellow", "orange", "beige"]
BRANDS = ["northwind", "contoso", "fabrikam", "example"]
CATEGORY_WORDS = {
    "electronics": ["laptop", "tablet", "headphones", "earbuds", "camera", "charger", "notebook"],
    "phone": ["phone", "smartphone", "mobile"],
    "bag": ["bag", "backpack", "suitcase", "handbag", "tote", "luggage"],
    "wallet": ["wallet", "purse", "cardholder"],
    "keys": ["key", "keys", "fob", "keyring"],
    "documents": ["passport", "card", "licence", "license", "document"],
    "clothing": ["jacket", "coat", "scarf", "hat", "sweater", "hoodie"],
    "jewellery": ["ring", "necklace", "bracelet", "earring", "watch"],
    "eyewear": ["glasses", "sunglasses", "spectacles"],
    "umbrella": ["umbrella"],
    "toy": ["toy", "teddy", "doll"],
}


class DeterministicExtractor:
    name = "deterministic-fallback"

    def extract(self, inp: ExtractionInput) -> ExtractionResult:
        text = f"{inp.item_label} {inp.description}".lower()
        words = text.replace(",", " ").replace(".", " ").split()
        cat = label = None
        for c, keys in CATEGORY_WORDS.items():
            hit = next((w for w in words if w in keys), None)
            if hit:
                cat, label = c, hit.capitalize()
                break
        colour = next((c for c in COLOURS if c in words), None)
        brand = next((b.capitalize() for b in BRANDS if b in words), None)
        return ExtractionResult(self.name, True, {
            "category": (cat, 0.6 if cat else 0.0),
            "item_label": (label, 0.6 if label else 0.0),
            "brand": (brand, 0.5 if brand else 0.0),
            "model": (None, 0.0),
            "colour": (colour, 0.7 if colour else 0.0),
        })


# ------------------------------------------------------------------------- xAI ----

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": list(FIELDS),
    "properties": {
        name: {
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "confidence"],
            "properties": {
                "value": {"type": ["string", "null"], **({"enum": CATEGORIES + [None]} if name == "category" else {})},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
        }
        for name in FIELDS
    },
}

_PROMPT = (
    "You extract visible attributes of a lost or found item for a lost-and-found service. "
    "Use only what the text and images show. Use null when unsure; never guess serial numbers or "
    "identities. category must be one of: " + ", ".join(CATEGORIES) + ". item_label is a short noun "
    "phrase such as 'Laptop'. colour is the main colour in plain English."
)

# Tests replace this to avoid network calls.
transport: httpx.BaseTransport | None = None


class GrokExtractor:
    name = "xai"

    def extract(self, inp: ExtractionInput) -> ExtractionResult:
        s = config.settings
        content: list[dict[str, Any]] = [
            {"type": "text", "text": f"Item label: {inp.item_label}\nDescription: {inp.description}"}]
        for ctype, data in inp.images[:3]:
            content.append({"type": "image_url", "image_url": {
                "url": f"data:{ctype};base64,{base64.b64encode(data).decode()}"}})
        body = {
            "model": s.ai_vision_model,
            "messages": [{"role": "system", "content": _PROMPT}, {"role": "user", "content": content}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "item_attributes", "strict": True, "schema": _SCHEMA}},
            "temperature": 0,
        }
        with httpx.Client(base_url=s.ai_base_url, timeout=s.ai_timeout_seconds, transport=transport) as client:
            r = client.post("/chat/completions", json=body, headers={"Authorization": f"Bearer {s.ai_api_key}"})
            r.raise_for_status()
            raw = json.loads(r.json()["choices"][0]["message"]["content"])
        fields: dict[str, tuple[str | None, float]] = {}
        for name in FIELDS:
            item = raw.get(name) or {}
            value = item.get("value")
            if name == "category" and value not in CATEGORIES:
                value = None
            if isinstance(value, str):
                value = value.strip()[:120] or None
            conf = float(item.get("confidence") or 0)
            fields[name] = (value, max(0.0, min(1.0, conf)))
        return ExtractionResult(self.name, False, fields)


def extract(inp: ExtractionInput) -> ExtractionResult:
    """Run the configured provider; fall back to deterministic rules on any failure."""
    if config.settings.ai_enabled and config.settings.ai_provider == "xai":
        try:
            return GrokExtractor().extract(inp)
        except Exception as exc:  # outage, timeout, bad JSON: never block the report
            log.warning("ai extraction failed, using fallback: %s", type(exc).__name__)
    return DeterministicExtractor().extract(inp)
