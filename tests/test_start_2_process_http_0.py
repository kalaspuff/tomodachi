import asyncio
import platform
from typing import Any

import aiohttp
import pytest

from run_test_service_helper import start_service


@pytest.mark.skipif(
    platform.system() != "Linux",
    reason="SO_REUSEPORT can only be enabled on Linux",
)
def test_start_2_process_http_reuse_port_request(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    func, future = start_service("tests/services/start_process_service_http_0.py", monkeypatch, wait=False)

    port = 53250

    async def _async(loop: Any) -> None:
        await asyncio.sleep(1)
        async with aiohttp.ClientSession(loop=loop) as client:
            services_uuid = set()
            for ti in range(100):
                response = await client.get("http://127.0.0.1:{}/get-uuid".format(port))
                data = await response.read()
                assert len(data) > 0
                services_uuid.add(str(data))
                if len(services_uuid) == 2:
                    break
            assert len(services_uuid) == 2

    loop.run_until_complete(_async(loop))
    loop.run_until_complete(future)

    services = func()
    assert services is not None
    assert len(services) == 2
    instance1 = services.get("test_http")
    assert instance1 is not None
    assert instance1.uuid is not None
    instance2 = services.get("test_http2")
    assert instance2 is not None
    assert instance2.uuid is not None

    assert instance1.uuid != instance2.uuid
    assert instance1.function_order == ["_start_service", "_started_service", "_stop_service"]
    assert instance2.function_order == ["_start_service", "_started_service", "_stop_service"]

    instance1.stop_service()
    instance2.stop_service()
