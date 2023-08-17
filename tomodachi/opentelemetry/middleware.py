import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, cast

from aiohttp import hdrs, web
from yarl import URL

from opentelemetry import trace
from opentelemetry.semconv.trace import MessagingOperationValues, SpanAttributes
from opentelemetry.trace.propagation.tracecontext import Context, TraceContextTextMapPropagator
from opentelemetry.util.http import remove_url_credentials
from tomodachi.__version__ import __version__ as tomodachi_version
from tomodachi.transport.aws_sns_sqs import MessageAttributesType
from tomodachi.transport.http import get_forwarded_remote_ip


@web.middleware
class OpenTelemetryAioHTTPMiddleware:
    def __init__(self, service: Any, tracer_provider: Optional[trace.TracerProvider] = None) -> None:
        self.service = service
        self.tracer = trace.get_tracer("tomodachi.opentelemetry", tomodachi_version, tracer_provider)

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
        http_url = str(request.url)
        if not host:
            http_url = str(
                URL.build(scheme=request.scheme, host=(server_ip or "127.0.0.1"), port=server_port).join(
                    request.rel_url
                )
            )

        port = int(host.split(":")[1]) if host and ":" in host else 80

        ctx = TraceContextTextMapPropagator().extract(carrier=request.headers)
        response: Optional[web.Response] = None

        if route:
            span_name = f"{request.method} {route}"
        else:
            span_name = f"{request.method} {request.path}"

        attributes = {}

        if request.method:
            attributes["http.request.method"] = request.method

        if route:
            attributes["http.route"] = route

        if host is not None:
            attributes["server.address"] = host.split(":")[0]
            attributes["server.port"] = port
        else:
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
                if response is not None:
                    span.set_attribute("http.response.status_code", response.status)
                    if response.status == 499:
                        replaced_status_code = getattr(response, "_replaced_status_code", None)
                        if replaced_status_code:
                            span.set_attribute("http.response.replaced_status_code", replaced_status_code)
                else:
                    span.set_attribute("http.response.status_code", 500)

                if response is None or response.status < 100 or response.status >= 500:
                    span.set_status(trace.StatusCode.ERROR)

        if response is None:
            response = web.HTTPInternalServerError()
            response.body = b""
            response.headers[hdrs.CONNECTION] = "close"
            response.force_close()

        if isinstance(response, (web.HTTPException, web.HTTPInternalServerError)):
            raise response

        return response


class OpenTelemetryAWSSQSMiddleware:
    def __init__(self, service: Any, tracer_provider: Optional[trace.TracerProvider] = None) -> None:
        self.service = service
        self.tracer = trace.get_tracer("tomodachi.opentelemetry", tomodachi_version, tracer_provider)

    async def __call__(
        self,
        handler: Callable[..., Awaitable[web.Response]],
        *,
        topic: str = "",
        queue_url: str = "",
        message_attributes: Optional[MessageAttributesType] = None,
        sns_message_id: str = "",
    ) -> None:
        if getattr(self.service, "_is_instrumented_by_opentelemetry", False) is False:
            await handler()
            return

        if not topic and not queue_url and message_attributes is None and not sns_message_id:
            # not originating from aws_sns_sqs transport
            await handler()
            return

        if message_attributes is None:
            message_attributes = {}

        queue_name = queue_url.rsplit("/")[-1]

        ctx = TraceContextTextMapPropagator().extract(carrier=message_attributes)

        with self.tracer.start_as_current_span(
            name=f"{topic} process",
            kind=trace.SpanKind.CONSUMER,
            context=ctx,
        ) as span:
            span.set_attribute("messaging.system", "AmazonSQS")
            span.set_attribute("messaging.operation", "process")
            span.set_attribute("messaging.destination.name", topic)
            span.set_attribute("messaging.destination.kind", "topic")
            span.set_attribute("messaging.source.name", queue_name)
            span.set_attribute("messaging.source.kind", "queue")
            span.set_attribute("messaging.message.id", sns_message_id)

            await handler()

            span.set_status(trace.StatusCode.OK)
