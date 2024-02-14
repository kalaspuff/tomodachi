import functools
import logging
from os import environ
from typing import Any, Collection, Dict, List, Optional, Set, Union, cast

import structlog
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor  # type: ignore
from opentelemetry.metrics import NoOpMeter, get_meter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.environment_variables import OTEL_LOG_LEVEL
from opentelemetry.sdk.metrics import Meter, MeterProvider
from opentelemetry.sdk.resources import SERVICE_INSTANCE_ID as RESOURCE_SERVICE_INSTANCE_ID
from opentelemetry.sdk.resources import SERVICE_NAME as RESOURCE_SERVICE_NAME
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Tracer, TracerProvider
from opentelemetry.trace import NoOpTracer, SpanKind, StatusCode, get_tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.util.http import ExcludeList, get_excluded_urls, parse_excluded_urls
from opentelemetry.util.types import AttributeValue

import tomodachi
from tomodachi.__version__ import __version__ as tomodachi_version
from tomodachi.opentelemetry.distro import (
    _add_meter_provider_views,
    _create_logger_provider,
    _create_meter_provider,
    _create_tracer_provider,
    _get_logger_provider,
    _get_meter_provider,
    _get_tracer_provider,
)
from tomodachi.opentelemetry.logging import OpenTelemetryLoggingHandler, add_trace_structlog_processor
from tomodachi.opentelemetry.middleware import (
    OpenTelemetryAioHTTPMiddleware,
    OpenTelemetryAMQPMiddleware,
    OpenTelemetryAWSSQSMiddleware,
    OpenTelemetryScheduleFunctionMiddleware,
)

INSTRUMENTATION_CLASS_ATTRIBUTES = {
    "_opentelemetry_tracer_provider",
    "_opentelemetry_meter_provider",
    "_opentelemetry_excluded_urls",
    "_is_instrumented_by_opentelemetry",
    "_InstrumentedTomodachiService__post_init_hook",
    "_InstrumentedTomodachiService__post_teardown_hook",
}


class TomodachiInstrumentor(BaseInstrumentor):
    _instrumented_services: Optional[Set[tomodachi.Service]] = None
    _logging_handlers: Optional[List[OpenTelemetryLoggingHandler]] = None
    _is_instrumented_by_opentelemetry: bool = False

    @classmethod
    def instrument_service(
        cls,
        service: tomodachi.Service,
        tracer_provider: Optional[TracerProvider] = None,
        meter_provider: Optional[MeterProvider] = None,
        excluded_urls: Optional[str] = None,
    ) -> None:
        if isinstance(service, type):
            raise Exception("instrument_service must be called with an instance of tomodachi.Service")

        tracer_provider = cls._tracer_provider(tracer_provider)
        meter_provider = cls._meter_provider(meter_provider)

        if excluded_urls is None:
            _excluded_urls = ExcludeList(
                list(
                    set(
                        [url for url in get_excluded_urls("TOMODACHI")._excluded_urls]
                        + [url for url in get_excluded_urls("AIOHTTP")._excluded_urls]
                    )
                )
            )
        else:
            _excluded_urls = parse_excluded_urls(excluded_urls)

        if cls._instrumented_services is None:
            cls._instrumented_services = set()

        cls._instrumented_services.add(service)

        # setting resource "service.name" if not set - this is a bit hacky at the moment
        additional_resource_attributes: Dict[str, AttributeValue]
        if getattr(tracer_provider, "resource", None):
            additional_resource_attributes = {}
            if service.name not in ("service", "app"):
                attr_value = tracer_provider.resource._attributes.get(RESOURCE_SERVICE_NAME) or ""
                if attr_value[0:16] in ("", "unknown_service", "unknown_service:"):
                    additional_resource_attributes[RESOURCE_SERVICE_NAME] = service.name
                attr_value = tracer_provider.resource._attributes.get(RESOURCE_SERVICE_INSTANCE_ID) or ""
                if not attr_value:
                    additional_resource_attributes[RESOURCE_SERVICE_INSTANCE_ID] = service.uuid
            if additional_resource_attributes:
                resource = tracer_provider.resource.merge(
                    Resource.create({**tracer_provider.resource._attributes, **additional_resource_attributes})
                )
                tracer_provider.resource._attributes = resource._attributes

        if getattr(meter_provider._sdk_config, "resource", None):
            additional_resource_attributes = {}
            if service.name not in ("service", "app"):
                attr_value = meter_provider._sdk_config.resource._attributes.get(RESOURCE_SERVICE_NAME) or ""
                if attr_value[0:16] in ("", "unknown_service", "unknown_service:"):
                    additional_resource_attributes[RESOURCE_SERVICE_NAME] = service.name
            attr_value = meter_provider._sdk_config.resource._attributes.get(RESOURCE_SERVICE_INSTANCE_ID) or ""
            if not attr_value:
                additional_resource_attributes[RESOURCE_SERVICE_INSTANCE_ID] = service.uuid
            if additional_resource_attributes:
                resource = meter_provider._sdk_config.resource.merge(
                    Resource.create(
                        {**meter_provider._sdk_config.resource._attributes, **additional_resource_attributes}
                    )
                )
                meter_provider._sdk_config.resource._attributes = resource._attributes

        if cls._logging_handlers:
            for handler in cls._logging_handlers:
                logger_provider = cast(LoggerProvider, handler._logger_provider)
                if getattr(logger_provider, "resource", None):
                    additional_resource_attributes = {}
                    if service.name not in ("service", "app"):
                        attr_value = logger_provider.resource._attributes.get(RESOURCE_SERVICE_NAME) or ""
                        if attr_value[0:16] in ("", "unknown_service", "unknown_service:"):
                            additional_resource_attributes[RESOURCE_SERVICE_NAME] = service.name
                    attr_value = logger_provider.resource._attributes.get(RESOURCE_SERVICE_INSTANCE_ID) or ""
                    if not attr_value:
                        additional_resource_attributes[RESOURCE_SERVICE_INSTANCE_ID] = service.uuid
                    if additional_resource_attributes:
                        resource = logger_provider.resource.merge(
                            Resource.create({**logger_provider.resource._attributes, **additional_resource_attributes})
                        )
                        logger_provider.resource._attributes = resource._attributes
                        setattr(handler._logger, "_resource", logger_provider.resource)

        tracer = get_tracer("tomodachi", tomodachi_version, tracer_provider)
        meter = get_meter("tomodachi", tomodachi_version, meter_provider)

        if meter and not isinstance(meter, NoOpMeter) and not tracer:
            # collect metrics even if tracing is disabled
            tracer = NoOpTracer()

        aiohttp_pre_middleware = getattr(service, "_aiohttp_pre_middleware", None)
        if aiohttp_pre_middleware is None:
            aiohttp_pre_middleware = []
            setattr(service, "_aiohttp_pre_middleware", aiohttp_pre_middleware)
        if not [m for m in aiohttp_pre_middleware if isinstance(m, OpenTelemetryAioHTTPMiddleware)]:
            aiohttp_pre_middleware.append(
                OpenTelemetryAioHTTPMiddleware(
                    service=service, tracer=tracer, meter=meter, excluded_urls=_excluded_urls
                )
            )

        awssnssqs_message_pre_middleware = getattr(service, "_awssnssqs_message_pre_middleware", None)
        if awssnssqs_message_pre_middleware is None:
            awssnssqs_message_pre_middleware = []
            setattr(service, "_awssnssqs_message_pre_middleware", awssnssqs_message_pre_middleware)
        if not [m for m in awssnssqs_message_pre_middleware if isinstance(m, OpenTelemetryAWSSQSMiddleware)]:
            awssnssqs_message_pre_middleware.append(
                OpenTelemetryAWSSQSMiddleware(service=service, tracer=tracer, meter=meter)
            )

        amqp_message_pre_middleware = getattr(service, "_amqp_message_pre_middleware", None)
        if amqp_message_pre_middleware is None:
            amqp_message_pre_middleware = []
            setattr(service, "_amqp_message_pre_middleware", amqp_message_pre_middleware)
        if not [m for m in amqp_message_pre_middleware if isinstance(m, OpenTelemetryAMQPMiddleware)]:
            amqp_message_pre_middleware.append(OpenTelemetryAMQPMiddleware(service=service, tracer=tracer, meter=meter))

        schedule_pre_middleware = getattr(service, "_schedule_pre_middleware", None)
        if schedule_pre_middleware is None:
            schedule_pre_middleware = []
            setattr(service, "_schedule_pre_middleware", schedule_pre_middleware)
        if not [m for m in schedule_pre_middleware if isinstance(m, OpenTelemetryScheduleFunctionMiddleware)]:
            schedule_pre_middleware.append(
                OpenTelemetryScheduleFunctionMiddleware(service=service, tracer=tracer, meter=meter)
            )

        context = getattr(service, "context", None)
        if context:
            context["_aiohttp_pre_middleware"] = aiohttp_pre_middleware
            context["_awssnssqs_message_pre_middleware"] = awssnssqs_message_pre_middleware
            context["_amqp_message_pre_middleware"] = amqp_message_pre_middleware
            context["_schedule_pre_middleware"] = schedule_pre_middleware
            context["_opentelemetry_tracer"] = tracer
            context["_opentelemetry_meter"] = meter

        setattr(service, "_is_instrumented_by_opentelemetry", True)
        setattr(service, "_opentelemetry_tracer", tracer)
        setattr(service, "_opentelemetry_meter", meter)

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
        setattr(service, "_opentelemetry_meter_provider", None)
        setattr(service, "_opentelemetry_meter", None)
        setattr(service, "_is_instrumented_by_opentelemetry", False)

        context = getattr(service, "context", None)
        if context:
            context["_opentelemetry_tracer"] = None
            context["_opentelemetry_meter"] = None

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
        return ("tomodachi",)

    def _instrument_tomodachi(
        self, tracer_provider: TracerProvider, meter_provider: MeterProvider, excluded_urls: Optional[str]
    ) -> None:
        _InstrumentedTomodachiService._opentelemetry_tracer_provider = tracer_provider
        _InstrumentedTomodachiService._opentelemetry_meter_provider = meter_provider
        _InstrumentedTomodachiService._opentelemetry_excluded_urls = excluded_urls

        from tomodachi import TOMODACHI_CLASSES  # isort:skip

        for cls in TOMODACHI_CLASSES:
            if cls is _InstrumentedTomodachiService:
                continue
            for attr in INSTRUMENTATION_CLASS_ATTRIBUTES:
                setattr(cls, attr, getattr(_InstrumentedTomodachiService, attr, None))

        # @todo this wrapping functionality for the publish methods of aws_sns_sqs and amqp could use some refactoring

        # aws_sns_sqs: _publish_message
        if getattr(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._publish_message, "__wrapped__", None):
            setattr(
                tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport,
                "_publish_message",
                getattr(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._publish_message, "__wrapped__", None),
            )

        aws_sns_sqs_publish_message = tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._publish_message

        @functools.wraps(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._publish_message)
        async def _traced_publish_awssnssqs_message(
            cls: tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport,
            topic_arn: str,
            message: Any,
            message_attributes: Dict,
            context: Dict,
            *args: Any,
            service: Any = None,
            **kwargs: Any,
        ) -> str:
            tracer = (
                cast(Tracer, getattr(service, "_opentelemetry_tracer", None) or context.get("_opentelemetry_tracer"))
                or None
            )
            if not tracer:
                return await aws_sns_sqs_publish_message(
                    topic_arn, message, message_attributes, context, *args, service=service, **kwargs
                )

            topic: str = (
                cls.get_topic_name_without_prefix(cls.decode_topic(cls.get_topic_from_arn(topic_arn)), context)
                if topic_arn
                else ""
            )

            attributes: Dict[str, AttributeValue] = {
                "messaging.system": "aws_sqs",
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
                sns_message_id = await aws_sns_sqs_publish_message(
                    topic_arn, message, message_attributes, context, *args, service=service, **kwargs
                )
                span.set_attribute("messaging.message.id", sns_message_id)
                span.set_status(StatusCode.OK)

            return sns_message_id

        setattr(
            tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport,
            "_publish_message",
            _traced_publish_awssnssqs_message.__get__(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport),
        )

        # aws_sns_sqs: _send_raw_message
        if getattr(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._send_raw_message, "__wrapped__", None):
            setattr(
                tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport,
                "_send_raw_message",
                getattr(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._send_raw_message, "__wrapped__", None),
            )

        aws_sns_sqs_send_raw_message = tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._send_raw_message

        @functools.wraps(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._send_raw_message)
        async def _traced_send_raw_awssqs_message(
            cls: tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport,
            queue_url: str,
            message_body: Any,
            message_attributes: Dict,
            context: Dict,
            *args: Any,
            service: Any = None,
            **kwargs: Any,
        ) -> str:
            tracer = (
                cast(Tracer, getattr(service, "_opentelemetry_tracer", None) or context.get("_opentelemetry_tracer"))
                or None
            )
            if not tracer:
                return await aws_sns_sqs_send_raw_message(
                    queue_url, message_body, message_attributes, context, *args, service=service, **kwargs
                )

            queue_name: str = (
                cls.get_queue_name_without_prefix(cls.get_queue_name_from_queue_url(queue_url), context)
                if queue_url
                else ""
            )

            attributes: Dict[str, AttributeValue] = {
                "messaging.system": "aws_sqs",
                "messaging.operation": "publish",
                "messaging.destination.name": queue_name,
                "messaging.destination.kind": "queue",
            }

            with tracer.start_as_current_span(
                f"{queue_name} publish",
                kind=SpanKind.PRODUCER,
                attributes=attributes,
            ) as span:
                TraceContextTextMapPropagator().inject(carrier=message_attributes)
                sqs_message_id = await aws_sns_sqs_send_raw_message(
                    queue_url, message_body, message_attributes, context, *args, service=service, **kwargs
                )
                span.set_attribute("messaging.message.id", sqs_message_id)
                span.set_status(StatusCode.OK)

            return sqs_message_id

        setattr(
            tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport,
            "_send_raw_message",
            _traced_send_raw_awssqs_message.__get__(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport),
        )

        # amqp: _publish_message
        if getattr(tomodachi.transport.amqp.AmqpTransport._publish_message, "__wrapped__", None):
            setattr(
                tomodachi.transport.amqp.AmqpTransport,
                "_publish_message",
                getattr(tomodachi.transport.amqp.AmqpTransport._publish_message, "__wrapped__", None),
            )

        amqp_publish_message = tomodachi.transport.amqp.AmqpTransport._publish_message

        @functools.wraps(tomodachi.transport.amqp.AmqpTransport._publish_message)
        async def _traced_publish_amqp_message(
            cls: tomodachi.transport.amqp.AmqpTransport,
            routing_key: str,
            exchange_name: str,
            payload: Any,
            properties: Dict,
            routing_key_prefix: Optional[str],
            service: Any,
            context: Dict,
            *args: Any,
            **kwargs: Any,
        ) -> None:
            tracer = (
                cast(Tracer, getattr(service, "_opentelemetry_tracer", None) or context.get("_opentelemetry_tracer"))
                or None
            )
            if not tracer:
                await amqp_publish_message(
                    routing_key,
                    exchange_name,
                    payload,
                    properties,
                    routing_key_prefix,
                    service,
                    context,
                    *args,
                    **kwargs,
                )
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
                await amqp_publish_message(
                    routing_key,
                    exchange_name,
                    payload,
                    properties,
                    routing_key_prefix,
                    service,
                    context,
                    *args,
                    **kwargs,
                )
                span.set_status(StatusCode.OK)

        setattr(
            tomodachi.transport.amqp.AmqpTransport,
            "_publish_message",
            _traced_publish_amqp_message.__get__(tomodachi.transport.amqp.AmqpTransport),
        )

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
        meter_provider: MeterProvider = self._meter_provider(kwargs.get("meter_provider"))
        logger_provider: LoggerProvider = self._logger_provider(kwargs.get("logger_provider"))
        excluded_urls = kwargs.get("excluded_urls")

        self._instrument_tomodachi(tracer_provider, meter_provider, excluded_urls)
        self._instrument_logging(logger_provider)
        self._instrument_structlog_loggers()

    def instrument(self, **kwargs: Any) -> None:
        if not self._is_instrumented_by_opentelemetry or not TomodachiInstrumentor._instrumented_services:
            self._is_instrumented_by_opentelemetry = False
            super().instrument(**kwargs)

    def _uninstrument_tomodachi(self) -> None:
        _InstrumentedTomodachiService._opentelemetry_tracer_provider = None
        _InstrumentedTomodachiService._opentelemetry_meter_provider = None
        _InstrumentedTomodachiService._opentelemetry_excluded_urls = None

        from tomodachi import TOMODACHI_CLASSES  # isort:skip

        for cls in TOMODACHI_CLASSES:
            if cls is _InstrumentedTomodachiService:
                continue
            for attr in INSTRUMENTATION_CLASS_ATTRIBUTES:
                if hasattr(cls, attr):
                    delattr(cls, attr)

        # aws_sns_sqs: _publish_message
        if getattr(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._publish_message, "__wrapped__", None):
            setattr(
                tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport,
                "_publish_message",
                getattr(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._publish_message, "__wrapped__", None),
            )

        # aws_sns_sqs: _send_raw_message
        if getattr(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._send_raw_message, "__wrapped__", None):
            setattr(
                tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport,
                "_send_raw_message",
                getattr(tomodachi.transport.aws_sns_sqs.AWSSNSSQSTransport._send_raw_message, "__wrapped__", None),
            )

        # amqp: _publish_message
        if getattr(tomodachi.transport.amqp.AmqpTransport._publish_message, "__wrapped__", None):
            setattr(
                tomodachi.transport.amqp.AmqpTransport,
                "_publish_message",
                getattr(tomodachi.transport.amqp.AmqpTransport._publish_message, "__wrapped__", None),
            )

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
            tracer_provider = _get_tracer_provider() or _create_tracer_provider()
        return tracer_provider

    @staticmethod
    def _meter_provider(
        meter_provider: Optional[MeterProvider] = None, resource: Optional[Resource] = None
    ) -> MeterProvider:
        if not meter_provider:
            meter_provider = _get_meter_provider() or _create_meter_provider()
        _add_meter_provider_views(meter_provider)
        return meter_provider

    @staticmethod
    def _logger_provider(logger_provider: Optional[LoggerProvider] = None) -> LoggerProvider:
        if not logger_provider:
            logger_provider = _get_logger_provider() or _create_logger_provider()
        return logger_provider


class _InstrumentedTomodachiService(tomodachi.Service):
    _tomodachi_class_is_service_class: bool = False

    _is_instrumented_by_opentelemetry: bool = False
    _opentelemetry_tracer_provider: Optional[TracerProvider] = None
    _opentelemetry_meter_provider: Optional[MeterProvider] = None
    _opentelemetry_excluded_urls: Optional[str] = None

    _opentelemetry_tracer: Optional[Tracer] = None
    _opentelemetry_meter: Optional[Meter] = None

    def __post_init_hook(self) -> None:
        TomodachiInstrumentor.instrument_service(
            self,
            tracer_provider=self._opentelemetry_tracer_provider,
            meter_provider=self._opentelemetry_meter_provider,
            excluded_urls=self._opentelemetry_excluded_urls,
        )

    def __post_teardown_hook(self) -> None:
        TomodachiInstrumentor.uninstrument_service(self)
