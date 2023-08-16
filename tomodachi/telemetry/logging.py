from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import trace

if TYPE_CHECKING:  # pragma: no cover
    try:
        from structlog.typing import EventDict, WrappedLogger
    except (ImportError, ModuleNotFoundError):
        from structlog.types import EventDict, WrappedLogger


def add_open_telemetry_spans(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    span = trace.get_current_span()
    if not span.is_recording():
        return event_dict

    ctx = span.get_span_context()

    if ctx.span_id is not None:
        event_dict["span_id"] = hex(ctx.span_id)
    if ctx.trace_id is not None:
        event_dict["trace_id"] = hex(ctx.trace_id)
    event_dict["trace_flags"] = ctx.trace_flags

    return event_dict
