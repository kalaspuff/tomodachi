import asyncio
import os
import signal
import tomodachi
from tomodachi.transport.http import http, http_error
from tomodachi.discovery.dummy_registry import DummyRegistry


@tomodachi.service
class HttpService(object):
    name = 'test_http'
    discovery = [DummyRegistry]
    options = {
        'http': {
            'port': None,
        }
    }
    uuid = None
    closer = asyncio.Future()
    slow_request = False

    @http('GET', r'/test/?')
    async def test(self, request):
        return 'test'  # tomodachi

    @http('GET', r'/test/(?P<id>[^/]+?)/?')
    async def test_with_id(self, request, id):
        return 'test {}'.format(id)

    @http('GET', r'/slow/?')
    async def test_slow(self, request):
        await asyncio.sleep(2.0)
        self.slow_request = True
        return 'test'

    @http(['GET'], r'/dict/?')
    async def test_dict(self, request):
        return {
            'status': 200,
            'body': 'test dict',
            'headers': {
                'X-Dict': 'test'
            }
        }

    @http('GET', r'/tuple/?')
    async def test_tuple(self, request):
        return (200, 'test tuple', {
            'X-Tuple': 'test'
        })

    @http('GET', r'/exception/?')
    async def test_exception(self, request):
        raise Exception('test')

    @http('GET', r'/slow-exception/?')
    async def test_slow_exception(self, request):
        await asyncio.sleep(2.0)
        raise Exception('test')

    @http_error(status_code=404)
    async def test_404(self, request):
        return 'test 404'

    async def _started_service(self):
        async def _async():
            async def sleep_and_kill():
                await asyncio.sleep(10.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            asyncio.ensure_future(sleep_and_kill())
            await self.closer
            os.kill(os.getpid(), signal.SIGINT)
        asyncio.ensure_future(_async())

    def stop_service(self):
        if not self.closer.done():
            self.closer.set_result(None)
