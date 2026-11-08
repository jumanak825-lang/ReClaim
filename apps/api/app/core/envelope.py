"""Response envelopes shared by every endpoint (see docs/05 §5.1)."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class Meta(BaseModel):
    request_id: str
    next_cursor: str | None = Field(
        default=None, description="Opaque cursor for the next page. Null when there are no more results."
    )


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta


class ErrorBody(BaseModel):
    code: str = Field(description="Stable machine-readable error code, e.g. CLAIM_NOT_REVIEWABLE.")
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody
    meta: Meta


def ok(data: Any, next_cursor: str | None = None) -> dict[str, Any]:
    """Wrap a payload in the success envelope."""
    return {"data": data, "meta": {"request_id": request_id_var.get(), "next_cursor": next_cursor}}
