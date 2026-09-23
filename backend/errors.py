"""Request ID tracking and structured error responses. Every response
(success or error) carries an X-Request-ID header; every error response
also embeds it in the body as {"error": {"code", "message", "request_id"}}
instead of FastAPI's default {"detail": ...}."""

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("rag_api")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
}


def _code_for_status(status_code):
    return _STATUS_CODES.get(status_code, "error")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns a request_id (reusing an incoming X-Request-ID if given),
    logs every request's outcome, and attaches the id as a response
    header -- runs for every request/response, success or error."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.monotonic()

        response = await call_next(request)

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response


def register_error_handlers(app: FastAPI):
    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        request_id = _request_id(request)
        headers = dict(exc.headers or {})
        headers["X-Request-ID"] = request_id
        return JSONResponse(
            status_code=exc.status_code,
            headers=headers,
            content={
                "error": {
                    "code": _code_for_status(exc.status_code),
                    "message": str(exc.detail),
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        # RequestValidationError is not an HTTPException subclass, so
        # without this it falls through to FastAPI's own default handler
        # (a bare {"detail": [...]} body) instead of our structured shape.
        request_id = _request_id(request)
        return JSONResponse(
            status_code=422,
            headers={"X-Request-ID": request_id},
            content={
                "error": {
                    "code": "validation_error",
                    "message": str(exc.errors()),
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit_exceeded(request: Request, exc: RateLimitExceeded):
        request_id = _request_id(request)
        response = JSONResponse(
            status_code=429,
            headers={"X-Request-ID": request_id},
            content={
                "error": {
                    "code": "rate_limited",
                    "message": "Too many requests. Please slow down.",
                    "request_id": request_id,
                }
            },
        )
        # Populates Retry-After (and X-RateLimit-*) from the limiter's own
        # tracked state for this request -- same mechanism slowapi's
        # default handler uses, just wrapped in our own error shape. This
        # reaches into a private (underscore-prefixed) slowapi method, so
        # it's wrapped defensively: a slowapi upgrade that renames/removes
        # it should degrade to a 429 without these extra headers, not
        # crash the error handler itself.
        try:
            return request.app.state.limiter._inject_headers(
                response, request.state.view_rate_limit
            )
        except Exception:
            logger.warning(
                "failed to inject rate-limit headers (slowapi internals may have "
                "changed) request_id=%s", request_id, exc_info=True,
            )
            return response

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        request_id = _request_id(request)
        logger.exception("unhandled_exception request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": request_id},
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "request_id": request_id,
                }
            },
        )
