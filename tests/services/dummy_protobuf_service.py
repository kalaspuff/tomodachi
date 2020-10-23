import tomodachi
from tomodachi.discovery.dummy_registry import DummyRegistry
from tomodachi.envelope.protobuf_base import ProtobufBase


@tomodachi.service
class DummyService(tomodachi.Service):
    name = "test_dummy_protobuf"
    discovery = [DummyRegistry]
    message_envelope = ProtobufBase
    options = {
        "aws_sns_sqs": {
            "region_name": "eu-west-1",
            "aws_access_key_id": "XXXXXXXXX",
            "aws_secret_access_key": "XXXXXXXXX",
        },
        "amqp": {"port": 54321, "login": "invalid", "password": "invalid"},
    }

    start = False
    started = False
    stop = False

    async def _start_service(self) -> None:
        self.start = True

    async def _started_service(self) -> None:
        self.started = True

    async def _stop_service(self) -> None:
        self.stop = True
