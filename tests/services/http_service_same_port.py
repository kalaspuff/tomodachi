from aiohttp import web
import tomodachi
from tomodachi.transport.http import http


@tomodachi.service
class HttpServiceOne(object):
    name = 'test_http1'
    options = {
        'http': {
            'port': 54322,
        }
    }

    @http('GET', r'/test/?')
    async def test(self, request: web.Request) -> str:
        return 'test'


@tomodachi.service
class HttpServiceTwo(object):
    name = 'test_http2'
    options = {
        'http': {
            'port': 54322,
        }
    }

    @http('GET', r'/test/?')
    async def test(self, request: web.Request) -> str:
        return 'test'
