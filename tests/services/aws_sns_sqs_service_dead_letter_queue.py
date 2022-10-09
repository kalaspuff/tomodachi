import asyncio
import os
import uuid as uuid_
from typing import Any

import tomodachi
from tomodachi.transport.aws_sns_sqs import AWSSNSSQSInternalServiceError, aws_sns_sqs, aws_sns_sqs_publish

data_uuid = str(uuid_.uuid4())


@tomodachi.service
class AWSSNSSQSService(tomodachi.Service):
    name = "test_aws_sns_sqs_dead_letter_queue"
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
    uuid = os.environ.get("TOMODACHI_TEST_SERVICE_UUID") or ""
    closer: asyncio.Future
    test_topic_data_received_count = 0
    test_dlq_data_received_after_count = -1
    data_uuid = data_uuid

    def check_closer(self) -> None:
        if self.test_topic_data_received_count == 3 and self.test_dlq_data_received_after_count == 3:
            if not self.closer.done():
                self.closer.set_result(None)

    @aws_sns_sqs(
        "test-topic-redrive",
        queue_name="test-queue-{}".format(data_uuid),
        visibility_timeout=3,
        dead_letter_queue_name="test-queue-dlq-{}".format(data_uuid),
        max_receive_count=3,
    )
    async def test_redrive(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            self.test_topic_data_received_count += 1
            self.check_closer()

            raise AWSSNSSQSInternalServiceError

    @aws_sns_sqs(queue_name="test-queue-dlq-{}".format(data_uuid))
    async def test_dlq(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            await asyncio.sleep(6)
            if self.test_dlq_data_received_after_count < 0:
                self.test_dlq_data_received_after_count = self.test_topic_data_received_count

            self.check_closer()

    async def _start_service(self) -> None:
        self.closer = asyncio.Future()

    async def _started_service(self) -> None:
        async def publish(data: Any, topic: str, **kwargs: Any) -> None:
            await aws_sns_sqs_publish(self, data, topic=topic, wait=False, **kwargs)

        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(30.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            task = asyncio.ensure_future(sleep_and_kill())
            await self.closer
            if not task.done():
                task.cancel()
            tomodachi.exit()

        asyncio.ensure_future(_async())

        async def _async_publisher() -> None:
            await publish(self.data_uuid, "test-topic-redrive")

        asyncio.ensure_future(_async_publisher())

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
