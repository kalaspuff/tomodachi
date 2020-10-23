import asyncio
import os
import signal

import tomodachi
from tomodachi.discovery.dummy_registry import DummyRegistry
from tomodachi.envelope.json_base import JsonBase


class AutoClosingService(tomodachi.Service):
    name = "test_auto_closing"
    discovery = [DummyRegistry]
    message_envelope = JsonBase

    start = False
    started = False
    stop = False

    async def _start_service(self) -> None:
        self.log("_start_service() function called")
        self.start = True

    async def _started_service(self) -> None:
        self.log("_started_service() function called")
        self.started = True
        await asyncio.sleep(0.1)
        os.kill(os.getpid(), signal.SIGTERM)

    async def _stop_service(self) -> None:
        self.log("_stop_service() function called")
        self.stop = True
