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
    async def test(self, request):
        return 'test'  # tomodachi


@tomodachi.service
class HttpServiceTwo(object):
    name = 'test_http2'
    options = {
        'http': {
            'port': 54322,
        }
    }

    @http('GET', r'/test/?')
    async def test(self, request):
        return 'test'  # tomodachi
