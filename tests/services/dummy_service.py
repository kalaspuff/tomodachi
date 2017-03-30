import tomodachi
from tomodachi.discovery.dummy_registry import DummyRegistry
from tomodachi.protocol.json_base import JsonBase


@tomodachi.service
class DummyService(object):
    name = 'test_dummy'
    discovery = [DummyRegistry]
    message_protocol = JsonBase
    options = {
        'aws_sns_sqs': {
            'region_name': 'eu-west-1',
            'aws_access_key_id': 'XXXXXXXXX',
            'aws_secret_access_key': 'XXXXXXXXX'
        }
    }

    start = False
    started = False
    stop = False

    async def _start_service(self):
        self.start = True

    async def _started_service(self):
        self.started = True

    async def _stop_service(self):
        self.stop = True
