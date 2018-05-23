import asyncio
import os
import signal
import tomodachi
from typing import Any, Dict, Tuple  # noqa
from aiohttp import web
from tomodachi.transport.http import http, http_error


@tomodachi.service
class HttpService(tomodachi.Service):
    name = 'test_http'
    options = {
        'http': {
            'port': None,
            'access_log': '/tmp/03c2ad00-d47d-4569-84a3-0958f88f6c14.log'
        }
    }
    uuid = None
    closer = asyncio.Future()  # type: Any
    slow_request = False

    def __init__(self) -> None:
        try:
            os.remove('/tmp/03c2ad00-d47d-4569-84a3-0958f88f6c14.log')
        except OSError:
            pass

    @http('GET', r'/test/?')
    async def test(self, request: web.Request) -> str:
        return 'test'

    @http_error(status_code=404)
    async def test_404(self, request: web.Request) -> str:
        return 'test 404'

    async def _started_service(self) -> None:
        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(10.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            task = asyncio.ensure_future(sleep_and_kill())
            await self.closer
            if not task.done():
                task.cancel()
            os.kill(os.getpid(), signal.SIGINT)
        asyncio.ensure_future(_async())

    async def _stop_service(self) -> None:
        try:
            os.remove('/tmp/03c2ad00-d47d-4569-84a3-0958f88f6c14.log')
        except OSError:
            pass

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
