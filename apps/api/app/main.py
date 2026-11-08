"""Reclaim API: FastAPI on PostgreSQL with an outbox worker.

Simulated parts are labelled in responses: PayPal Sandbox or the local mock checkout,
simulated courier, keyword fallback extraction when no AI key is configured.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from .core import config
from .core.envelope import request_id_var
from .core.errors import ERROR_RESPONSES, install_error_handlers
from .db.session import ping, transaction
from .routers import auth, matches_claims, misc, organisations, recoveries_payments, reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("reclaim.api")
access_log = logging.getLogger("reclaim.access")

# Log redaction (docs/08, CLAUDE.md): never log secrets, tokens or private evidence.
# - uvicorn's access log prints full URLs including query strings; ours logs the path only.
# - httpx logs every outbound URL at INFO; a Zapier catch-hook URL is itself a secret.
logging.getLogger("uvicorn.access").disabled = True
for noisy in ("httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


class RequestIdMiddleware:
    """Request ID on every response and one structured access-log line per request.

    Logs method, path (no query string: it can carry tokens), status and duration only.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode(errors="ignore")[:64]
        rid = incoming if incoming.replace("-", "").isalnum() else str(uuid.uuid4())
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            access_log.info("request_id=%s method=%s path=%s status=%s duration_ms=%.1f", rid, scope["method"],
                            scope["path"], status, (time.perf_counter() - started) * 1000)
            request_id_var.reset(token)


async def _embedded_worker() -> None:
    from .workers.outbox import drain

    log.info("embedded outbox worker started")
    while True:
        try:
            if await asyncio.to_thread(drain) == 0:
                await asyncio.sleep(config.settings.worker_poll_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("embedded worker error")
            await asyncio.sleep(5)


def _seed_if_empty() -> None:
    """Local convenience: with dev routes on, an empty (migrated) database gets the demo seed."""
    from . import seed

    try:
        with transaction():
            if seed.is_empty():
                seed.load_seed()
                log.info("empty database: demo seed loaded")
    except Exception as exc:
        log.warning("could not check/seed database (run `alembic upgrade head`?): %s", type(exc).__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = config.settings
    if not ping():
        log.error("database unreachable at startup; /api/v1/ready will report not_ready")
    elif s.enable_dev_routes:
        await asyncio.to_thread(_seed_if_empty)
    task = asyncio.create_task(_embedded_worker()) if s.worker_mode == "embedded" else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Reclaim API",
    version="0.2.0",
    description="Lost-and-found recovery network API (PostgreSQL). Simulated parts are labelled: "
    "payments run on PayPal Sandbox (or a local mock checkout when no PayPal credentials are set), the "
    "courier is simulated, and extraction falls back to keyword rules when no AI key is configured. "
    "`/api/v1/dev/*` needs ENABLE_DEV_ROUTES=true.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIdMiddleware)
install_error_handlers(app)

for r in (auth.router, reports.router, matches_claims.router, recoveries_payments.router,
          organisations.router, misc.router, misc.dev):
    app.include_router(r, prefix="/api/v1", responses=ERROR_RESPONSES)
