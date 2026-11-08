"""Write the OpenAPI schema to apps/api/openapi.json (the frontend generates TS types from it).

Usage (from apps/api):  .venv/Scripts/python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

schema = app.openapi()
(ROOT / "openapi.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
print(f"wrote openapi.json ({len(schema['paths'])} paths)")
