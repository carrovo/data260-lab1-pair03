"""Request tracing: one trace id per request, carried everywhere.

TraceMiddleware reads X-Trace-Id (or makes a new id), keeps it in a context
variable for the length of the request, echoes it in the response header and
writes one access-log line that contains it. publish_safely() picks the id up
from the context variable, so the Kafka event, the worker log lines and the
MongoDB documents all carry the id the client saw.
"""

from __future__ import annotations

import logging
import re
import sys
import time
from contextvars import ContextVar

from .events import TRACE_HEADER, new_trace_id

logger = logging.getLogger("p03.http")

_current_trace_id: ContextVar[str | None] = ContextVar(
    "p03_trace_id", default=None
)
_SAFE_TRACE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_HEADER_BYTES = TRACE_HEADER.lower().encode("latin-1")


def get_trace_id() -> str | None:
    """Trace id of the request being handled, or None outside a request."""
    return _current_trace_id.get()


def clean_trace_id(value: str | None) -> str:
    """Keep a client id if it is short and plain; otherwise make a new one."""
    if value and _SAFE_TRACE_ID.match(value):
        return value
    return new_trace_id()


def _ensure_logger() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class TraceMiddleware:
    """Pure ASGI middleware, so the context variable is set for every handler."""

    def __init__(self, app, service: str = "") -> None:
        self.app = app
        self.service = service
        _ensure_logger()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name == _HEADER_BYTES:
                incoming = value.decode("latin-1")
                break
        trace_id = clean_trace_id(incoming)
        token = _current_trace_id.set(trace_id)
        started = time.perf_counter()
        status = {"code": 500}

        async def send_with_trace(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((_HEADER_BYTES, trace_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace)
        finally:
            logger.info(
                "request service=%s method=%s path=%s status=%s "
                "duration_ms=%.1f trace_id=%s",
                self.service or "-",
                scope.get("method", "-"),
                scope.get("path", "-"),
                status["code"],
                (time.perf_counter() - started) * 1000,
                trace_id,
            )
            _current_trace_id.reset(token)
