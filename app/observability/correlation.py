from __future__ import annotations

from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.ids import new_correlation_id

_CORRELATION_HEADER = "X-Correlation-Id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(_CORRELATION_HEADER) or new_correlation_id()
        bind_contextvars(correlation_id=correlation_id)

        span = trace.get_current_span()
        if span is not None:
            span.set_attribute("correlation_id", correlation_id)

        try:
            response = await call_next(request)
        finally:
            clear_contextvars()

        response.headers[_CORRELATION_HEADER] = correlation_id
        return response
