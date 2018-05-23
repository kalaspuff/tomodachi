import os
import asyncio
import tomodachi
from typing import Tuple, Callable, Union
from aiohttp import web
from tomodachi import http, http_error, http_static, websocket, HttpResponse
from tomodachi.discovery import DummyRegistry


@tomodachi.service
class ExampleHttpService(tomodachi.Service):
    name = 'example_http_service'
    log_level = 'DEBUG'
    uuid = os.environ.get('SERVICE_UUID')

    # Build own "discovery" functions, to be run on start and stop
    # See tomodachi/discovery/dummy_registry.py for example
    discovery = [DummyRegistry]

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = {
        'http': {
            'port': 4711,
            'content_type': 'text/plain',
            'charset': 'utf-8',
            'access_log': True
        }
    }

    @http('GET', r'/example/?')
    async def example(self, request: web.Request) -> str:
        await asyncio.sleep(1)
        self.log('test')
        return '友達'  # tomodachi

    @http('GET', r'/example/(?P<id>[^/]+?)/?')
    async def example_with_id(self, request: web.Request, id: str) -> str:
        return '友達 (id: {})'.format(id)

    @http('GET', r'/response/?')
    async def response_object(self, request: web.Request) -> HttpResponse:
        return HttpResponse(body='{"data": true}', status=200, content_type='application/json')

    @http_static('static/', r'/static/')
    async def static_files(self) -> None:
        # This function is actually never called by accessing the /static/ URL:s.
        pass

    @websocket(r'/websocket/?')
    async def websocket_connection(self, websocket: web.WebSocketResponse) -> Tuple[Callable, Callable]:
        # Called when a websocket client is connected
        self.log('websocket client connected')

        async def _receive(data: Union[str, bytes]) -> None:
            # Called when the websocket receives data
            self.log('websocket data received: {}'.format(data))
            await websocket.send_str('response')

        async def _close() -> None:
            # Called when the websocket is closed by the other end
            self.log('websocket closed')

        return _receive, _close

    @http_error(status_code=404)
    async def error_404(self, request: web.Request) -> str:
        return 'error 404'
