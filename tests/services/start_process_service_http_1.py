import asyncio
import os
import signal

from aiohttp import web

import tomodachi
from tomodachi.transport.http import http


@tomodachi.service
class HttpService(tomodachi.Service):
    name = "test_http"
    options = {"http": {"port": 53251, "access_log": True, "real_ip_from": "127.0.0.1"}}
    uuid = None
    closer: asyncio.Future
    function_order = []

    @http("GET", r"/?")
    async def index(self, request: web.Request) -> str:
        self.function_order.append("index")
        return "response"

    async def _start_service(self) -> None:
        self.function_order.append("_start_service")
        self.closer = asyncio.Future()
        await asyncio.sleep(4)

    async def _started_service(self) -> None:
        self.function_order.append("_started_service")

        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(4.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            task = asyncio.ensure_future(sleep_and_kill())
            await self.closer
            if not task.done():
                task.cancel()
            tomodachi.exit()

        asyncio.ensure_future(_async())

    def stop_service(self) -> None:
        self.function_order.append("stop_service")
        if not self.closer.done():
            self.closer.set_result(None)

    async def _stop_service(self) -> None:
        self.function_order.append("_stop_service")
