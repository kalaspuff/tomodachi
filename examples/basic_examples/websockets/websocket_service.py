import os
import asyncio
import tomodachi
import pathlib
import uuid
from aiohttp.web_fileresponse import FileResponse
from typing import Tuple, Callable, Union
from aiohttp import web
from tomodachi import http_error, http, http_static, websocket


@tomodachi.service
class ExampleWebsocketService(tomodachi.Service):
    name = 'example_websocket_service'
    log_level = 'DEBUG'
    uuid = os.environ.get('SERVICE_UUID')

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = {
        'http': {
            'port': 4711,
            'content_type': 'text/plain',
            'charset': 'utf-8',
            'access_log': True
        }
    }

    @http('GET', r'/(?:|index.html)')
    async def index(self, request: web.Request) -> web.Response:
        path = '{}/{}'.format(os.path.dirname(self.context.get('context', {}).get('_service_file_path')), 'public/index.html')
        response = FileResponse(path=path,  # type: ignore
                                chunk_size=256 * 1024)  # type: web.Response
        return response

    @http_static('public/', r'/public')
    async def public(self) -> None:
        pass

    @websocket(r'/websocket/?')
    async def websocket_connection(self, websocket: web.WebSocketResponse) -> Tuple[Callable, Callable]:
        # Called when a websocket client is connected
        self.log('websocket client connected')

        async def _receive(data: Union[str, bytes]) -> None:
            # Called when the websocket receives data
            self.log('websocket data received: {}'.format(data))
            await websocket.send_str('response {}'.format(str(uuid.uuid4())))

        async def _close() -> None:
            # Called when the websocket is closed by the other end
            self.log('websocket closed')

        # Receiving function and closure function returned as tuple
        return _receive, _close

    @http_error(status_code=404)
    async def error_404(self, request: web.Request) -> str:
        return 'error 404'
