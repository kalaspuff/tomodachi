import re
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, cast

from aiohttp import hdrs, web

from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.util.types import AttributeValue
from tomodachi.__version__ import __version__ as tomodachi_version
from tomodachi.transport.aws_sns_sqs import MessageAttributesType
from tomodachi.transport.http import get_forwarded_remote_ip


@web.middleware
class OpenTelemetryAioHTTPMiddleware:
    def __init__(
        self,
        service: Any,
        tracer: Optional[trace.Tracer] = None,
        tracer_provider: Optional[trace.TracerProvider] = None,
    ) -> None:
        self.service = service
        self.tracer = tracer or trace.get_tracer("tomodachi.opentelemetry", tomodachi_version, tracer_provider)

    def get_route(self, request: web.Request) -> Optional[str]:
        route: Optional[str]
        try:
            route = getattr(request.match_info.route._resource, "_simplified_pattern", None)
        except Exception:
            route = None

        if not route:
            pattern = request.match_info.route.get_info().get("pattern", None)
            if not pattern:
                return None
            simplified = re.compile(r"^\^?(.+?)\$?$").match(pattern.pattern)
            route = simplified.group(1) if simplified else None

        return route

    async def __call__(
        self,
        request: web.Request,
        handler: Callable[..., Awaitable[web.Response]],
    ) -> web.Response:
        if getattr(self.service, "_is_instrumented_by_opentelemetry", False) is False:
            return await handler(request)

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

        host = request.headers.get(hdrs.HOST, None)
        port = int(host.split(":")[1]) if host and ":" in host else 80

        if route:
            span_name = f"{request.method} {route}"
        else:
            span_name = f"{request.method} {request.path}"

        attributes: Dict[str, AttributeValue] = {}

        if request.method:
            attributes["http.request.method"] = request.method

        if route:
            attributes["http.route"] = route

        if host is not None:
            attributes["server.address"] = host.split(":")[0]
            attributes["server.port"] = port
        else:
            if server_ip:
                attributes["server.address"] = server_ip
            attributes["server.port"] = server_port or port

        attributes["url.scheme"] = request.scheme
        attributes["url.path"] = request.path

        if request.query_string:
            attributes["url.query"] = request.query_string

        user_agent = request.headers.get(hdrs.USER_AGENT, None)
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

        ctx = TraceContextTextMapPropagator().extract(carrier=request.headers)
        response: Optional[web.Response] = None

        with self.tracer.start_as_current_span(
            name=span_name,
            kind=trace.SpanKind.SERVER,
            context=ctx,
            attributes=attributes,
        ) as span:
            try:
                response = await handler(request)
            except web.HTTPException as exc:
                response = exc
                if exc.status < 100 or exc.status >= 500:
                    raise
            finally:
                if (
                    response is not None
                    and isinstance(getattr(response, "status", None), int)
                    and response.status >= 100
                    and response.status <= 599
                ):
                    span.set_attribute("http.response.status_code", response.status)
                    if response.status == 499:
                        replaced_status_code = getattr(response, "_replaced_status_code", None)
                        if replaced_status_code:
                            span.set_attribute("http.response.replaced_status_code", replaced_status_code)
                else:
                    span.set_attribute("http.response.status_code", 500)
                    span.set_status(trace.StatusCode.ERROR)
                    response = None

        if response is None:
            response = web.HTTPInternalServerError()
            response.body = b""
            response.headers[hdrs.CONNECTION] = "close"
            response.force_close()

        if isinstance(response, (web.HTTPException, web.HTTPInternalServerError)):
            raise response

        return response


class OpenTelemetryAWSSQSMiddleware:
    def __init__(
        self,
        service: Any,
        tracer: Optional[trace.Tracer] = None,
        tracer_provider: Optional[trace.TracerProvider] = None,
    ) -> None:
        self.service = service
        self.tracer = tracer or trace.get_tracer("tomodachi.opentelemetry", tomodachi_version, tracer_provider)

    async def __call__(
        self,
        handler: Callable[..., Awaitable[web.Response]],
        *,
        topic: str,
        queue_url: str,
        message_attributes: MessageAttributesType,
        sns_message_id: str,
        sqs_message_id: str,
    ) -> None:
        if getattr(self.service, "_is_instrumented_by_opentelemetry", False) is False:
            await handler()
            return

        queue_name = queue_url.rsplit("/")[-1]

        attributes: Dict[str, AttributeValue] = {
            "messaging.system": "AmazonSQS",
            "messaging.operation": "process",
            "messaging.source.name": queue_name,
            "messaging.source.kind": "queue",
            "messaging.message.id": sns_message_id or sqs_message_id,
        }

        if topic:
            attributes["messaging.destination.name"] = topic
            attributes["messaging.destination.kind"] = "topic"
        else:
            attributes["messaging.destination.name"] = queue_name
            attributes["messaging.destination.kind"] = "queue"

        ctx = TraceContextTextMapPropagator().extract(carrier=message_attributes)

        with self.tracer.start_as_current_span(
            name=f"{topic} process",
            kind=trace.SpanKind.CONSUMER,
            context=ctx,
            attributes=attributes,
        ) as span:
            await handler()
            span.set_status(trace.StatusCode.OK)


class OpenTelemetryAMQPMiddleware:
    def __init__(
        self,
        service: Any,
        tracer: Optional[trace.Tracer] = None,
        tracer_provider: Optional[trace.TracerProvider] = None,
    ) -> None:
        self.service = service
        self.tracer = tracer or trace.get_tracer("tomodachi.opentelemetry", tomodachi_version, tracer_provider)

    async def __call__(
        self,
        handler: Callable[..., Awaitable[web.Response]],
        *,
        routing_key: str,
        exchange_name: str,
        properties: Any,
    ) -> None:
        if getattr(self.service, "_is_instrumented_by_opentelemetry", False) is False:
            await handler()
            return

        if not exchange_name:
            exchange_name = "amq.topic"

        attributes: Dict[str, AttributeValue] = {
            "messaging.system": "rabbitmq",
            "messaging.operation": "process",
            "messaging.destination.name": exchange_name,
            "messaging.rabbitmq.destination.routing_key": routing_key,
        }

        headers = getattr(properties, "headers", {})
        if not isinstance(headers, dict):
            headers = {}
        ctx = TraceContextTextMapPropagator().extract(carrier=headers)

        with self.tracer.start_as_current_span(
            name=f"{routing_key} process",
            kind=trace.SpanKind.CONSUMER,
            context=ctx,
            attributes=attributes,
        ) as span:
            await handler()
            span.set_status(trace.StatusCode.OK)


class OpenTelemetryScheduleFunctionMiddleware:
    def __init__(
        self,
        service: Any,
        tracer: Optional[trace.Tracer] = None,
        tracer_provider: Optional[trace.TracerProvider] = None,
    ) -> None:
        self.service = service
        self.tracer = tracer or trace.get_tracer("tomodachi.opentelemetry", tomodachi_version, tracer_provider)

    async def __call__(
        self,
        handler: Callable[..., Awaitable[web.Response]],
        *,
        invocation_time: str = "",
        interval: str = "",
    ) -> None:
        if getattr(self.service, "_is_instrumented_by_opentelemetry", False) is False:
            await handler()
            return

        attributes: Dict[str, AttributeValue] = {
            "function.name": handler.__name__,
            "function.trigger": "timer",
            "function.time": invocation_time,
        }

        if interval:
            attributes["function.interval"] = str(interval)

        with self.tracer.start_as_current_span(
            name=handler.__name__,
            kind=trace.SpanKind.INTERNAL,
            attributes=attributes,
        ) as span:
            await handler()
            span.set_status(trace.StatusCode.OK)
