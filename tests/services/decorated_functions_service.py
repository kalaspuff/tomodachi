import asyncio
import os
import signal
from typing import Any

from aiohttp import web

import tomodachi
from tomodachi.transport.http import http


@tomodachi.decorator
async def count_invocations_1(self: Any, *args: Any, **kwargs: Any) -> None:
    self.invocation_count += 1


@tomodachi.decorator()
async def count_invocations_2(self: Any, *args: Any, **kwargs: Any) -> None:
    self.invocation_count += 1


@tomodachi.decorator(include_function=True)
async def count_invocations_3(func: Any, self: Any, *args: Any, **kwargs: Any) -> None:
    self.invocation_count += 1


@tomodachi.decorator
def count_invocations_4(self: Any, *args: Any, **kwargs: Any) -> None:
    self.invocation_count += 1


@tomodachi.decorator
def count_invocations_0(self: Any, *args: Any, **kwargs: Any) -> str:
    self.invocation_count += 1
    return "0"


@tomodachi.service
class HttpService(tomodachi.Service):
    name = "test_http"
    options = {"http": {"port": None, "access_log": True, "real_ip_from": "127.0.0.1"}}
    invocation_count = 0
    uuid = None
    closer: asyncio.Future

    @http("GET", r"/count/1/?")
    @count_invocations_1
    async def count_1(self, request: web.Request) -> str:
        return str(self.invocation_count)

    @http("GET", r"/count/2/?")
    @count_invocations_2
    async def count_2(self, request: web.Request) -> str:
        return str(self.invocation_count)

    @http("GET", r"/count/3/?")
    @count_invocations_3
    async def count_3(self, request: web.Request) -> str:
        return str(self.invocation_count)

    @http("GET", r"/count/4/?")
    @count_invocations_4
    def count_4(self, request: web.Request) -> str:
        return str(self.invocation_count)

    @http("GET", r"/count/0/?")
    @count_invocations_0
    async def count_0(self, request: web.Request) -> str:
        return str(self.invocation_count)

    async def _start_service(self) -> None:
        self.closer = asyncio.Future()

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
            tomodachi.exit()

        asyncio.ensure_future(_async())

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
