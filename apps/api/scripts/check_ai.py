"""Check the xAI (Grok) extraction setup without printing the API key.

1. Lists the model ids this key can use, so you can pick AI_VISION_MODEL from real data.
2. If AI_VISION_MODEL is set, runs one real extraction (text plus a tiny image) through the same
   code path the worker uses, with no fallback, so a wrong model id or an unsupported
   feature shows up here instead of silently becoming "AI unavailable".

Usage (from apps/api, with AI_* exported):  .venv/Scripts/python scripts/check_ai.py
"""

import base64
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import config  # noqa: E402
from app.integrations.ai import ExtractionInput, GrokExtractor  # noqa: E402

# 1x1 white PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC")

s = config.settings
print(f"AI_PROVIDER      {s.ai_provider}")
print(f"AI_BASE_URL      {s.ai_base_url}")
print(f"AI_API_KEY       {'set' if s.ai_api_key else 'missing'}")
print(f"AI_VISION_MODEL  {s.ai_vision_model or 'missing'}")
if s.ai_provider != "xai":
    sys.exit("Only AI_PROVIDER=xai is implemented.")
if not s.ai_api_key:
    sys.exit("Set AI_API_KEY first.")

headers = {"Authorization": f"Bearer {s.ai_api_key}"}
with httpx.Client(base_url=s.ai_base_url, timeout=s.ai_timeout_seconds) as c:
    r = c.get("/models", headers=headers)
    if r.status_code != 200:
        sys.exit(f"Listing models FAILED: HTTP {r.status_code} (check the key and AI_BASE_URL)")
    ids = sorted(m.get("id", "?") for m in r.json().get("data", []))
    # xAI-specific listing with input modalities; optional, ignored if unavailable.
    vision = set()
    lm = c.get("/language-models", headers=headers)
    if lm.status_code == 200:
        vision = {m["id"] for m in lm.json().get("models", []) if "image" in (m.get("input_modalities") or [])}
print("\nModels available to this key" + (" (* = accepts images)" if vision else "") + ":")
for i in ids:
    print(f"  {'*' if i in vision else ' '} {i}")

if not s.ai_vision_model:
    sys.exit("\nSet AI_VISION_MODEL to one of the image-capable ids above, then run this again.")
if s.ai_vision_model not in ids:
    print(f"\nWARNING: AI_VISION_MODEL={s.ai_vision_model} is not in the list above (it may be an alias).")

print("\nRunning one test extraction...")
try:
    res = GrokExtractor().extract(ExtractionInput(
        item_label="Laptop", description="Silver laptop with a small sticker near the keyboard.",
        images=[("image/png", PNG)]))
except httpx.HTTPStatusError as exc:
    try:
        detail = exc.response.json()
    except ValueError:
        detail = exc.response.text[:300]
    sys.exit(f"Extraction FAILED: HTTP {exc.response.status_code}: {detail}")
except Exception as exc:
    sys.exit(f"Extraction FAILED: {type(exc).__name__}: {exc}")
print("Extraction OK. The lost wizard will show 'AI suggestions'.")
for name, (value, conf) in res.fields.items():
    print(f"  {name:10} {value!s:30} confidence {conf:.2f}")
