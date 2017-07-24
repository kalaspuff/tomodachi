import aiohttp
import asyncio
import pytest
import os
import logging
from typing import Any
from multidict import CIMultiDictProxy
from run_test_service_helper import start_service


def test_start_http_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/http_service.py', monkeypatch)

    assert services is not None
    assert len(services) == 1
    instance = services.get('test_http')
    assert instance is not None

    port = instance.context.get('_http_port')
    assert port is not None
    assert port != 0
    assert instance.uuid is not None
    instance.stop_service()
    loop.run_until_complete(future)


def test_conflicting_port_http_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/http_service_same_port.py', monkeypatch)

    assert services is not None
    assert len(services) == 2
    instance = services.get('test_http1')
    assert instance is not None

    port1 = instance.context.get('_http_port')
    assert instance.uuid is not None

    instance = services.get('test_http2')
    assert instance is not None

    port2 = instance.context.get('_http_port')
    assert instance.uuid is not None

    assert bool(port1 and port2) is False

    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert 'address already in use' in err


def test_request_http_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/http_service.py', monkeypatch)
    instance = services.get('test_http')
    port = instance.context.get('_http_port')

    async def _async(loop: Any) -> None:
        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/test'.format(port))
            assert response.status == 200
            assert await response.text() == 'test'
            assert response.headers.get('Server') == 'tomodachi'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.post('http://127.0.0.1:{}/test'.format(port))
            assert response.status == 405

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.head('http://127.0.0.1:{}/test'.format(port))
            assert response.status == 200

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/dict'.format(port))
            assert response.status == 200
            assert await response.text() == 'test dict'
            assert isinstance(response.headers, CIMultiDictProxy)
            assert response.headers.get('X-Dict') == 'test'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/tuple'.format(port))
            assert response.status == 200
            assert await response.text() == 'test tuple'
            assert isinstance(response.headers, CIMultiDictProxy)
            assert response.headers.get('X-Tuple') == 'test'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/aiohttp'.format(port))
            assert response.status == 200
            assert await response.text() == 'test aiohttp'
            assert isinstance(response.headers, CIMultiDictProxy)
            assert response.headers.get('X-Aiohttp') == 'test'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/response'.format(port))
            assert response.status == 200
            assert await response.text() == 'test tomodachi response'
            assert isinstance(response.headers, CIMultiDictProxy)
            assert response.headers.get('X-Tomodachi-Response') == 'test'

        async with aiohttp.ClientSession(loop=loop) as client:
            _id = '123456789'
            response = await client.get('http://127.0.0.1:{}/test/{}'.format(port, _id))
            assert response.status == 200
            assert await response.text() == 'test {}'.format(_id)

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/non-existant-url'.format(port))
            assert response.status == 404
            assert await response.text() == 'test 404'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/exception'.format(port))
            assert response is not None
            assert response.status == 500
            assert isinstance(response.headers, CIMultiDictProxy)
            assert response.headers.get('Server') == 'tomodachi'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = None
            with pytest.raises(asyncio.TimeoutError):
                response = await asyncio.shield(client.get('http://127.0.0.1:{}/slow-exception'.format(port), timeout=0.1))
            assert response is None

        async with aiohttp.ClientSession(loop=loop) as client:
            assert instance.slow_request is False
            response = None
            with pytest.raises(asyncio.TimeoutError):
                response = await asyncio.shield(client.get('http://127.0.0.1:{}/slow'.format(port), timeout=0.1))
            assert response is None
            assert instance.slow_request is False

            await asyncio.sleep(2.0)
            assert instance.slow_request is True

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/slow'.format(port), timeout=3.0)
            assert response is not None

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/test-weird-content-type'.format(port))
            assert response is not None
            assert response.status == 200
            assert await response.text() == 'test'
            assert response.headers.get('Content-Type') == 'text/plain; '

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/test-charset'.format(port))
            assert response is not None
            assert response.status == 200
            assert await response.text() == 'test'
            assert response.headers.get('Content-Type') == 'text/plain; charset=utf-8'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/test-charset'.format(port))
            assert response is not None
            assert response.status == 200
            assert await response.text() == 'test'
            assert response.headers.get('Content-Type') == 'text/plain; charset=utf-8'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/test-charset-encoding-correct'.format(port))
            assert response is not None
            assert response.status == 200
            assert await response.text() == 'test åäö'
            assert response.headers.get('Content-Type') == 'text/plain; charset=iso-8859-1'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/test-charset-encoding-error'.format(port))
            assert response is not None
            assert response.status == 500
            assert response.headers.get('Content-Type') == 'text/plain; charset=utf-8'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/test-charset-invalid'.format(port))
            assert response is not None
            assert response.status == 500
            assert response.headers.get('Content-Type') == 'text/plain; charset=utf-8'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/empty-data'.format(port))
            assert response is not None
            assert response.status == 200
            assert await response.text() == ''
            assert response.headers.get('Content-Type') == 'text/plain; charset=utf-8'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/byte-data'.format(port))
            assert response is not None
            assert response.status == 200
            assert await response.text() == 'test åäö'
            assert response.headers.get('Content-Type') == 'text/plain; charset=utf-8'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/none-data'.format(port))
            assert response is not None
            assert response.status == 200
            assert await response.text() == ''
            assert response.headers.get('Content-Type') == 'text/plain; charset=utf-8'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/forwarded-for'.format(port))
            assert response is not None
            assert response.status == 200
            assert await response.text() == '127.0.0.1'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/forwarded-for'.format(port), headers={'X-Forwarded-For': '192.168.0.1, 10.0.0.1'})
            assert response is not None
            assert response.status == 200
            assert await response.text() == '192.168.0.1'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/authorization'.format(port), headers={'Authorization': 'Basic YXV0aHVzZXI6c2VjcmV0YWY='})
            assert response is not None
            assert response.status == 200
            assert await response.text() == 'authuser'

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.get('http://127.0.0.1:{}/authorization'.format(port), headers={'Authorization': 'Basic 0123456789'})
            assert response is not None
            assert response.status == 200
            assert await response.text() == ''

    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)


def test_access_log(monkeypatch: Any, loop: Any) -> None:
    log_path = '/tmp/03c2ad00-d47d-4569-84a3-0958f88f6c14.log'

    logging.basicConfig(format='%(asctime)s (%(name)s): %(message)s', level=logging.INFO)
    logging.Formatter(fmt='%(asctime)s.%(msecs).03d', datefmt='%Y-%m-%d %H:%M:%S')

    services, future = start_service('tests/services/http_access_log_service.py', monkeypatch)
    instance = services.get('test_http')
    port = instance.context.get('_http_port')

    assert os.path.exists(log_path) is True
    with open(log_path) as file:
        content = file.read()
        assert content == 'Listening [http] on http://127.0.0.1:{}/\n'.format(port)

    async def _async(loop: Any) -> None:
        async with aiohttp.ClientSession(loop=loop) as client:
            await client.get('http://127.0.0.1:{}/test'.format(port))
            with open(log_path) as file:
                content = file.read()
                assert '[http] [200] 127.0.0.1 - "GET /test HTTP/1.1" 4 0' in content
                assert '[http] [404] 127.0.0.1 - "GET /404 HTTP/1.1" 8 0' not in content

        async with aiohttp.ClientSession(loop=loop) as client:
            await client.get('http://127.0.0.1:{}/404'.format(port))
            with open(log_path) as file:
                content = file.read()
                assert '[http] [200] 127.0.0.1 - "GET /test HTTP/1.1" 4 0' in content
                assert '[http] [404] 127.0.0.1 - "GET /404 HTTP/1.1" 8 0' in content

    with open(log_path) as file:
        content = file.read()
        assert content == 'Listening [http] on http://127.0.0.1:{}/\n'.format(port)

    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)

    assert os.path.exists(log_path) is False
