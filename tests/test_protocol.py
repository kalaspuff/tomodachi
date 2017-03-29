import asyncio
import os
import signal
import time
from run_test_service_helper import start_service


def test_json_base(monkeypatch, capsys):
    services, future = start_service('tests/services/dummy_service.py', monkeypatch)

    instance = services.get('dummy')

    async def _async():
        data = {'key': 'value'}
        t1 = time.time()
        json_message = await instance.message_protocol.build_message(instance, 'topic', data)
        t2 = time.time()
        result, message_uuid, timestamp = await instance.message_protocol.parse_message(json_message)
        assert result.get('data') == data
        assert len(message_uuid) == 73
        assert message_uuid[0:36] == instance.uuid
        assert timestamp >= t1
        assert timestamp <= t2

    loop = asyncio.get_event_loop()
    loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)
