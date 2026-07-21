"""Request/run trace context and structured log helpers."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_trace_id: ContextVar[str | None] = ContextVar("alphadesk_trace_id", default=None)


def new_trace_id() -> str:
    return f"tr_{uuid4().hex[:24]}"


def get_trace_id() -> str | None:
    return _trace_id.get()


def set_trace_id(trace_id: str | None) -> None:
    _trace_id.set(trace_id)


def bind_trace_id(trace_id: str | None = None) -> str:
    value = trace_id or new_trace_id()
    set_trace_id(value)
    return value


class JsonLogFormatter(logging.Formatter):
    """Minimal JSON log lines with optional trace_id."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        trace = get_trace_id()
        if trace:
            payload["trace_id"] = trace
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key in ("workspace_id", "run_id", "event", "duration_ms", "cost_usd"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, default=str)


def configure_structured_logging(*, level: int = logging.INFO) -> None:
    """Attach a JSON formatter to the root logger once."""
    root = logging.getLogger()
    if any(isinstance(f, JsonLogFormatter) for h in root.handlers for f in [h.formatter]):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
