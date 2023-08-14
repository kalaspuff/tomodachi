import os
import uuid
from typing import Callable, Tuple, Union

from aiohttp import web
from aiohttp.web_fileresponse import FileResponse

import tomodachi
from tomodachi import Options, http, http_error, http_static, websocket


class ExampleWebsocketService(tomodachi.Service):
    name = "example-websocket-service"

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = Options(
        http=Options.HTTP(
            port=4711,
            content_type="text/plain; charset=utf-8",
            access_log=True,
        ),
    )

    @http("GET", r"/(?:|index.html)")
    async def index(self, request: web.Request) -> web.Response:
        path = "{}/{}".format(
            os.path.dirname(self.context.get("context", {}).get("_service_file_path")), "public/index.html"
        )
        response: web.Response = FileResponse(path=path, chunk_size=256 * 1024)
        return response

    @http_static("public/", r"/public")
    async def public(self) -> None:
        pass

    @websocket(r"/websocket/?")
    async def websocket_connection(self, websocket: web.WebSocketResponse) -> Tuple[Callable, Callable]:
        # Called when a websocket client is connected
        tomodachi.get_logger().info("websocket client connected")

        async def _receive(data: Union[str, bytes]) -> None:
            # Called when the websocket receives data
            tomodachi.get_logger().info("websocket data received: {}".format(data))
            await websocket.send_str("response {}".format(str(uuid.uuid4())))

        async def _close() -> None:
            # Called when the websocket is closed by the other end
            tomodachi.get_logger().info("websocket closed")

        # Receiving function and closure function returned as tuple
        return _receive, _close

    @http_error(status_code=404)
    async def error_404(self, request: web.Request) -> str:
        return "error 404"
