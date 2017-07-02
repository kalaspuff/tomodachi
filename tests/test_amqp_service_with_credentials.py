import pytest
import os
import asyncio
from typing import Any
from run_test_service_helper import start_service


@pytest.mark.skipif(not os.environ.get('TOMODACHI_TEST_RABBITMQ_ENABLED'), reason='RabbitMQ needs to be enabled and environment TOMODACHI_TEST_RABBITMQ_ENABLED needs to be set')
def test_start_amqp_service_with_credentials(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/amqp_service_with_credentials.py', monkeypatch)

    assert services is not None
    assert len(services) == 1
    instance = services.get('test_amqp')
    assert instance is not None

    assert instance.uuid is not None

    async def _async(loop: Any) -> None:
        await asyncio.sleep(5)
        assert instance.test_topic_data_received
        assert instance.test_topic_metadata_topic == 'test.topic'
        assert instance.test_topic_service_uuid == instance.uuid
        assert instance.wildcard_topic_data_received

    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)
