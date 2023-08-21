import copy
import logging
from os import environ
from typing import Any, Awaitable, Callable, Collection, Dict, List, Optional, Set, Tuple, Type, Union, cast

import structlog
from wrapt import wrap_function_wrapper

import tomodachi
from opentelemetry._logs import NoOpLoggerProvider, get_logger_provider, set_logger_provider
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor  # type: ignore
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.sdk._configuration import _get_exporter_names, _import_exporters
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.environment_variables import OTEL_LOG_LEVEL
from opentelemetry.sdk.resources import SERVICE_NAME as RESOURCE_SERVICE_NAME
from opentelemetry.sdk.resources import OTELResourceDetector, Resource
from opentelemetry.sdk.trace import Tracer, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import (
    NoOpTracerProvider,
    ProxyTracerProvider,
    SpanKind,
    StatusCode,
    get_tracer,
    get_tracer_provider,
    set_tracer_provider,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.util.types import AttributeValue
from tomodachi.__version__ import __version__ as tomodachi_version
from tomodachi.opentelemetry.logging import OpenTelemetryLoggingHandler, add_trace_structlog_processor
from tomodachi.opentelemetry.middleware import (
    OpenTelemetryAioHTTPMiddleware,
    OpenTelemetryAMQPMiddleware,
    OpenTelemetryAWSSQSMiddleware,
    OpenTelemetryScheduleFunctionMiddleware,
)


class TomodachiInstrumentor(BaseInstrumentor):
    _original_service_cls: Optional[Type[tomodachi.Service]] = None
    _instrumented_services: Optional[Set[tomodachi.Service]] = None
    _logging_handlers: Optional[List[OpenTelemetryLoggingHandler]] = None
    _is_instrumented_by_opentelemetry: bool = False

    @classmethod
    def instrument_service(cls, service: tomodachi.Service, tracer_provider: Optional[TracerProvider] = None) -> None:
        if isinstance(service, type):
            raise Exception("instrument_service must be called with an instance of tomodachi.Service")

        tracer_provider = cls._tracer_provider(tracer_provider)

        if cls._instrumented_services is None:
            cls._instrumented_services = set()

        cls._instrumented_services.add(service)

        # setting resource "service.name" if not set - this is a bit hacky at the moment
        resource_service_name = tracer_provider.resource._attributes.get(RESOURCE_SERVICE_NAME)
        service_name = service.name
        if (
            not resource_service_name
            or resource_service_name == "unknown_service"
            or resource_service_name.startswith("unknown_service:")
        ) and service_name not in ("service", "app"):
            resource = tracer_provider.resource.merge(Resource.create({RESOURCE_SERVICE_NAME: service_name}))
            tracer_provider = copy.copy(tracer_provider)
            tracer_provider._resource = resource
            setattr(service, "_opentelemetry_tracer_provider", tracer_provider)

            for logging_handler in cls._logging_handlers or []:
                logger_provider = cast(LoggerProvider, logging_handler._logger_provider)
                resource_service_name_ = logger_provider.resource._attributes.get(RESOURCE_SERVICE_NAME)
                if not resource_service_name_ or resource_service_name_ == resource_service_name:
                    resource = logger_provider.resource.merge(Resource.create({RESOURCE_SERVICE_NAME: service_name}))
                    logger_provider._resource = resource
                    logging_handler._logger_provider = logger_provider
                    setattr(logging_handler._logger, "_resource", logger_provider.resource)

        tracer = get_tracer("tomodachi.opentelemetry", tomodachi_version, tracer_provider)
        setattr(service, "_opentelemetry_tracer", tracer)

        aiohttp_pre_middleware = getattr(service, "_aiohttp_pre_middleware", None)
        if aiohttp_pre_middleware is None:
            aiohttp_pre_middleware = []
            setattr(service, "_aiohttp_pre_middleware", aiohttp_pre_middleware)
        if not [m for m in aiohttp_pre_middleware if isinstance(m, OpenTelemetryAioHTTPMiddleware)]:
            aiohttp_pre_middleware.append(
                OpenTelemetryAioHTTPMiddleware(service=service, tracer=tracer, tracer_provider=tracer_provider)
            )

        awssnssqs_message_pre_middleware = getattr(service, "_awssnssqs_message_pre_middleware", None)
        if awssnssqs_message_pre_middleware is None:
            awssnssqs_message_pre_middleware = []
            setattr(service, "_awssnssqs_message_pre_middleware", awssnssqs_message_pre_middleware)
        if not [m for m in awssnssqs_message_pre_middleware if isinstance(m, OpenTelemetryAWSSQSMiddleware)]:
            awssnssqs_message_pre_middleware.append(
                OpenTelemetryAWSSQSMiddleware(service=service, tracer=tracer, tracer_provider=tracer_provider)
            )

        amqp_message_pre_middleware = getattr(service, "_amqp_message_pre_middleware", None)
        if amqp_message_pre_middleware is None:
            amqp_message_pre_middleware = []
            setattr(service, "_amqp_message_pre_middleware", amqp_message_pre_middleware)
        if not [m for m in amqp_message_pre_middleware if isinstance(m, OpenTelemetryAMQPMiddleware)]:
            amqp_message_pre_middleware.append(
                OpenTelemetryAMQPMiddleware(service=service, tracer=tracer, tracer_provider=tracer_provider)
            )

        schedule_pre_middleware = getattr(service, "_schedule_pre_middleware", None)
        if schedule_pre_middleware is None:
            schedule_pre_middleware = []
            setattr(service, "_schedule_pre_middleware", schedule_pre_middleware)
        if not [m for m in schedule_pre_middleware if isinstance(m, OpenTelemetryScheduleFunctionMiddleware)]:
            schedule_pre_middleware.append(
                OpenTelemetryScheduleFunctionMiddleware(service=service, tracer=tracer, tracer_provider=tracer_provider)
            )

        context = getattr(service, "context", None)  # test
        if context:
            context["_aiohttp_pre_middleware"] = aiohttp_pre_middleware
            context["_awssnssqs_message_pre_middleware"] = awssnssqs_message_pre_middleware
            context["_amqp_message_pre_middleware"] = amqp_message_pre_middleware
            context["_schedule_pre_middleware"] = schedule_pre_middleware

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

        aiohttp_pre_middleware = getattr(service, "_aiohttp_pre_middleware", None)
        if aiohttp_pre_middleware:
            for middleware in aiohttp_pre_middleware[:]:
                if isinstance(middleware, OpenTelemetryAioHTTPMiddleware):
                    aiohttp_pre_middleware.remove(middleware)

        awssnssqs_message_pre_middleware = getattr(service, "_awssnssqs_message_pre_middleware", None)
        if awssnssqs_message_pre_middleware:
            for middleware in awssnssqs_message_pre_middleware[:]:
                if isinstance(middleware, OpenTelemetryAWSSQSMiddleware):
                    awssnssqs_message_pre_middleware.remove(middleware)

        amqp_message_pre_middleware = getattr(service, "_amqp_message_pre_middleware", None)
        if amqp_message_pre_middleware:
            for middleware in amqp_message_pre_middleware[:]:
                if isinstance(middleware, OpenTelemetryAMQPMiddleware):
                    amqp_message_pre_middleware.remove(middleware)

        schedule_pre_middleware = getattr(service, "_schedule_pre_middleware", None)
        if schedule_pre_middleware:
            for middleware in schedule_pre_middleware[:]:
                if isinstance(middleware, OpenTelemetryScheduleFunctionMiddleware):
                    schedule_pre_middleware.remove(middleware)

        setattr(service, "_opentelemetry_tracer_provider", None)
        setattr(service, "_opentelemetry_tracer", None)
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

        if not names:
            return

        log_level_ = environ.get(OTEL_LOG_LEVEL, log_level) or logging.NOTSET
        if isinstance(log_level_, str) and not log_level_.isdigit():
            log_level = getattr(logging, log_level_.upper(), None) or logging.NOTSET
        elif isinstance(log_level_, str) and log_level_.isdigit():
            log_level = int(log_level_)
        handler = OpenTelemetryLoggingHandler(level=log_level, logger_provider=logger_provider)

        if cls._logging_handlers is None:
            cls._logging_handlers = []
        cls._logging_handlers.append(handler)

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

        if cls._logging_handlers:
            cls._logging_handlers.clear()

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
        return (f"tomodachi == {tomodachi_version}",)

    def _instrument_tomodachi(self, tracer_provider: TracerProvider) -> None:
        _InstrumentedTomodachiService._opentelemetry_tracer_provider = tracer_provider
        if self._original_service_cls is not tomodachi.Service:
            self._original_service_cls = tomodachi.Service
            setattr(tomodachi, "Service", _InstrumentedTomodachiService)

        async def _traced_publish_awssnssqs_message(
            func: Callable[..., Awaitable[str]],
            cls: tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport,
            args: Tuple[str, Any, Dict, Dict],
            kwargs: Dict[str, Any],
        ) -> str:
            topic_arn, message, message_attributes, context = args
            tracer = cast(Tracer, context.get("_opentelemetry_tracer"))
            if not tracer:
                return await func(*args, **kwargs)

            topic: str = (
                cls.get_topic_name_without_prefix(cls.decode_topic(cls.get_topic_from_arn(topic_arn)), context)
                if topic_arn
                else ""
            )

            attributes: Dict[str, AttributeValue] = {
                "messaging.system": "AmazonSQS",
                "messaging.operation": "publish",
                "messaging.destination.name": topic,
                "messaging.destination.kind": "topic",
            }

            with tracer.start_as_current_span(
                f"{topic} publish",
                kind=SpanKind.PRODUCER,
                attributes=attributes,
            ) as span:
                TraceContextTextMapPropagator().inject(carrier=message_attributes)
                sns_message_id = await func(*args, **kwargs)
                span.set_attribute("messaging.message.id", sns_message_id)
                span.set_status(StatusCode.OK)

            return sns_message_id

        wrap_function_wrapper(
            "tomodachi.transport.aws_sns_sqs", "AWSSNSSQSTransport._publish_message", _traced_publish_awssnssqs_message
        )

        async def _traced_publish_amqp_message(
            func: Callable[..., Awaitable[str]],
            cls: tomodachi.transport.amqp.AmqpTransport,
            args: Tuple[str, str, Any, Dict, Optional[str], Any, Dict],
            kwargs: Dict[str, Any],
        ) -> None:
            routing_key, exchange_name, payload, properties, routing_key_prefix, service, context = args
            tracer = cast(Tracer, context.get("_opentelemetry_tracer"))
            if not tracer:
                await func(*args, **kwargs)
                return

            if not exchange_name:
                exchange_name = "amq.topic"

            attributes: Dict[str, AttributeValue] = {
                "messaging.system": "rabbitmq",
                "messaging.operation": "publish",
                "messaging.destination.name": exchange_name,
                "messaging.rabbitmq.destination.routing_key": routing_key,
            }

            if "headers" not in properties:
                properties["headers"] = {}

            with tracer.start_as_current_span(
                f"{routing_key} publish",
                kind=SpanKind.PRODUCER,
                attributes=attributes,
            ) as span:
                TraceContextTextMapPropagator().inject(carrier=properties["headers"])
                await func(*args, **kwargs)
                span.set_status(StatusCode.OK)

        wrap_function_wrapper(
            "tomodachi.transport.amqp", "AmqpTransport._publish_message", _traced_publish_amqp_message
        )

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

        self._instrument_tomodachi(tracer_provider)
        self._instrument_services(tracer_provider)
        self._instrument_logging(logger_provider)
        self._instrument_structlog_loggers()

    def instrument(self, **kwargs: Any) -> None:
        if not self._is_instrumented_by_opentelemetry or not TomodachiInstrumentor._instrumented_services:
            self._is_instrumented_by_opentelemetry = False
            super().instrument(**kwargs)

    def _uninstrument_tomodachi(self) -> None:
        _InstrumentedTomodachiService._opentelemetry_tracer_provider = None
        if self._original_service_cls:
            setattr(tomodachi, "Service", self._original_service_cls)

        unwrap(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport, "_publish_message")
        unwrap(tomodachi.transport.amqp.AmqpTransport, "_publish_message")

    def _uninstrument_services(self) -> None:
        if TomodachiInstrumentor._instrumented_services is not None:
            for service in [s for s in TomodachiInstrumentor._instrumented_services]:
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
        self._uninstrument_tomodachi()
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
                return tracer_provider

            trace_exporters, _, _ = _import_exporters(
                exporter_names,
                [],
                [],
            )
            if not trace_exporters:
                return tracer_provider

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
                return logger_provider

            _, _, log_exporters = _import_exporters(
                [],
                [],
                exporter_names,
            )
            if not log_exporters:
                return logger_provider

            for _, exporter in log_exporters.items():
                logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter()))

        return logger_provider


class _InstrumentedTomodachiService(tomodachi.Service):
    _tomodachi_class_is_service_class: bool = False
    _is_instrumented_by_opentelemetry: bool = False
    _opentelemetry_tracer_provider: Optional[TracerProvider] = None
    _opentelemetry_tracer: Optional[Tracer] = None

    def __post_init_hook(self) -> None:
        TomodachiInstrumentor.instrument_service(self, tracer_provider=self._opentelemetry_tracer_provider)

    def __post_teardown_hook(self) -> None:
        TomodachiInstrumentor.uninstrument_service(self)
