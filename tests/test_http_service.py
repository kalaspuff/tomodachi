import aiohttp
import asyncio
from run_test_service_helper import start_service


def test_start_http_service(monkeypatch, capsys):
    services, future = start_service('tests/http_service.py', monkeypatch)

    assert services is not None
    assert len(services) == 1
    instance = services.get('dummy_http')
    assert instance is not None

    port = instance.context.get('_http_port')
    assert port is not None
    assert port != 0
    instance.stop_service()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(future)


def test_request_http_service(monkeypatch, capsys):
    services, future = start_service('tests/http_service.py', monkeypatch)
    instance = services.get('dummy_http')
    port = instance.context.get('_http_port')

    async def _async(loop):
        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/test'.format(port))
            assert response.status == 200
            assert await response.text() == 'test'

            response = await client.post('http://127.0.0.1:{}/test'.format(port))
            assert response.status == 405

            response = await client.head('http://127.0.0.1:{}/test'.format(port))
            assert response.status == 200

            _id = '123456789'
            response = await client.get('http://127.0.0.1:{}/test/{}'.format(port, _id))
            assert response.status == 200
            assert await response.text() == 'test {}'.format(_id)

            response = await client.get('http://127.0.0.1:{}/non-existant-url'.format(port))
            assert response.status == 404
            assert await response.text() == 'test 404'

    loop = asyncio.get_event_loop()
    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)
