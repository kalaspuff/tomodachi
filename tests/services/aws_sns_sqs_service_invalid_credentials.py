import asyncio
import os
import signal
import tomodachi
from typing import Any
from tomodachi.discovery.aws_sns_registration import AWSSNSRegistration
from tomodachi.protocol.json_base import JsonBase
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs


@tomodachi.service
class AWSSNSSQSService(object):
    name = 'test_aws_sns_sqs'
    log_level = 'INFO'
    discovery = [AWSSNSRegistration]
    message_protocol = JsonBase
    options = {
        'aws_sns_sqs': {
            'region_name': 'eu-west-1',
            'aws_access_key_id': 'XXXXXXXXX',
            'aws_secret_access_key': 'XXXXXXXXX'
        }
    }
    closer = asyncio.Future()  # type: Any

    @aws_sns_sqs('test-topic', ('data',))
    async def test(self, data: Any) -> None:
        pass

    @aws_sns_sqs('test-topic#', ('metadata', 'data'))
    async def faked_wildcard_topic(self, metadata: Any, data: Any) -> None:
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
