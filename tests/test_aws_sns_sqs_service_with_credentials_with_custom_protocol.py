import asyncio
import os
import time
from typing import Any

import pytest

from run_test_service_helper import start_service


@pytest.mark.skipif(
    not os.environ.get("TOMODACHI_TEST_AWS_ACCESS_KEY_ID") or not os.environ.get("TOMODACHI_TEST_AWS_ACCESS_SECRET"),
    reason="AWS configuration options missing in environment",
)
def test_start_aws_sns_sqs_service_with_credentials_with_custom_protocol(
    monkeypatch: Any, capsys: Any, loop: Any
) -> None:
    services, future = start_service(
        "tests/services/aws_sns_sqs_service_with_credentials_with_custom_protocol.py", monkeypatch
    )

    assert services is not None
    assert len(services) == 1
    instance = services.get("test_aws_sns_sqs")
    assert instance is not None

    assert instance.uuid is not None

    async def _async(loop: Any) -> None:
        loop_until = time.time() + 10
        while loop_until > time.time():
            if instance.test_topic_data_received and instance.test_topic_data:
                break
            await asyncio.sleep(0.5)

        assert instance.test_topic_data_received
        assert instance.test_topic_data == instance.data_uuid

    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)
