import asyncio
import os
import signal
from typing import Any

import tomodachi
from tomodachi.protocol.json_base import JsonBase
from tomodachi.transport.amqp import amqp


@tomodachi.service
class AMQPService(tomodachi.Service):
    name = 'test_amqp'
    log_level = 'INFO'
    message_protocol = JsonBase
    options = {
        'amqp': {
            'port': 54321,
            'login': 'invalid',
            'password': 'invalid'
        }
    }
    closer = asyncio.Future()  # type: Any

    @amqp('test.topic', ('data',))
    async def test(self, data: Any) -> None:
        pass

    @amqp('test.#', ('metadata', 'data'))
    async def wildcard_topic(self, metadata: Any, data: Any) -> None:
        pass

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

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
