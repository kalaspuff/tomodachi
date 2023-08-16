import re
from typing import Any, Awaitable, Callable, Optional, Tuple, cast

from aiohttp import hdrs, web
from opentelemetry import trace
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.util.http import remove_url_credentials
from yarl import URL

from tomodachi.__version__ import __version__ as tomodachi_version
from tomodachi.transport.http import get_forwarded_remote_ip


@web.middleware
class OpenTelemetryHTTPMiddleware:
    def __init__(self, tracer_provider: Optional[trace.TracerProvider] = None) -> None:
        self.tracer = trace.get_tracer("tomodachi.telemetry", tomodachi_version, tracer_provider)

    def extract_status_code(self, response: Any) -> int:
        if isinstance(response, int):
            return response
        if isinstance(response, (str, bytes)):
            return 200
        if isinstance(response, (list, tuple)):
            try:
                return int(response[0])
            except (IndexError, ValueError):
                return 0
        if isinstance(response, dict):
            try:
                return int(response.get("status", 0))
            except ValueError:
                return 0
        if isinstance(response, web.Response):
            return cast(int, response.status)
        return 0

    # def extract_route(self, request: web.Request) -> str:
    #     route_fallback_pattern = re.compile("unknown")
    #     route_pattern: re.Pattern = request.match_info.route.get_info().get("pattern", route_fallback_pattern)
    #     print(request.match_info.route.get_info())
    #     print(route_pattern)
    #     simplified = re.compile(r"^\^?(.+?)\$?$").match(route_pattern.pattern)
    #     print(simplified.group(1))
    #     return simplified.group(1) if simplified else route_fallback_pattern.pattern

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
        protocol_version = ".".join(map(str, request.version))
        route: Optional[str] = self.get_route(request)

        peer_ip = None
        peer_port = None
        if request._transport_peername:
            peer_ip, peer_port = cast(Tuple[str, int], request._transport_peername)

        host_ip = None
        host_port = None
        if request.transport:
            sock = request.transport.get_extra_info("socket")
            if sock:
                sockname = sock.getsockname()
                if sockname:
                    host_ip, host_port = cast(Tuple[str, int], sockname)

        host = request.headers.get(hdrs.HOST, None)
        http_url = str(request.url)
        if not host:
            http_url = str(
                URL.build(scheme=request.scheme, host=(host_ip or "127.0.0.1"), port=host_port).join(request.rel_url)
            )

        port = int(host.split(":")[1]) if host and ":" in host else 80

        # http_url = str(
        #     request.url
        #     if host
        #     else URL.build(scheme=request.scheme, host=(host_ip or "127.0.0.1"), port=host_port).join(request.rel_url)
        # )

        ctx = TraceContextTextMapPropagator().extract(carrier=request.headers)
        response: Optional[web.Response] = None

        with self.tracer.start_as_current_span(
            name=f"{request.method} {request.path}",
            kind=trace.SpanKind.SERVER,
            context=ctx,
        ) as span:
            span.set_attribute(SpanAttributes.HTTP_SCHEME, request.scheme)

            if host is not None:
                span.set_attribute(SpanAttributes.HTTP_HOST, host)

            if host_ip:
                span.set_attribute(SpanAttributes.NET_HOST_IP, host_ip)

            span.set_attribute(SpanAttributes.NET_HOST_PORT, host_port or port)

            span.set_attribute(SpanAttributes.HTTP_FLAVOR, protocol_version)
            span.set_attribute(SpanAttributes.HTTP_TARGET, request.path)
            span.set_attribute(SpanAttributes.HTTP_URL, remove_url_credentials(http_url))

            if request.method:
                span.set_attribute(SpanAttributes.HTTP_METHOD, request.method)

            user_agent = request.headers.get(hdrs.USER_AGENT, None)
            if user_agent:
                span.set_attribute(SpanAttributes.HTTP_USER_AGENT, user_agent)

            span.set_attribute(SpanAttributes.HTTP_CLIENT_IP, get_forwarded_remote_ip(request))

            if peer_ip and peer_port:
                span.set_attribute(SpanAttributes.NET_PEER_IP, peer_ip)
                span.set_attribute(SpanAttributes.NET_PEER_PORT, peer_port)

            if route:
                span.set_attribute(SpanAttributes.HTTP_ROUTE, route)

            try:
                response = await handler(request)
            except web.HTTPException as exc:
                response = exc
                if exc.status < 100 or exc.status >= 500:
                    raise
            finally:
                if response is not None:
                    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status)
                    if response.status == 499:
                        replaced_status_code = getattr(response, "_replaced_status_code", None)
                        if replaced_status_code:
                            span.set_attribute("http.replaced_status_code", replaced_status_code)
                else:
                    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 500)

                if response is None or response.status < 100 or response.status >= 500:
                    span.set_status(trace.StatusCode.ERROR)
                else:
                    span.set_status(trace.StatusCode.OK)

        if response is None:
            response = web.HTTPInternalServerError()
            response.body = b""
            response.headers[hdrs.CONNECTION] = "close"
            response.force_close()

        if isinstance(response, (web.HTTPException, web.HTTPInternalServerError)):
            raise response

        return response
