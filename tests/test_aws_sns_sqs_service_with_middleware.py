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
def test_start_aws_sns_sqs_service_with_middleware(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/aws_sns_sqs_service_with_middleware.py", monkeypatch, loop=loop)

    assert services is not None
    assert len(services) == 1
    instance = services.get("test_aws_sns_sqs")
    assert instance is not None

    assert instance.uuid is not None

    async def _async(loop: Any) -> None:
        loop_until = time.time() + 90
        while loop_until > time.time():
            if instance.test_topic_data_received:
                break
            await asyncio.sleep(0.5)

        assert instance.test_topic_data_received
        assert len(instance.test_queue_url) > 1
        assert len(instance.test_receipt_handle) > 1
        assert instance.test_approximate_receive_count >= 1
        assert instance.test_message_attributes == {"attr_1": "value_1", "attr_2": "value_2", "initial_a_value": 5}
        assert instance.test_middleware_values == {
            "kwarg_abc": 4711,
            "kwarg_xyz": 4712,
            "initial_a_value": 5,
            "a_value": 30,
            "another_value": 42,
            "middlewares_called": ["middleware_init_000", "middleware_func_abc", "middleware_func_xyz"],
        }

    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)
