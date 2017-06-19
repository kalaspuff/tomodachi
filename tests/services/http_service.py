import asyncio
import os
import signal
import tomodachi
from typing import Any, Dict, Tuple  # noqa
from aiohttp import web
from tomodachi.transport.http import http, http_error, Response
from tomodachi.discovery.dummy_registry import DummyRegistry


@tomodachi.service
class HttpService(object):
    name = 'test_http'
    discovery = [DummyRegistry]
    options = {
        'http': {
            'port': None,
            'access_log': True
        }
    }
    uuid = None
    closer = asyncio.Future()  # type: Any
    slow_request = False

    @http('GET', r'/test/?')
    async def test(self, request: web.Request) -> str:
        return 'test'

    @http('GET', r'/test/(?P<id>[^/]+?)/?')
    async def test_with_id(self, request: web.Request, id: str) -> str:
        return 'test {}'.format(id)

    @http('GET', r'/slow/?')
    async def test_slow(self, request: web.Request) -> str:
        await asyncio.sleep(2.0)
        self.slow_request = True
        return 'test'

    @http(['GET'], r'/dict/?')
    async def test_dict(self, request: web.Request) -> Dict:
        return {
            'status': 200,
            'body': 'test dict',
            'headers': {
                'X-Dict': 'test'
            }
        }

    @http('GET', r'/tuple/?')
    async def test_tuple(self, request: web.Request) -> Tuple:
        return (200, 'test tuple', {
            'X-Tuple': 'test'
        })

    @http('GET', r'/aiohttp/?')
    async def test_aiohttp(self, request: web.Request) -> web.Response:
        return web.Response(body='test aiohttp', status=200, headers={
            'X-Aiohttp': 'test'
        })

    @http('GET', r'/response/?')
    async def test_response_object(self, request: web.Request) -> Response:
        return Response(body='test tomodachi response', status=200, headers={
            'X-Tomodachi-Response': 'test'
        })

    @http('GET', r'/exception/?')
    async def test_exception(self, request: web.Request) -> None:
        raise Exception('test')

    @http('GET', r'/slow-exception/?')
    async def test_slow_exception(self, request: web.Request) -> None:
        await asyncio.sleep(2.0)
        raise Exception('test')

    @http_error(status_code=404)
    async def test_404(self, request: web.Request) -> str:
        return 'test 404'

    async def _started_service(self) -> None:
        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(10.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            asyncio.ensure_future(sleep_and_kill())
            await self.closer
            os.kill(os.getpid(), signal.SIGINT)
        asyncio.ensure_future(_async())

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
