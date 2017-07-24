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
            'access_log': True,
            'real_ip_from': '127.0.0.1'
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

    @http('GET', r'/test-weird-content-type/?')
    async def test_weird_content_type(self, request: web.Request) -> Response:
        return web.Response(body='test', status=200, headers={
            'Content-Type': 'text/plain; '
        })

    @http('GET', r'/test-charset/?')
    async def test_charset(self, request: web.Request) -> Response:
        return web.Response(body='test', status=200, headers={
            'Content-Type': 'text/plain; charset=utf-8'
        })

    @http('GET', r'/test-charset-encoding-correct/?')
    async def test_charset_encoding_correct(self, request: web.Request) -> Response:
        return Response(body='test \xe5\xe4\xf6', status=200, headers={
            'Content-Type': 'text/plain; charset=iso-8859-1'
        })

    @http('GET', r'/test-charset-encoding-error/?')
    async def test_charset_encoding_error(self, request: web.Request) -> Response:
        return Response(body='test 友達', status=200, headers={
            'Content-Type': 'text/plain; charset=iso-8859-1'
        })

    @http('GET', r'/test-charset-invalid/?')
    async def test_charset_invalid(self, request: web.Request) -> Response:
        return Response(body='test', status=200, headers={
            'Content-Type': 'text/plain; charset=utf-9'
        })

    @http('GET', r'/empty-data/?')
    async def empty_data(self, request: web.Request) -> str:
        return ''

    @http('GET', r'/byte-data/?')
    async def byte_data(self, request: web.Request) -> bytes:
        return b'test \xc3\xa5\xc3\xa4\xc3\xb6'

    @http('GET', r'/none-data/?')
    async def none_data(self, request: web.Request) -> None:
        return None

    @http('GET', r'/forwarded-for/?')
    async def forwarded_for(self, request: web.Request) -> str:
        return request.request_ip

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
