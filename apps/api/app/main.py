"""Reclaim API — STUB MODE.

In-memory, seeded, single-process backend that implements the demo-path
contract so the frontend can build against real endpoints. Replace
app/stub/* with Postgres-backed services; keep routers + schemas stable.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from .core.config import settings
from .core.envelope import request_id_var
from .core.errors import ERROR_RESPONSES, install_error_handlers
from .routers import auth, matches_claims, misc, organisations, recoveries_payments, reports
from .stub.seed import load_seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode()[:64]
        rid = incoming or str(uuid.uuid4())
        token = request_id_var.set(rid)

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_seed()
    yield


app = FastAPI(
    title="Reclaim API (stub)",
    version="0.1.0-stub",
    description="**STUB MODE**: in-memory data, seeded demo accounts, mocked PayPal, simulated courier, "
    "keyword-based extraction/matching. Data resets on restart or `POST /api/v1/dev/reset`. "
    "Response shapes are the contract for the real backend.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIdMiddleware)
install_error_handlers(app)

for r in (auth.router, reports.router, matches_claims.router, recoveries_payments.router,
          organisations.router, misc.router):
    app.include_router(r, prefix="/api/v1", responses=ERROR_RESPONSES)
