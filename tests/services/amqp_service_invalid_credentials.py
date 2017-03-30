import asyncio
import os
import signal
import tomodachi
from tomodachi.protocol.json_base import JsonBase
from tomodachi.transport.amqp import amqp


@tomodachi.service
class AWSSNSSQSService(object):
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
    closer = asyncio.Future()

    @amqp('test.topic', ('data',))
    async def test(self, data):
        pass

    @amqp('test.#', ('metadata', 'data'))
    async def wildcard_topic(self, metadata, data):
        pass

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
