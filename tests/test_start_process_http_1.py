import asyncio
from typing import Any

import aiohttp

from run_test_service_helper import start_service


def test_start_process_http_early_request(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    func, future = start_service("tests/services/start_process_service_http_1.py", monkeypatch, wait=False, loop=loop)
    port = 53251

    async def _async(loop: Any) -> None:
        await asyncio.sleep(1.5)
        async with aiohttp.ClientSession(loop=loop) as client:
            try:
                response = await client.get("http://127.0.0.1:{}/".format(port))
            except Exception:
                response = False

            assert response is False

    loop.run_until_complete(_async(loop))
    loop.run_until_complete(future)

    services = loop.run_until_complete(func())
    assert services is not None
    assert len(services) == 1
    instance = services.get("test_http")
    assert instance is not None

    assert instance.uuid is not None

    assert instance.function_order == ["_start_service", "_started_service", "_stop_service"]

    instance.stop_service()
