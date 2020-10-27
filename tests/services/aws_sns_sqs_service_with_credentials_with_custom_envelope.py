import asyncio
import json
import os
import signal
import uuid
from typing import Any, Dict, Tuple, Union

import tomodachi
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs, aws_sns_sqs_publish

data_uuid = str(uuid.uuid4())


class CustomEnvelope(object):
    @classmethod
    async def build_message(cls, service: Any, topic: str, data: Any, **kwargs: Any) -> str:
        message = {"envelope": "custom", "data": data}
        return json.dumps(message)

    @classmethod
    async def parse_message(cls, payload: str, **kwargs: Any) -> Union[Dict, Tuple]:
        message = json.loads(payload)
        return message, None, None


@tomodachi.service
class AWSSNSSQSService(tomodachi.Service):
    name = "test_aws_sns_sqs"
    log_level = "INFO"
    options = {
        "aws": {
            "region_name": os.environ.get("TOMODACHI_TEST_AWS_REGION"),
            "aws_access_key_id": os.environ.get("TOMODACHI_TEST_AWS_ACCESS_KEY_ID"),
            "aws_secret_access_key": os.environ.get("TOMODACHI_TEST_AWS_ACCESS_SECRET"),
        },
        "aws_sns_sqs": {
            "queue_name_prefix": os.environ.get("TOMODACHI_TEST_SQS_QUEUE_PREFIX"),
            "topic_prefix": os.environ.get("TOMODACHI_TEST_SNS_TOPIC_PREFIX"),
        },
    }
    uuid = os.environ.get("TOMODACHI_TEST_SERVICE_UUID")
    closer = asyncio.Future()  # type: Any
    test_topic_data_received = False
    test_topic_data = None
    data_uuid = data_uuid

    def check_closer(self) -> None:
        if self.test_topic_data_received:
            if not self.closer.done():
                self.closer.set_result(None)

    @aws_sns_sqs("test-custom-topic", queue_name="test-queue-{}".format(data_uuid), message_envelope=CustomEnvelope)
    async def test(self, data: Any, envelope: Any, default_value: bool = True) -> None:
        if data == self.data_uuid and envelope == "custom":
            self.test_topic_data_received = default_value
            self.test_topic_data = data

            self.check_closer()

    async def _started_service(self) -> None:
        async def publish(data: Any, topic: str) -> None:
            await aws_sns_sqs_publish(self, data, topic=topic, wait=False, message_envelope=CustomEnvelope)

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

        self.data_uuid = str(uuid.uuid4())
        for _ in range(30):
            if self.test_topic_data_received:
                break
            await publish(self.data_uuid, "test-custom-topic")
            await asyncio.sleep(0.1)

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
