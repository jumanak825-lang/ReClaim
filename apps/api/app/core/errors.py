"""Error type and handlers producing the error envelope (docs/05 §5.1)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .envelope import ErrorEnvelope, request_id_var

log = logging.getLogger("reclaim.api")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers or {}


def not_found(entity: str) -> ApiError:
    return ApiError(404, f"{entity.upper()}_NOT_FOUND", f"{entity.replace('_', ' ').capitalize()} not found.")


def _body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {"code": code, "message": message, "details": details or {}},
        "meta": {"request_id": request_id_var.get(), "next_cursor": None},
    }


_HTTP_CODES = {
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    429: "RATE_LIMITED",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"loc": [str(p) for p in err.get("loc", [])], "message": err.get("msg", ""), "type": err.get("type", "")}
            for err in exc.errors()
        ]
        return JSONResponse(
            _body("VALIDATION_ERROR", "Some fields are invalid.", {"fields": fields}), status_code=400
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error request_id=%s", request_id_var.get())
        return JSONResponse(_body("INTERNAL_ERROR", "Something went wrong."), status_code=500)


# Documented on every router so the generated TypeScript types include the error shape.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorEnvelope, "description": desc}
    for status, desc in {
        400: "Validation error",
        401: "Not signed in",
        403: "Not allowed",
        404: "Not found",
        409: "State conflict",
        422: "Semantic validation error",
        429: "Rate limited (see Retry-After header)",
    }.items()
}
