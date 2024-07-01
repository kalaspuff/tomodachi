import asyncio
import os
import time
from typing import Any

import pytest

from run_test_service_helper import start_service
from tomodachi.transport.aws_sns_sqs import connector


@pytest.mark.skipif(
    not os.environ.get("TOMODACHI_TEST_AWS_ACCESS_KEY_ID") or not os.environ.get("TOMODACHI_TEST_AWS_ACCESS_SECRET"),
    reason="AWS configuration options missing in environment",
)
def test_start_aws_sns_sqs_service_dead_letter_queue(capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/aws_sns_sqs_service_dead_letter_queue.py", loop=loop)

    assert services is not None
    assert len(services) == 1
    instance = services.get("test_aws_sns_sqs_dead_letter_queue")
    assert instance is not None

    assert instance.uuid is not None

    async def _async(loop: Any) -> None:
        loop_until = time.time() + 32
        while loop_until > time.time():
            if instance.test_topic_data_received_count == 3 and instance.test_dlq_data_received_after_count == 3:
                break
            await asyncio.sleep(0.5)

        assert instance.test_topic_data_received_count == 3
        assert instance.test_dlq_data_received_after_count == 3

        async with connector("tomodachi.sqs", service_name="sqs") as sqs_client:
            dlq_name = "test-queue-dlq-{}".format(instance.data_uuid)
            response = await sqs_client.get_queue_url(QueueName=dlq_name)
            dlq_url = response.get("QueueUrl")
            response = await sqs_client.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=[
                    "VisibilityTimeout",
                    "MessageRetentionPeriod",
                ],
            )
            dlq_attributes = response.get("Attributes", {})

        assert dlq_attributes == {
            "VisibilityTimeout": "30",
            "MessageRetentionPeriod": "1209600",  # 14 days
        }

    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)
