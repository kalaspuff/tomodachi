from typing import Any

import aiohttp

from run_test_service_helper import start_service


def test_decorated_functions_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/decorated_functions_service.py', monkeypatch)
    instance = services.get('test_http')
    port = instance.context.get('_http_port')

    async def _async(loop: Any) -> None:
        assert instance.invocation_count == 0
        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/count/1'.format(port))
            assert response.status == 200
            assert await response.text() == str(instance.invocation_count)
            assert instance.invocation_count == 1

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/count/1'.format(port))
            assert response.status == 200
            assert await response.text() == str(instance.invocation_count)
            assert instance.invocation_count == 2

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/count/1'.format(port))
            assert response.status == 200
            assert await response.text() == str(instance.invocation_count)
            assert instance.invocation_count == 3

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/count/2'.format(port))
            assert response.status == 200
            assert await response.text() == str(instance.invocation_count)
            assert instance.invocation_count == 4

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/count/3'.format(port))
            assert response.status == 200
            assert await response.text() == str(instance.invocation_count)
            assert instance.invocation_count == 5

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/count/4'.format(port))
            assert response.status == 200
            assert await response.text() == str(instance.invocation_count)
            assert instance.invocation_count == 6

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/count/0'.format(port))
            assert response.status == 200
            assert await response.text() == '0'
            assert instance.invocation_count == 7

    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)
