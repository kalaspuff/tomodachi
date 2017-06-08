import asyncio
import os
import signal
import tomodachi
from tomodachi.protocol.json_base import JsonBase
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs


@tomodachi.service
class MockDecoratorService(object):
    name = 'mock_decorator'
    log_level = 'INFO'
    message_protocol = JsonBase
    function_tested = False

    @aws_sns_sqs('test-topic')
    async def test(self):
        self.function_tested = True

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
