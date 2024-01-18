import re
from time import time_ns
from traceback import format_exception
from typing import Any, Awaitable, Callable, Dict, Mapping, NamedTuple, Optional, Tuple, Type, TypeVar, cast

from aiohttp import hdrs, web
from opentelemetry import metrics, trace
from opentelemetry.metrics._internal.instrument import Instrument
from opentelemetry.sdk.metrics import Meter
from opentelemetry.sdk.metrics._internal.instrument import _Histogram, _UpDownCounter
from opentelemetry.sdk.trace import Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.util.http import ExcludeList
from opentelemetry.util.types import AttributeValue

from tomodachi._exception import limit_exception_traceback
from tomodachi.logging import get_logger
from tomodachi.transport.aws_sns_sqs import AWSSNSSQSTransport, MessageAttributesType
from tomodachi.transport.http import get_forwarded_remote_ip

IT = TypeVar("IT", bound=Instrument)


class InstrumentOptions(NamedTuple):
    name: str
    unit: str
    description: str
    attribute_keys: Tuple[str, ...]


class OpenTelemetryTomodachiMiddleware:
    service: Any
    service_context: Dict
    tracer: Optional[trace.Tracer]
    meter: Optional[metrics.Meter]

    duration_histogram_options: InstrumentOptions
    active_tasks_counter_options: InstrumentOptions

    _duration_histogram: Optional[metrics.Histogram] = None
    _active_tasks_counter: Optional[metrics.UpDownCounter] = None

    def __init__(
        self, service: Any, tracer: Optional[trace.Tracer] = None, meter: Optional[metrics.Meter] = None, **kwargs: Any
    ) -> None:
        self.service = service
        self.service_context = getattr(service, "context", {})
        self.tracer = tracer
        self.meter = meter

        if meter:
            self._duration_histogram = self._get_instrument(_Histogram, *self.duration_histogram_options[0:3])
            self._active_tasks_counter = self._get_instrument(_UpDownCounter, *self.active_tasks_counter_options[0:3])

    def _get_instrument(self, type_: Type[IT], name: str, unit: str, description: str) -> Optional[IT]:
        meter = cast(Meter, self.meter)
        (is_registered, instrument_id) = meter._is_instrument_registered(name, type_, unit, description)

        if not is_registered:
            with meter._instrument_ids_lock:
                try:
                    meter._instrument_ids.remove(instrument_id)
                except KeyError:
                    pass

            if type_ is _Histogram:
                return cast(IT, meter.create_histogram(name, unit, description))
            elif type_ is _UpDownCounter:
                return cast(IT, meter.create_up_down_counter(name, unit, description))
            else:
                get_logger("tomodachi.opentelemetry").warning(
                    "unsupported instrument type",
                    instrument_name=name,
                    instrument_unit=unit,
                    instrument_description=description,
                    instrument_type=getattr(type_, "__name__", type(type_).__name__),
                )
                raise Exception("unsupported instrument type")

        with meter._instrument_id_instrument_lock:
            return cast(IT, meter._instrument_id_instrument[instrument_id])

    def increase_active_tasks(
        self,
        attributes: Optional[Mapping[str, AttributeValue]],
        extra_attributes: Optional[Dict[str, AttributeValue]] = None,
        *,
        value: int = 1,
    ) -> None:
        if self._active_tasks_counter and attributes:
            attribute_keys = self.active_tasks_counter_options.attribute_keys
            attributes_ = {k: attributes[k] for k in attribute_keys if k in attributes}
            if extra_attributes:
                attributes_.update(extra_attributes)
            self._active_tasks_counter.add(value, attributes_)

    def decrease_active_tasks(
        self,
        attributes: Optional[Mapping[str, AttributeValue]],
        extra_attributes: Optional[Dict[str, AttributeValue]] = None,
        *,
        value: int = -1,
    ) -> None:
        self.increase_active_tasks(attributes, extra_attributes, value=value)

    def record_duration(
        self,
        start_time: Optional[int],
        end_time: Optional[int],
        attributes: Optional[Mapping[str, AttributeValue]],
        extra_attributes: Optional[Dict[str, AttributeValue]] = None,
    ) -> None:
        if self._duration_histogram and start_time and end_time and attributes:
            attribute_keys = self.duration_histogram_options.attribute_keys
            attributes_ = {k: attributes[k] for k in attribute_keys if k in attributes}
            if extra_attributes:
                attributes_.update(extra_attributes)

            duration_ns = end_time - start_time
            duration = duration_ns / 1e9

            self._duration_histogram.record(duration, attributes_)


@web.middleware
class OpenTelemetryAioHTTPMiddleware(OpenTelemetryTomodachiMiddleware):
    duration_histogram_options = InstrumentOptions(
        "http.server.duration",
        "s",
        "Measures the duration of inbound HTTP requests.",
        (
            "http.route",
            "http.request.method",
            "http.response.status_code",
            "network.protocol.name",
            "network.protocol.version",
            "server.address",
            "server.port",
            "url.scheme",
        ),
    )
    active_tasks_counter_options = InstrumentOptions(
        "http.server.active_requests",
        "{request}",
        "Measures the number of concurrent HTTP requests that are currently in-flight.",
        (
            "http.request.method",
            "server.address",
            "server.port",
            "url.scheme",
        ),
    )

    def __init__(
        self,
        service: Any,
        tracer: Optional[trace.Tracer] = None,
        meter: Optional[metrics.Meter] = None,
        excluded_urls: Optional[ExcludeList] = None,
    ) -> None:
        super().__init__(service, tracer, meter)
        self.excluded_urls = excluded_urls

    def get_route(self, request: web.Request) -> Optional[str]:
        route: Optional[str]
        try:
            route = getattr(request.match_info.route._resource, "_simplified_pattern", None)
        except Exception:
            route = None

        if not route:
            pattern = request.match_info.route.get_info().get("pattern")
            if not pattern:
                return None
            simplified = re.compile(r"^\^?(.+?)\$?$").match(pattern.pattern)
            route = simplified.group(1) if simplified else None

        return route

    def get_attributes(self, request: web.Request) -> Dict[str, AttributeValue]:
        protocol_version = ".".join(map(str, request.version))
        route: Optional[str] = self.get_route(request)

        client_socket_addr = None
        client_socket_port = None
        if request._transport_peername:
            client_socket_addr, client_socket_port = cast(Tuple[str, int], request._transport_peername)

        server_ip = None
        server_port = None
        if request.transport:
            sock = request.transport.get_extra_info("socket")
            if sock:
                sockname = sock.getsockname()
                if sockname:
                    server_ip, server_port = cast(Tuple[str, int], sockname)

        host = request.headers.get(hdrs.HOST)
        port = int(host.split(":")[1]) if host and ":" in host else 80

        attributes: Dict[str, AttributeValue] = {}

        if request.method:
            attributes["http.request.method"] = request.method

        if route:
            attributes["http.route"] = route

        attributes["server.address"] = host.split(":")[0] if host is not None else (server_ip or "127.0.0.1")
        attributes["server.port"] = port if host is not None else (server_port or port)

        attributes["url.scheme"] = request.scheme
        attributes["url.path"] = request.path

        if request.query_string:
            attributes["url.query"] = request.query_string

        user_agent = request.headers.get(hdrs.USER_AGENT)
        if user_agent:
            attributes["user_agent.original"] = user_agent

        attributes["client.address"] = get_forwarded_remote_ip(request)

        if client_socket_addr and client_socket_port:
            attributes["client.socket.address"] = client_socket_addr
            attributes["client.socket.port"] = client_socket_port

        if server_ip:
            attributes["server.socket.address"] = server_ip

        attributes["server.socket.port"] = server_port or port
        attributes["network.protocol.version"] = protocol_version
        attributes["network.protocol.name"] = "http"

        return attributes

    async def __call__(
        self,
        request: web.Request,
        handler: Callable[..., Awaitable[web.Response]],
    ) -> web.Response:
        try:
            return await self.handle(request, handler)
        except web.HTTPException:
            raise
        except Exception as exc:
            get_logger("exception").exception(f"uncaught exception: {str(exc)}")
            raise

    async def handle(
        self,
        request: web.Request,
        handler: Callable[..., Awaitable[web.Response]],
    ) -> web.Response:
        exclude_instrumentation: bool = any(
            [
                getattr(self.service, "_is_instrumented_by_opentelemetry", False) is False,
                self.excluded_urls and self.excluded_urls.url_disabled(request.path),
            ]
        )
        if exclude_instrumentation or not self.tracer:
            return await handler(request)

        start_time = time_ns()

        attributes = self.get_attributes(request)
        route = cast(Optional[str], attributes.get("http.route"))
        ctx = TraceContextTextMapPropagator().extract(carrier=request.headers)
        response: Optional[web.Response] = None

        span = cast(
            Span,
            self.tracer.start_span(
                name=f"{request.method} {route}" if route else request.method,
                kind=trace.SpanKind.SERVER,
                context=ctx,
                attributes=attributes,
                start_time=start_time,
            ),
        )
        with trace.use_span(span, end_on_exit=False):
            try:
                self.increase_active_tasks(attributes)
                response = await handler(request)
            except web.HTTPException as exc:
                response = exc
                if exc.status < 100 or exc.status >= 500:
                    raise
            finally:
                response_status_code: int
                if (
                    response is not None
                    and isinstance(getattr(response, "status", None), int)
                    and response.status >= 100
                    and response.status <= 599
                ):
                    response_status_code = response.status
                    if response.status >= 500:
                        span.set_status(trace.StatusCode.ERROR)
                    if response.status == 499:
                        replaced_status_code = getattr(response, "_replaced_status_code", None)
                        if replaced_status_code:
                            span.set_status(
                                trace.StatusCode.ERROR,
                                "Client closed the connection while the server was still processing the request.",
                            )
                            response_status_code = replaced_status_code
                        else:
                            span.set_status(
                                trace.StatusCode.ERROR,
                                "Client closed the connection before the server could start processing the request.",
                            )

                    caught_exceptions = getattr(response, "_caught_exceptions", None)
                    if caught_exceptions:
                        for exception in caught_exceptions:
                            span.record_exception(
                                exception,
                                {
                                    "exception.stacktrace": "".join(
                                        format_exception(type(exception), exception, exception.__traceback__)
                                    )
                                },
                            )
                else:
                    response_status_code = 500
                    span.set_status(trace.StatusCode.ERROR)
                    response = None

                span.set_attribute("http.response.status_code", response_status_code)

                self.decrease_active_tasks(attributes)
                end_time = span.end_time if span.is_recording() and span.end_time else time_ns()
                self.record_duration(
                    start_time, end_time, attributes, {"http.response.status_code": response_status_code}
                )
                span.end(end_time=end_time)

        if response is None:
            response = web.HTTPInternalServerError()
            response.body = b""
            response.headers[hdrs.CONNECTION] = "close"
            response.force_close()

        if isinstance(response, (web.HTTPException, web.HTTPInternalServerError)):
            raise response

        return response


class OpenTelemetryAWSSQSMiddleware(OpenTelemetryTomodachiMiddleware):
    duration_histogram_options = InstrumentOptions(
        "messaging.aws_sqs.duration",
        "s",
        "Measures the duration of processing a message by the handler function.",
        (
            "messaging.destination.name",
            "messaging.destination.kind",
            "messaging.destination_publish.name",
            "messaging.destination_publish.kind",
            "code.function",
        ),
    )
    active_tasks_counter_options = InstrumentOptions(
        "messaging.aws_sqs.active_tasks",
        "{message}",
        "Measures the number of concurrent SQS messages that are currently being processed.",
        (
            "messaging.destination.name",
            "messaging.destination.kind",
            "messaging.destination_publish.name",
            "messaging.destination_publish.kind",
            "code.function",
        ),
    )

    async def __call__(
        self,
        handler: Callable[..., Awaitable[None]],
        *,
        topic: str,
        queue_url: str,
        message_attributes: MessageAttributesType,
        sns_message_id: str,
        sqs_message_id: str,
    ) -> None:
        if getattr(self.service, "_is_instrumented_by_opentelemetry", False) is False or not self.tracer:
            return await handler()

        start_time = time_ns()

        queue_name: str = AWSSNSSQSTransport.get_queue_name_without_prefix(
            AWSSNSSQSTransport.get_queue_name_from_queue_url(queue_url), self.service_context
        )

        attributes: Dict[str, AttributeValue] = {
            "messaging.system": "aws_sqs",
            "messaging.operation": "process",
            "messaging.destination.name": queue_name,
            "messaging.destination.kind": "queue",
            "messaging.message.id": sns_message_id or sqs_message_id,
            "messaging.destination_publish.name": topic if topic else queue_name,
            "messaging.destination_publish.kind": "topic" if topic else "queue",
            "code.function": handler.__name__,
        }

        ctx = TraceContextTextMapPropagator().extract(carrier=message_attributes)

        span = cast(
            Span,
            self.tracer.start_span(
                name=f"{topic} process",
                kind=trace.SpanKind.CONSUMER,
                context=ctx,
                attributes=attributes,
                start_time=start_time,
            ),
        )
        with trace.use_span(span, end_on_exit=False):
            function_success: bool = True
            try:
                self.increase_active_tasks(attributes)
                await handler()
                span.set_status(trace.StatusCode.OK)
            except Exception as exc:
                function_success = False
                span.set_status(trace.StatusCode.ERROR)
                limit_exception_traceback(exc, ("tomodachi.transport.aws_sns_sqs", "tomodachi.helpers.middleware"))
                span.record_exception(
                    exc,
                    {"exception.stacktrace": "".join(format_exception(type(exc), exc, exc.__traceback__))},
                    escaped=True,
                )
                raise
            finally:
                self.decrease_active_tasks(attributes)
                end_time = span.end_time if span.is_recording() and span.end_time else time_ns()
                self.record_duration(start_time, end_time, attributes, {"function.success": function_success})
                span.end(end_time=end_time)


class OpenTelemetryAMQPMiddleware(OpenTelemetryTomodachiMiddleware):
    duration_histogram_options = InstrumentOptions(
        "messaging.rabbitmq.duration",
        "s",
        "Measures the duration of processing a message by the handler function.",
        (
            "messaging.destination.name",
            "messaging.rabbitmq.destination.routing_key",
            "code.function",
        ),
    )
    active_tasks_counter_options = InstrumentOptions(
        "messaging.rabbitmq.active_tasks",
        "{message}",
        "Measures the number of concurrent AMQP messages that are currently being processed.",
        (
            "messaging.destination.name",
            "messaging.rabbitmq.destination.routing_key",
            "code.function",
        ),
    )

    async def __call__(
        self,
        handler: Callable[..., Awaitable[None]],
        *,
        routing_key: str,
        exchange_name: str,
        properties: Any,
    ) -> None:
        if getattr(self.service, "_is_instrumented_by_opentelemetry", False) is False or not self.tracer:
            return await handler()

        start_time = time_ns()

        if not exchange_name:
            exchange_name = "amq.topic"

        attributes: Dict[str, AttributeValue] = {
            "messaging.system": "rabbitmq",
            "messaging.operation": "process",
            "messaging.destination.name": exchange_name,
            "messaging.rabbitmq.destination.routing_key": routing_key,
            "code.function": handler.__name__,
        }

        headers = getattr(properties, "headers", {})
        if not isinstance(headers, dict):
            headers = {}
        ctx = TraceContextTextMapPropagator().extract(carrier=headers)

        span = cast(
            Span,
            self.tracer.start_span(
                name=f"{routing_key} process",
                kind=trace.SpanKind.CONSUMER,
                context=ctx,
                attributes=attributes,
                start_time=start_time,
            ),
        )
        with trace.use_span(span, end_on_exit=False):
            function_success: bool = True
            try:
                self.increase_active_tasks(attributes)
                await handler()
                span.set_status(trace.StatusCode.OK)
            except Exception as exc:
                function_success = False
                span.set_status(trace.StatusCode.ERROR)
                limit_exception_traceback(exc, ("tomodachi.transport.amqp", "tomodachi.helpers.middleware"))
                span.record_exception(
                    exc,
                    {"exception.stacktrace": "".join(format_exception(type(exc), exc, exc.__traceback__))},
                    escaped=True,
                )
                raise
            finally:
                self.decrease_active_tasks(attributes)
                end_time = span.end_time if span.is_recording() and span.end_time else time_ns()
                self.record_duration(start_time, end_time, attributes, {"function.success": function_success})
                span.end(end_time=end_time)


class OpenTelemetryScheduleFunctionMiddleware(OpenTelemetryTomodachiMiddleware):
    duration_histogram_options = InstrumentOptions(
        "function.duration", "s", "Measures the duration of running the scheduled handler function.", ("code.function",)
    )
    active_tasks_counter_options = InstrumentOptions(
        "function.active_tasks",
        "{task}",
        "Measures the number of concurrent invocations of the scheduled handler that is currently running.",
        ("code.function",),
    )

    async def __call__(
        self,
        handler: Callable[..., Awaitable[None]],
        *,
        invocation_time: str = "",
        interval: str = "",
    ) -> None:
        if getattr(self.service, "_is_instrumented_by_opentelemetry", False) is False or not self.tracer:
            return await handler()

        start_time = time_ns()

        attributes: Dict[str, AttributeValue] = {
            "code.function": handler.__name__,
            "function.trigger": "timer",
            "function.time": invocation_time,
        }

        if interval:
            attributes["function.interval"] = str(interval)

        span = cast(
            Span,
            self.tracer.start_span(
                name=handler.__name__,
                kind=trace.SpanKind.INTERNAL,
                attributes=attributes,
                start_time=start_time,
            ),
        )
        with trace.use_span(span, end_on_exit=False):
            function_success: bool = True
            try:
                self.increase_active_tasks(attributes)
                await handler()
                span.set_status(trace.StatusCode.OK)
            except Exception as exc:
                function_success = False
                span.set_status(trace.StatusCode.ERROR)
                limit_exception_traceback(exc, ("tomodachi.transport.schedule", "tomodachi.helpers.middleware"))
                span.record_exception(
                    exc,
                    {"exception.stacktrace": "".join(format_exception(type(exc), exc, exc.__traceback__))},
                    escaped=True,
                )
                raise
            finally:
                self.decrease_active_tasks(attributes)
                end_time = span.end_time if span.is_recording() and span.end_time else time_ns()
                self.record_duration(start_time, end_time, attributes, {"function.success": function_success})
                span.end(end_time=end_time)
