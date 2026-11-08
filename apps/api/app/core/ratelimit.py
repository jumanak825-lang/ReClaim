"""Fixed-window rate limits stored in Postgres, shared by every API process (docs/08).

Counters are written in their own short transaction, so a request that fails and
rolls back (e.g. a wrong password) still counts.
"""

from __future__ import annotations

import time

from fastapi import Request
from sqlalchemy import text

from . import config
from .errors import ApiError

_UPSERT = text("""
    INSERT INTO rate_limit_buckets (key, window_start, count) VALUES (:key, :window, 1)
    ON CONFLICT (key, window_start) DO UPDATE SET count = rate_limit_buckets.count + 1
    RETURNING count
""")


def _parse(spec: str) -> tuple[int, int]:
    count, seconds = spec.split("/")
    return int(count), int(seconds)


def client_ip(request: Request) -> str:
    # The web app proxies /api/*, so the first X-Forwarded-For hop is the browser.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


def hit(bucket: str, key: str, spec: str) -> None:
    """Count one request for `bucket:key`; raise 429 RATE_LIMITED when over the limit."""
    if not config.settings.rate_limits_enabled:
        return
    from ..db.session import engine  # local import avoids a cycle at startup

    limit, window = _parse(spec)
    now = int(time.time())
    window_start = now - now % window
    with engine().begin() as conn:
        count = conn.execute(_UPSERT, {"key": f"{bucket}:{key}"[:200], "window": window_start}).scalar_one()
        if count == 1 and now % 50 == 0:  # occasional cleanup of old windows
            conn.execute(text("DELETE FROM rate_limit_buckets WHERE window_start < :cut"), {"cut": now - 86400})
    if count > limit:
        retry = window_start + window - now
        raise ApiError(429, "RATE_LIMITED", "Too many requests. Try again shortly.",
                       {"retry_after_seconds": retry}, headers={"Retry-After": str(max(1, retry))})
