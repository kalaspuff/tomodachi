import asyncio
import os
import signal
from tomodachi.transport.http import http, http_error
from tomodachi.discovery.dummy_registry import DummyRegistry


class HttpService(object):
    name = 'dummy_http'
    discovery = [DummyRegistry]
    options = {
        'http': {
            'port': None,
        }
    }
    uuid = None
    closer = asyncio.Future()

    @http('GET', r'/test/?')
    async def test(self, request):
        return 'test'  # tomodachi

    @http('GET', r'/test/(?P<id>[^/]+?)/?')
    async def test_with_id(self, request, id):
        return 'test {}'.format(id)

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
