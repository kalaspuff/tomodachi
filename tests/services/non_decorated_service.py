import asyncio
import os
import signal


class NonDecoratedService(object):
    name = 'test_non_decorated'

    async def _started_service(self):
        await asyncio.sleep(0.1)
        os.kill(os.getpid(), signal.SIGTERM)
