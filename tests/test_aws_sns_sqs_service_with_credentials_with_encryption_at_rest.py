import asyncio
import json
import os
import time
from typing import Any

import pytest

from run_test_service_helper import start_service


@pytest.mark.skipif(
    not os.environ.get("TOMODACHI_TEST_AWS_ACCESS_KEY_ID") or not os.environ.get("TOMODACHI_TEST_AWS_ACCESS_SECRET"),
    reason="AWS configuration options missing in environment",
)
def test_start_aws_sns_sqs_service_with_credentials(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service(
        "tests/services/aws_sns_sqs_service_with_credentials_with_encryption_at_rest.py", monkeypatch
    )

    assert services is not None
    assert len(services) == 1
    instance = services.get("test_aws_sns_sqs_encryption_at_rest")
    assert instance is not None

    assert instance.uuid is not None

    async def _async(loop: Any) -> None:
        loop_until = time.time() + 10
        while loop_until > time.time():
            if (
                instance.test_topic_data_received
                and instance.test_topic_metadata_topic
                and instance.test_topic_service_uuid
                and instance.test_topic_specified_queue_name_data_received
                and len(instance.test_message_attribute_currencies) == 7
                and len(instance.test_message_attribute_amounts) == 2
            ):
                break
            await asyncio.sleep(0.5)

        assert instance.test_topic_data_received
        assert instance.test_topic_metadata_topic == "encrypted-test-topic"
        assert instance.test_topic_service_uuid == instance.uuid
        assert instance.test_topic_specified_queue_name_data_received
        assert len(instance.test_message_attribute_currencies) == 7
        assert len(instance.test_message_attribute_amounts) == 2
        assert instance.test_message_attribute_currencies == {
            json.dumps({"currency": "EUR"}),
            json.dumps({"currency": ["GBP"]}),
            json.dumps({"currency": ["CNY", "USD", "JPY"]}),
            json.dumps({"currency": "SEK", "amount": 4711}, sort_keys=True),
            json.dumps({"currency": ["SEK"], "amount": 1338, "value": "1338.00 SEK"}, sort_keys=True),
            json.dumps({"currency": "SEK", "amount": "9001.00"}, sort_keys=True),
            json.dumps({"currency": "USD", "amount": 99.50, "value": "99.50 USD"}, sort_keys=True),
        }
        assert instance.test_message_attribute_amounts == {
            json.dumps({"currency": "SEK", "amount": 4711}, sort_keys=True),
            json.dumps({"currency": ["SEK"], "amount": 1338, "value": "1338.00 SEK"}, sort_keys=True),
        }

    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)
