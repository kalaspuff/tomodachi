import asyncio
import os
import time
import uuid as uuid_
from typing import Any

import tomodachi
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs, aws_sns_sqs_publish

data_uuid = str(uuid_.uuid4())


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
            "queue_name_prefix": os.environ.get("TOMODACHI_TEST_SQS_QUEUE_PREFIX") or "",
            "topic_prefix": os.environ.get("TOMODACHI_TEST_SNS_TOPIC_PREFIX") or "",
        },
        "aws_endpoint_urls": {
            "sns": os.environ.get("TOMODACHI_TEST_AWS_SNS_ENDPOINT_URL") or None,
            "sqs": os.environ.get("TOMODACHI_TEST_AWS_SQS_ENDPOINT_URL") or None,
        },
    }
    uuid = os.environ.get("TOMODACHI_TEST_SERVICE_UUID") or ""
    closer: asyncio.Future
    delay_seconds = 10
    test_topic_data_received = False

    def check_closer(self) -> None:
        if (
            self.test_topic_data_received and
            (time.time() - self.start_time) > self.delay_seconds
        ):
            if not self.closer.done():
                self.closer.set_result(None)

    @aws_sns_sqs("test-raw-topic", queue_name="test-queue-{}".format(data_uuid))
    async def test(self, value: Any, default_value: bool = True) -> None:
        if data == self.data_uuid:
            self.test_topic_data_received = True
        self.check_closer()

    async def _start_service(self) -> None:
        self.closer = asyncio.Future()

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
            tomodachi.exit()

        asyncio.ensure_future(_async())
        asyncio.ensure_future(
            aws_sns_sqs_publish(self, data_uuid, topic="test-raw-topic", delay_seconds=self.delay_seconds)
        )

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
