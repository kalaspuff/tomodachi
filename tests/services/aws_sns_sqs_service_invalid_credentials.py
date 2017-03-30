import asyncio
import os
import signal
import tomodachi
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
    closer = asyncio.Future()

    @aws_sns_sqs('test-topic', ('data',))
    async def test(self, data):
        pass

    @aws_sns_sqs('test-topic#', ('metadata', 'data'))
    async def faked_wildcard_topic(self, metadata, data):
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
