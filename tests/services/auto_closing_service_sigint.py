import asyncio
import os
import signal

import tomodachi
from tomodachi.discovery.dummy_registry import DummyRegistry
from tomodachi.envelope.json_base import JsonBase


@tomodachi.service
class AutoClosingService(tomodachi.Service):
    name = "test_auto_closing"
    discovery = [DummyRegistry]
    message_envelope = JsonBase

    start = False
    started = False
    stop = False

    async def _start_service(self) -> None:
        self.start = True

    async def _started_service(self) -> None:
        self.started = True
        await asyncio.sleep(0.1)
        os.kill(os.getpid(), signal.SIGINT)

    async def _stop_service(self) -> None:
        self.stop = True
