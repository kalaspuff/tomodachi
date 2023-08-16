import logging
from os import environ
from typing import Any, Collection, Dict, List, Optional, Set, Tuple, Type, cast

from opentelemetry import trace
from opentelemetry._logs import NoOpLoggerProvider, get_logger, get_logger_provider, set_logger_provider
from opentelemetry.environment_variables import _OTEL_PYTHON_LOGGER_PROVIDER as OTEL_PYTHON_LOGGER_PROVIDER
from opentelemetry.environment_variables import OTEL_LOGS_EXPORTER
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.sdk._configuration import _get_exporter_names, _import_exporters
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.environment_variables import OTEL_LOG_LEVEL
from opentelemetry.sdk.resources import OTELResourceDetector, Resource

import tomodachi
from tomodachi.__version__ import __version__ as tomodachi_version
from tomodachi.telemetry.logging import add_open_telemetry_spans
from tomodachi.telemetry.middleware import OpenTelemetryHTTPMiddleware
from tomodachi.telemetry.package import _instruments


class TomodachiInstrumentor(BaseInstrumentor):
    _original_service_cls: Optional[Type[tomodachi.Service]] = None
    _instrumented_services: Optional[Set[tomodachi.Service]] = None

    @staticmethod
    def instrument_service(service: tomodachi.Service, tracer_provider: Optional[trace.TracerProvider] = None) -> None:
        if isinstance(service, type):
            raise Exception("instrument_service must be called with an instance of tomodachi.Service")

        if TomodachiInstrumentor._instrumented_services is None:
            TomodachiInstrumentor._instrumented_services = set()

        TomodachiInstrumentor._instrumented_services.add(service)

        aiohttp_middleware = getattr(service, "_aiohttp_middleware", None)
        if aiohttp_middleware is None:
            aiohttp_middleware = []
            setattr(service, "_aiohttp_middleware", aiohttp_middleware)
        aiohttp_middleware.append(OpenTelemetryHTTPMiddleware(tracer_provider=tracer_provider))

        setattr(service, "_is_instrumented_by_opentelemetry", True)

    @staticmethod
    def uninstrument_service(service: tomodachi.Service) -> None:
        if isinstance(service, type):
            raise Exception("uninstrument_service must be called with an instance of tomodachi.Service")

        if TomodachiInstrumentor._instrumented_services is not None:
            try:
                TomodachiInstrumentor._instrumented_services.remove(service)
            except KeyError:
                pass

        aiohttp_middleware = getattr(service, "_aiohttp_middleware", None)
        if aiohttp_middleware:
            for middleware in aiohttp_middleware[:]:
                if isinstance(middleware, OpenTelemetryHTTPMiddleware):
                    aiohttp_middleware.remove(middleware)

        setattr(service, "_is_instrumented_by_opentelemetry", False)

    @staticmethod
    def instrument_logging() -> None:
        for logger in (
            tomodachi.logging.console_logger,
            tomodachi.logging.no_color_console_logger,
            tomodachi.logging.json_logger,
        ):
            if not isinstance(logger._processors, list):
                raise Exception("logger._processors must be a list")
            if add_open_telemetry_spans not in logger._processors:
                logger._processors.insert(-1, add_open_telemetry_spans)

    @staticmethod
    def uninstrument_logging() -> None:
        for logger in (
            tomodachi.logging.console_logger,
            tomodachi.logging.no_color_console_logger,
            tomodachi.logging.json_logger,
        ):
            if not isinstance(logger._processors, list):
                raise Exception("logger._processors must be a list")
            if add_open_telemetry_spans in logger._processors:
                logger._processors.remove(add_open_telemetry_spans)

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs: Any) -> None:
        resource = Resource.create().merge(OTELResourceDetector().detect())

        tracer_provider: Optional[trace.TracerProvider] = kwargs.get("tracer_provider")
        if not tracer_provider:
            tracer_provider = trace.get_tracer_provider()

        logger_provider: Optional[LoggerProvider] = kwargs.get("logger_provider")
        if not logger_provider:
            logger_provider = cast(LoggerProvider, get_logger_provider())
            if isinstance(logger_provider, NoOpLoggerProvider):
                logger_provider = LoggerProvider(resource=resource)
                set_logger_provider(logger_provider)

        _, _, log_exporters = _import_exporters(
            [],
            [],
            _get_exporter_names("logs"),
        )
        for _, exporter in log_exporters.items():
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter()))

        # instrument tomodachi.Service
        self._original_service_cls = tomodachi.Service
        _InstrumentedTomodachiService._tracer_provider = tracer_provider
        setattr(tomodachi, "Service", _InstrumentedTomodachiService)

        # instrument tomodachi.logging
        if not isinstance(tomodachi.logging.console_logger._processors, list):
            tomodachi.logging.console_logger._processors = list(tomodachi.logging.console_logger._processors)
        if add_open_telemetry_spans not in tomodachi.logging.console_logger._processors:
            tomodachi.logging.console_logger._processors.insert(0, add_open_telemetry_spans)

        # instrument logging
        log_level_ = environ.get(OTEL_LOG_LEVEL, "NOTSET")
        log_level: int = logging.NOTSET
        if isinstance(log_level_, str) and not log_level_.isdigit():
            log_level = getattr(logging, log_level_.upper(), None) or logging.NOTSET
        elif isinstance(log_level_, str) and log_level_.isdigit():
            log_level = int(log_level_)
        handler = _InstrumentedLoggingHandler(level=log_level, logger_provider=logger_provider)
        logging.getLogger("tomodachi").addHandler(handler)
        logging.getLogger("exception").addHandler(handler)

    def _uninstrument(self, **kwargs: Any) -> None:
        if TomodachiInstrumentor._instrumented_services is not None:
            for service in TomodachiInstrumentor._instrumented_services:
                self.uninstrument_service(service)
            TomodachiInstrumentor._instrumented_services.clear()

        if self._original_service_cls:
            setattr(tomodachi, "Service", self._original_service_cls)


from opentelemetry.util.types import Attributes


class _InstrumentedLoggingHandler(LoggingHandler):
    def __init__(self, level: int = logging.NOTSET, logger_provider: Optional[LoggerProvider] = None) -> None:
        super().__init__(level=level)
        self._logger_provider = logger_provider or get_logger_provider()
        self._logger = get_logger("tomodachi.telemetry", tomodachi_version, logger_provider=self._logger_provider)

    @staticmethod
    def _get_attributes(record: logging.LogRecord) -> Attributes:
        attributes = cast(Dict[str, Any], LoggingHandler._get_attributes(record))
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


class _InstrumentedTomodachiService(tomodachi.Service):
    _tomodachi_class_is_service_class: bool = False
    _is_instrumented_by_opentelemetry: bool = False
    _tracer_provider: Optional[trace.TracerProvider] = None

    def __post_init_hook(self) -> None:
        TomodachiInstrumentor.instrument_service(self, tracer_provider=self._tracer_provider)

    def __post_teardown_hook(self) -> None:
        TomodachiInstrumentor.uninstrument_service(self)
