"""Runtime configuration read from environment variables.

Only the variables the stub API needs are read here. See the root
`.env.example` for the full list the real backend will use.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    app_base_url: str = field(default_factory=lambda: os.getenv("APP_BASE_URL", "http://localhost:3000"))
    api_base_url: str = field(default_factory=lambda: os.getenv("API_BASE_URL", "http://localhost:8000"))
    cors_origins: list[str] = field(
        default_factory=lambda: _csv(os.getenv("CORS_ORIGINS", "http://localhost:3000"))
    )
    session_cookie_name: str = "reclaim_session"
    session_ttl_hours: int = field(default_factory=lambda: int(os.getenv("SESSION_TTL_HOURS", "12")))
    cookie_secure: bool = field(default_factory=lambda: _bool("COOKIE_SECURE", False))
    max_upload_bytes: int = 8 * 1024 * 1024

    # Stub-only knobs. They make async behaviour visible to the frontend
    # (processing spinners, simulated courier) without a real worker.
    stub_processing_seconds: float = field(
        default_factory=lambda: float(os.getenv("STUB_PROCESSING_SECONDS", "2"))
    )
    stub_courier_seconds: float = field(
        default_factory=lambda: float(os.getenv("STUB_COURIER_SECONDS", "20"))
    )
    zapier_webhook_url: str | None = field(default_factory=lambda: os.getenv("ZAPIER_WEBHOOK_URL") or None)


settings = Settings()
