import asyncio
import os
import signal
from tomodachi.discovery.dummy_registry import DummyRegistry
from tomodachi.protocol.json_base import JsonBase


class DummyService(object):
    name = 'dummy'
    discovery = [DummyRegistry]
    message_protocol = JsonBase

    start = False
    started = False
    stop = False

    async def _start_service(self):
        self.start = True

    async def _started_service(self):
        self.started = True
        await asyncio.sleep(0.1)
        os.kill(os.getpid(), signal.SIGINT)

    async def _stop_service(self):
        self.stop = True
