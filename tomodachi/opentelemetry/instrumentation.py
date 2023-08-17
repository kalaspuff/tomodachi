import logging
from os import environ
from typing import Any, Collection, List, Optional, Set, Type, Union, cast

import structlog

import tomodachi
from opentelemetry._logs import NoOpLoggerProvider, get_logger_provider, set_logger_provider
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.sdk._configuration import _get_exporter_names, _import_exporters
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.environment_variables import OTEL_LOG_LEVEL
from opentelemetry.sdk.resources import OTELResourceDetector, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NoOpTracerProvider, ProxyTracerProvider, get_tracer_provider, set_tracer_provider
from tomodachi.opentelemetry.logging import OpenTelemetryLoggingHandler, add_trace_structlog_processor
from tomodachi.opentelemetry.middleware import OpenTelemetryAioHTTPMiddleware, OpenTelemetryAWSSQSMiddleware
from tomodachi.opentelemetry.package import _instruments


class TomodachiInstrumentor(BaseInstrumentor):
    _original_service_cls: Optional[Type[tomodachi.Service]] = None
    _instrumented_services: Optional[Set[tomodachi.Service]] = None
    _is_instrumented_by_opentelemetry: bool = False

    @classmethod
    def instrument_service(cls, service: tomodachi.Service, tracer_provider: Optional[TracerProvider] = None) -> None:
        if isinstance(service, type):
            raise Exception("instrument_service must be called with an instance of tomodachi.Service")

        tracer_provider = cls._tracer_provider(tracer_provider)

        if cls._instrumented_services is None:
            cls._instrumented_services = set()

        cls._instrumented_services.add(service)

        aiohttp_middleware = getattr(service, "_aiohttp_middleware", None)
        if aiohttp_middleware is None:
            aiohttp_middleware = []
            setattr(service, "_aiohttp_middleware", aiohttp_middleware)
        if not [m for m in aiohttp_middleware if isinstance(m, OpenTelemetryAioHTTPMiddleware)]:
            aiohttp_middleware.append(OpenTelemetryAioHTTPMiddleware(service=service, tracer_provider=tracer_provider))

        message_middleware = getattr(service, "message_middleware", None)
        if message_middleware is None:
            message_middleware = []
            setattr(service, "message_middleware", message_middleware)
        if not [m for m in message_middleware if isinstance(m, OpenTelemetryAWSSQSMiddleware)]:
            message_middleware.append(OpenTelemetryAWSSQSMiddleware(service=service, tracer_provider=tracer_provider))

        setattr(service, "_is_instrumented_by_opentelemetry", True)

    @classmethod
    def uninstrument_service(cls, service: tomodachi.Service) -> None:
        if isinstance(service, type):
            raise Exception("uninstrument_service must be called with an instance of tomodachi.Service")

        if cls._instrumented_services is not None:
            try:
                cls._instrumented_services.remove(service)
            except KeyError:
                pass

        aiohttp_middleware = getattr(service, "_aiohttp_middleware", None)
        if aiohttp_middleware:
            for middleware in aiohttp_middleware[:]:
                if isinstance(middleware, OpenTelemetryAioHTTPMiddleware):
                    aiohttp_middleware.remove(middleware)

        message_middleware = getattr(service, "message_middleware", None)
        if message_middleware:
            for middleware in message_middleware[:]:
                if isinstance(middleware, OpenTelemetryAWSSQSMiddleware):
                    message_middleware.remove(middleware)

        setattr(service, "_is_instrumented_by_opentelemetry", False)

    @classmethod
    def instrument_logging(
        cls,
        names: Union[Optional[str], List[Optional[str]]],
        logger_provider: Optional[LoggerProvider] = None,
        log_level: int = logging.NOTSET,
    ) -> None:
        logger_provider = cls._logger_provider(logger_provider)

        if not isinstance(names, (list, tuple)):
            names = [names]

        for name in names[:]:
            logger = logging.getLogger(name)
            for handler in logger.handlers:
                if isinstance(handler, OpenTelemetryLoggingHandler):
                    names.remove(name)

        log_level_ = environ.get(OTEL_LOG_LEVEL, log_level) or logging.NOTSET
        if isinstance(log_level_, str) and not log_level_.isdigit():
            log_level = getattr(logging, log_level_.upper(), None) or logging.NOTSET
        elif isinstance(log_level_, str) and log_level_.isdigit():
            log_level = int(log_level_)
        handler = OpenTelemetryLoggingHandler(level=log_level, logger_provider=logger_provider)

        for name in names:
            logging.getLogger(name).addHandler(handler)

    @classmethod
    def uninstrument_logging(cls, names: Union[Optional[str], List[Optional[str]]]) -> None:
        if not isinstance(names, (list, tuple)):
            names = [names]

        for name in names:
            logger = logging.getLogger(name)
            for handler in logger.handlers:
                if not isinstance(handler, OpenTelemetryLoggingHandler):
                    continue
                logger.removeHandler(handler)
                try:
                    handler.acquire()
                    handler.flush()
                    handler.close()
                except (OSError, ValueError):
                    pass
                finally:
                    handler.release()

    @classmethod
    def instrument_structlog_logger(cls, logger: structlog.BoundLoggerBase) -> None:
        if not isinstance(logger._processors, list):
            raise Exception("logger._processors must be a list")
        if add_trace_structlog_processor not in logger._processors:
            logger._processors.insert(-1, add_trace_structlog_processor)

    @classmethod
    def uninstrument_structlog_logger(cls, logger: structlog.BoundLoggerBase) -> None:
        if not isinstance(logger._processors, list):
            raise Exception("logger._processors must be a list")
        if add_trace_structlog_processor in logger._processors:
            logger._processors.remove(add_trace_structlog_processor)

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument_tomodachi_class(self, tracer_provider: TracerProvider) -> None:
        _InstrumentedTomodachiService._tracer_provider = tracer_provider
        if self._original_service_cls is not tomodachi.Service:
            self._original_service_cls = tomodachi.Service
            setattr(tomodachi, "Service", _InstrumentedTomodachiService)

    def _instrument_services(self, tracer_provider: TracerProvider) -> None:
        pass

    def _instrument_logging(self, logger_provider: LoggerProvider) -> None:
        self.instrument_logging(["tomodachi", "exception"], logger_provider=logger_provider)

    def _instrument_structlog_loggers(self) -> None:
        for logger in (
            tomodachi.logging.console_logger,
            tomodachi.logging.no_color_console_logger,
            tomodachi.logging.json_logger,
        ):
            self.instrument_structlog_logger(logger)

    def _instrument(self, **kwargs: Any) -> None:
        tracer_provider: TracerProvider = self._tracer_provider(kwargs.get("tracer_provider"))
        logger_provider: LoggerProvider = self._logger_provider(kwargs.get("logger_provider"))

        self._instrument_tomodachi_class(tracer_provider)
        self._instrument_services(tracer_provider)
        self._instrument_logging(logger_provider)
        self._instrument_structlog_loggers()

    def instrument(self, **kwargs: Any) -> None:
        if not self._is_instrumented_by_opentelemetry or not TomodachiInstrumentor._instrumented_services:
            self._is_instrumented_by_opentelemetry = False
            super().instrument(**kwargs)

    def _uninstrument_tomodachi_class(self) -> None:
        _InstrumentedTomodachiService._tracer_provider = None
        if self._original_service_cls:
            setattr(tomodachi, "Service", self._original_service_cls)

    def _uninstrument_services(self) -> None:
        if TomodachiInstrumentor._instrumented_services is not None:
            for service in TomodachiInstrumentor._instrumented_services:
                self.uninstrument_service(service)
            TomodachiInstrumentor._instrumented_services.clear()

    def _uninstrument_logging(self) -> None:
        TomodachiInstrumentor.uninstrument_logging(["tomodachi", "exception"])

    def _uninstrument_structlog_loggers(self) -> None:
        for logger in (
            tomodachi.logging.console_logger,
            tomodachi.logging.no_color_console_logger,
            tomodachi.logging.json_logger,
        ):
            TomodachiInstrumentor.uninstrument_structlog_logger(logger)

    def _uninstrument(self, **kwargs: Any) -> None:
        self._uninstrument_tomodachi_class()
        self._uninstrument_services()
        self._uninstrument_logging()
        self._uninstrument_structlog_loggers()

    def uninstrument(self, **kwargs: Any) -> None:
        if not self._is_instrumented_by_opentelemetry:
            self._is_instrumented_by_opentelemetry = True
        self._uninstrument(**kwargs)

    @staticmethod
    def _tracer_provider(tracer_provider: Optional[TracerProvider] = None) -> TracerProvider:
        if not tracer_provider:
            tracer_provider = cast(TracerProvider, get_tracer_provider())
            if isinstance(tracer_provider, (NoOpTracerProvider, ProxyTracerProvider)):
                resource = Resource.create().merge(OTELResourceDetector().detect())
                tracer_provider = TracerProvider(resource=resource)
                set_tracer_provider(tracer_provider)

        if (
            getattr(tracer_provider, "_active_span_processor", None)
            and not tracer_provider._active_span_processor._span_processors
        ):
            exporter_names = _get_exporter_names("traces")
            if not exporter_names:
                return

            trace_exporters, _, _ = _import_exporters(
                exporter_names,
                [],
                [],
            )
            if not trace_exporters:
                return

            for _, exporter in trace_exporters.items():
                tracer_provider._active_span_processor.add_span_processor(BatchSpanProcessor(exporter()))

        return tracer_provider

    @staticmethod
    def _logger_provider(logger_provider: Optional[LoggerProvider] = None) -> LoggerProvider:
        if not logger_provider:
            logger_provider = cast(LoggerProvider, get_logger_provider())
            if isinstance(logger_provider, NoOpLoggerProvider):
                resource = Resource.create().merge(OTELResourceDetector().detect())
                logger_provider = LoggerProvider(resource=resource)
                set_logger_provider(logger_provider)

        if (
            getattr(logger_provider, "_multi_log_record_processor", None)
            and not logger_provider._multi_log_record_processor._log_record_processors
        ):
            exporter_names = _get_exporter_names("logs")
            if not exporter_names:
                return

            _, _, log_exporters = _import_exporters(
                [],
                [],
                exporter_names,
            )
            if not log_exporters:
                return

            for _, exporter in log_exporters.items():
                logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter()))

        return logger_provider


class _InstrumentedTomodachiService(tomodachi.Service):
    _tomodachi_class_is_service_class: bool = False
    _is_instrumented_by_opentelemetry: bool = False
    _tracer_provider: Optional[TracerProvider] = None

    def __post_init_hook(self) -> None:
        TomodachiInstrumentor.instrument_service(self, tracer_provider=self._tracer_provider)

    def __post_teardown_hook(self) -> None:
        TomodachiInstrumentor.uninstrument_service(self)
