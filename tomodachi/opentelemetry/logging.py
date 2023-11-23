from __future__ import annotations

import logging
from traceback import format_exception
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from opentelemetry import trace
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.util.types import Attributes

from tomodachi.__version__ import __version__ as tomodachi_version

if TYPE_CHECKING:  # pragma: no cover
    try:
        from structlog.typing import EventDict, WrappedLogger
    except (ImportError, ModuleNotFoundError):
        from structlog.types import EventDict, WrappedLogger


def add_trace_structlog_processor(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    span = trace.get_current_span()
    ctx = span.get_span_context()

    if not ctx.is_valid:
        return event_dict

    event_dict["span_id"] = hex(ctx.span_id)
    event_dict["trace_id"] = hex(ctx.trace_id)

    parent: Optional[trace.SpanContext] = getattr(span, "parent", None)
    if parent:
        event_dict["parent_span_id"] = hex(parent.span_id)

    return event_dict


class OpenTelemetryLoggingHandler(LoggingHandler):
    def __init__(self, level: int = logging.NOTSET, logger_provider: Optional[LoggerProvider] = None) -> None:
        super().__init__(level=level)
        self._logger_provider = cast(LoggerProvider, logger_provider or get_logger_provider())
        self._logger = self._logger_provider.get_logger("tomodachi.opentelemetry", tomodachi_version)

    @staticmethod
    def _get_attributes(record: logging.LogRecord) -> Attributes:
        attributes = cast(Dict[str, Any], LoggingHandler._get_attributes(record))
        if record.exc_info:
            _, exc, tb = record.exc_info
            if exc is not None and exc.__traceback__ and exc.__traceback__ != tb:
                attributes["exception.stacktrace"] = "".join(format_exception(type(exc), exc, exc.__traceback__))
        logger_context: Dict[str, Any] = attributes.pop("logger.context", None)
        if not logger_context:
            return attributes
        for k, v in logger_context.items():
            if not isinstance(v, (bool, str, bytes, int, float)):
                attributes[f"{k}"] = str(v)
            else:
                attributes[f"{k}"] = v
        return attributes

    def emit(self, record: logging.LogRecord) -> None:
        record_ = self._translate(record)
        self._logger.emit(record_)
