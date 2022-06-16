import asyncio
import os
import signal
from typing import Any, Callable, Dict, Tuple, Union

from aiohttp import web

import tomodachi
from tomodachi.discovery.dummy_registry import DummyRegistry
from tomodachi.transport.http import RequestHandler, Response, http, http_error, http_static, websocket


async def middleware_function(
    func: Callable, service: Any, request: web.Request, context: Dict, *args: Any, **kwargs: Any
) -> Any:
    if request.headers.get("X-Use-Middleware") == "Set":
        service.middleware_called = True

    if request.headers.get("X-Use-Middleware") == "Before":
        return "before"

    return_value = await func()

    if request.headers.get("X-Use-Middleware") == "After":
        return "after"

    return return_value


@tomodachi.service
class HttpService(tomodachi.Service):
    name = "test_http"
    discovery = [DummyRegistry]
    options = {"http": {"port": None, "access_log": True, "real_ip_from": "127.0.0.1"}}
    uuid = None
    http_middleware = [middleware_function]
    slow_request = False
    middleware_called = False
    function_triggered = False
    websocket_connected = False
    websocket_received_data = None
    websocket_header = None

    @http("GET", r"/test/?")
    async def test(self, request: web.Request) -> str:
        return_value = "test"
        return return_value

    @http("GET", r"/test/(?P<id>[^/]+?)/?")
    async def test_with_id(self, request: web.Request, id: str) -> str:
        return "test {}".format(id)

    @http("GET", r"/middleware-before/?")
    async def middleware_before(self, request: web.Request) -> str:
        self.function_triggered = True
        return "test"

    @http("GET", r"/slow/?")
    async def test_slow(self, request: web.Request) -> str:
        await asyncio.sleep(2.0)
        self.slow_request = True
        return "test"

    @http(["GET"], r"/dict/?")
    async def test_dict(self, request: web.Request) -> Dict:
        return {"status": 200, "body": "test dict", "headers": {"X-Dict": "test"}}

    @http("GET", r"/tuple/?")
    async def test_tuple(self, request: web.Request) -> Tuple:
        return (200, "test tuple", {"X-Tuple": "test"})

    @http("GET", r"/aiohttp/?")
    async def test_aiohttp(self, request: web.Request) -> web.Response:
        return web.Response(body="test aiohttp", status=200, headers={"X-Aiohttp": "test"})

    @http("GET", r"/same-response/?")
    @http("GET", r"/response/?")
    async def test_response_object(self, request: web.Request) -> Response:
        return Response(body="test tomodachi response", status=200, headers={"X-Tomodachi-Response": "test"})

    @http("GET", r"/exception/?")
    async def test_exception(self, request: web.Request) -> None:
        raise Exception("test")

    @http("GET", r"/slow-exception/?")
    async def test_slow_exception(self, request: web.Request) -> None:
        await asyncio.sleep(2.0)
        raise Exception("test")

    @http("GET", r"/test-weird-content-type/?")
    async def test_weird_content_type(self, request: web.Request) -> web.Response:
        return web.Response(body="test", status=200, headers={"Content-Type": "text/plain; "})

    @http("GET", r"/test-charset/?")
    async def test_charset(self, request: web.Request) -> web.Response:
        return web.Response(body="test", status=200, headers={"Content-Type": "text/plain; charset=utf-8"})

    @http("GET", r"/test-charset-encoding-correct/?")
    async def test_charset_encoding_correct(self, request: web.Request) -> Response:
        return Response(
            body="test \xe5\xe4\xf6", status=200, headers={"Content-Type": "text/plain; charset=iso-8859-1"}
        )

    @http("GET", r"/test-charset-encoding-error/?")
    async def test_charset_encoding_error(self, request: web.Request) -> Response:
        return Response(body="test 友達", status=200, headers={"Content-Type": "text/plain; charset=iso-8859-1"})

    @http("GET", r"/test-charset-invalid/?")
    async def test_charset_invalid(self, request: web.Request) -> Response:
        return Response(body="test", status=200, headers={"Content-Type": "text/plain; charset=utf-9"})

    @http("GET", r"/empty-data/?")
    async def empty_data(self, request: web.Request) -> str:
        return ""

    @http("GET", r"/byte-data/?")
    async def byte_data(self, request: web.Request) -> bytes:
        return b"test \xc3\xa5\xc3\xa4\xc3\xb6"

    @http("GET", r"/none-data/?")
    async def none_data(self, request: web.Request) -> None:
        return None

    @http("GET", r"/forwarded-for/?")
    async def forwarded_for(self, request: web.Request) -> str:
        return RequestHandler.get_request_ip(request) or ""

    @http("GET", r"/authorization/?")
    async def authorization(self, request: web.Request) -> str:
        return request._cache.get("auth").login if request._cache.get("auth") else ""

    @http_static("../static_files", r"/static/")
    async def static_files_filename_append(self) -> None:
        pass

    @http_static("../static_files", r"/download/(?P<filename>[^/]+?)/image")
    async def static_files_filename_existing(self) -> None:
        pass

    @http_error(status_code=404)
    async def test_404(self, request: web.Request) -> str:
        return "test 404"

    @websocket(r"/websocket-simple")
    async def websocket_simple(self, websocket: web.WebSocketResponse) -> None:
        self.websocket_connected = True

    @websocket(r"/websocket-header")
    async def websocket_with_header(self, websocket: web.WebSocketResponse, request: web.Request) -> None:
        self.websocket_header = request.headers.get("User-Agent")

    @websocket(r"/websocket-data")
    async def websocket_data(self, websocket: web.WebSocketResponse) -> Callable:
        async def _receive(data: Union[str, bytes]) -> None:
            self.websocket_received_data = data

        return _receive
