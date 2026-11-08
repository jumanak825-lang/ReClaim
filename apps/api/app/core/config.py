"""Runtime configuration read from environment variables (see the root `.env.example`)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    app_base_url: str = field(default_factory=lambda: _env("APP_BASE_URL", "http://localhost:3000"))
    api_base_url: str = field(default_factory=lambda: _env("API_BASE_URL", "http://localhost:8000"))
    cors_origins: list[str] = field(default_factory=lambda: _csv(_env("CORS_ORIGINS", "http://localhost:3000")))

    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "postgresql+psycopg://reclaim:reclaim@localhost:5433/reclaim")
    )

    session_cookie_name: str = "reclaim_session"
    session_ttl_hours: int = field(default_factory=lambda: int(_env("SESSION_TTL_HOURS", "12")))
    cookie_secure: bool = field(default_factory=lambda: _bool("COOKIE_SECURE", False))

    # Uploads: local-disk adapter for now (docs/11). Kept behind app/integrations/storage.py.
    upload_provider: str = field(default_factory=lambda: _env("UPLOAD_PROVIDER", "local"))
    upload_dir: Path = field(default_factory=lambda: Path(_env("UPLOAD_DIR", str(API_ROOT / "var" / "uploads"))))
    max_upload_bytes: int = 8 * 1024 * 1024

    # Rate limits: "<count>/<seconds>" per key (docs/08). Set RATE_LIMITS_ENABLED=false to disable.
    rate_limits_enabled: bool = field(default_factory=lambda: _bool("RATE_LIMITS_ENABLED", True))
    rate_limit_auth: str = field(default_factory=lambda: _env("RATE_LIMIT_AUTH", "10/60"))
    rate_limit_upload: str = field(default_factory=lambda: _env("RATE_LIMIT_UPLOAD", "30/60"))
    rate_limit_claim: str = field(default_factory=lambda: _env("RATE_LIMIT_CLAIM", "5/300"))

    # Background worker. "embedded" polls the outbox from inside the API process (handy for local dev
    # and the frontend's e2e run). Production runs `python -m app.workers` and sets WORKER_MODE=external.
    worker_mode: str = field(default_factory=lambda: _env("WORKER_MODE", "embedded"))
    worker_poll_seconds: float = field(default_factory=lambda: float(_env("WORKER_POLL_SECONDS", "1")))
    worker_max_attempts: int = field(default_factory=lambda: int(_env("WORKER_MAX_ATTEMPTS", "6")))

    # AI extraction. With no key, the deterministic fallback runs (docs/11 §1).
    ai_provider: str = field(default_factory=lambda: _env("AI_PROVIDER", "xai"))
    ai_api_key: str = field(default_factory=lambda: _env("AI_API_KEY"))
    ai_base_url: str = field(default_factory=lambda: _env("AI_BASE_URL", "https://api.x.ai/v1"))
    ai_vision_model: str = field(default_factory=lambda: _env("AI_VISION_MODEL"))
    ai_timeout_seconds: float = field(default_factory=lambda: float(_env("AI_TIMEOUT_SECONDS", "30")))

    # PayPal. PAYPAL_MODE: "auto" (sandbox when client id + secret are set, else mock), "sandbox", "mock".
    paypal_mode_setting: str = field(default_factory=lambda: _env("PAYPAL_MODE", "auto").lower())
    paypal_base_url: str = field(default_factory=lambda: _env("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com"))
    paypal_client_id: str = field(default_factory=lambda: _env("PAYPAL_CLIENT_ID"))
    paypal_client_secret: str = field(default_factory=lambda: _env("PAYPAL_CLIENT_SECRET"))
    paypal_webhook_id: str = field(default_factory=lambda: _env("PAYPAL_WEBHOOK_ID"))

    # Zapier: one catch-hook URL from env for the hackathon (docs/11 §2).
    zapier_webhook_url: str | None = field(default_factory=lambda: _env("ZAPIER_WEBHOOK_URL") or None)
    zapier_webhook_secret: str = field(default_factory=lambda: _env("ZAPIER_WEBHOOK_SECRET"))

    # Simulated courier: dispatched -> in_transit after this many seconds.
    courier_seconds: float = field(default_factory=lambda: float(_env("SIMULATED_COURIER_SECONDS", "20")))

    # /api/v1/dev/* (reset, demo accounts, mock PayPal, courier advance). Off unless explicitly enabled:
    # never turn on when the API is reachable from outside your machine (e.g. via ngrok).
    enable_dev_routes: bool = field(default_factory=lambda: _bool("ENABLE_DEV_ROUTES", False))

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_api_key and self.ai_vision_model)

    @property
    def paypal_mode(self) -> str:
        """"sandbox" calls PayPal's Orders v2 API; "mock" uses the local mock checkout (dev routes)."""
        if self.paypal_mode_setting in {"sandbox", "mock"}:
            return self.paypal_mode_setting
        return "sandbox" if self.paypal_client_id and self.paypal_client_secret else "mock"

    @property
    def paypal_is_sandbox(self) -> bool:
        return "sandbox" in self.paypal_base_url

    @property
    def paypal_webhook_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret and self.paypal_webhook_id)


settings = Settings()
