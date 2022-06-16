import asyncio
import logging
import mimetypes
import os
import pathlib
import platform
from typing import Any

import aiohttp
import pytest
from multidict import CIMultiDictProxy

from run_test_service_helper import start_service
from services.http_service import HttpService


def test_start_http_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/http_service.py", monkeypatch)

    assert services is not None
    assert len(services) == 1
    instance = services.get("test_http")
    assert instance is not None

    port = instance.context.get("_http_port")
    assert port is not None
    assert port != 0
    assert instance.uuid is not None
    instance.stop_service()
    loop.run_until_complete(future)


@pytest.mark.skipif(
    platform.system() == "Linux",
    reason="SO_REUSEPORT is automatically enable on Linux",
)
def test_conflicting_port_http_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/http_service_same_port.py", monkeypatch)

    assert services is not None
    assert len(services) == 2
    instance = services.get("test_http1")
    assert instance is not None

    port1 = instance.context.get("_http_port")
    assert instance.uuid is not None

    instance = services.get("test_http2")
    assert instance is not None

    port2 = instance.context.get("_http_port")
    assert instance.uuid is not None

    assert bool(port1 and port2) is False

    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert "address already in use" in err or "address in use" in err


@pytest.mark.service(service_class=HttpService)
async def test_request_http_service(test_service) -> None:
    client, instance = test_service

    response = await client.get("/test")
    assert response.status == 200
    assert await response.text() == "test"
    assert response.headers.get("Server") == "tomodachi"

    response = await client.post("/test")
    assert response.status == 405

    response = await client.head("/test")
    assert response.status == 200

    response = await client.get("/dict")
    assert response.status == 200
    assert await response.text() == "test dict"
    assert isinstance(response.headers, CIMultiDictProxy)
    assert response.headers.get("X-Dict") == "test"

    response = await client.get("/tuple")
    assert response.status == 200
    assert await response.text() == "test tuple"
    assert isinstance(response.headers, CIMultiDictProxy)
    assert response.headers.get("X-Tuple") == "test"

    response = await client.get("/aiohttp")
    assert response.status == 200
    assert await response.text() == "test aiohttp"
    assert isinstance(response.headers, CIMultiDictProxy)
    assert response.headers.get("X-Aiohttp") == "test"

    response = await client.get("/response")
    assert response.status == 200
    assert await response.text() == "test tomodachi response"
    assert isinstance(response.headers, CIMultiDictProxy)
    assert response.headers.get("X-Tomodachi-Response") == "test"

    response = await client.get("/same-response")
    assert response.status == 200
    assert await response.text() == "test tomodachi response"
    assert isinstance(response.headers, CIMultiDictProxy)
    assert response.headers.get("X-Tomodachi-Response") == "test"

    _id = "123456789"
    response = await client.get("/test/{}".format(_id))
    assert response.status == 200
    assert await response.text() == "test {}".format(_id)

    response = await client.get("/non-existant-url")
    assert response.status == 404
    assert await response.text() == "test 404"

    response = await client.get("/exception")
    assert response is not None
    assert response.status == 500
    assert isinstance(response.headers, CIMultiDictProxy)
    assert response.headers.get("Server") == "tomodachi"

    response = None
    with pytest.raises(asyncio.TimeoutError):
        response = await client.get("/slow-exception", timeout=0.1)
    assert response is None

    assert instance.slow_request is False
    response = None
    with pytest.raises(asyncio.TimeoutError):
        response = await client.get("/slow", timeout=0.1)

    response = await client.get("/slow", timeout=3.0)
    assert response is not None

    response = await client.get("/test-weird-content-type")
    assert response is not None
    assert response.status == 200
    assert await response.text() == "test"
    assert response.headers.get("Content-Type").strip() == "text/plain; ".strip()

    response = await client.get("/test-charset")
    assert response is not None
    assert response.status == 200
    assert await response.text() == "test"
    assert response.headers.get("Content-Type") == "text/plain; charset=utf-8"

    response = await client.get("/test-charset")
    assert response is not None
    assert response.status == 200
    assert await response.text() == "test"
    assert response.headers.get("Content-Type") == "text/plain; charset=utf-8"

    response = await client.get("/test-charset-encoding-correct")
    assert response is not None
    assert response.status == 200
    assert await response.text() == "test åäö"
    assert response.headers.get("Content-Type") == "text/plain; charset=iso-8859-1"

    response = await client.get("/test-charset-encoding-error")
    assert response is not None
    assert response.status == 500
    assert response.headers.get("Content-Type") == "text/plain; charset=utf-8"

    response = await client.get("/test-charset-invalid")
    assert response is not None
    assert response.status == 500
    assert response.headers.get("Content-Type") == "text/plain; charset=utf-8"

    response = await client.get("/empty-data")
    assert response is not None
    assert response.status == 200
    assert await response.text() == ""
    assert response.headers.get("Content-Type") == "text/plain; charset=utf-8"

    response = await client.get("/byte-data")
    assert response is not None
    assert response.status == 200
    assert await response.text() == "test åäö"
    assert response.headers.get("Content-Type") == "text/plain; charset=utf-8"

    response = await client.get("/none-data")
    assert response is not None
    assert response.status == 200
    assert await response.text() == ""
    assert response.headers.get("Content-Type") == "text/plain; charset=utf-8"

    response = await client.get("/forwarded-for")
    assert response is not None
    assert response.status == 200
    assert await response.text() == "127.0.0.1"

    response = await client.get(
        "/forwarded-for", headers={"X-Forwarded-For": "192.168.0.1, 10.0.0.1"}
    )
    assert response is not None
    assert response.status == 200
    assert await response.text() == "192.168.0.1"

    response = await client.get(
        "/authorization",
        headers={"Authorization": "Basic YXV0aHVzZXI6c2VjcmV0YWY="},
    )
    assert response is not None
    assert response.status == 200
    assert await response.text() == "authuser"

    response = await client.get(
        "/authorization", headers={"Authorization": "Basic 0123456789"}
    )
    assert response is not None
    assert response.status == 200
    assert await response.text() == ""

    assert instance.middleware_called is False
    response = await client.get("/test", headers={"X-Use-Middleware": "Set"})
    assert response.status == 200
    assert await response.text() == "test"
    assert instance.middleware_called is True

    assert instance.function_triggered is False
    response = await client.get(
        "/middleware-before", headers={"X-Use-Middleware": "Before"}
    )
    assert response.status == 200
    assert await response.text() == "before"
    assert instance.function_triggered is False

    response = await client.get(
        "/middleware-before", headers={"X-Use-Middleware": "After"}
    )
    assert response.status == 200
    assert await response.text() == "after"
    assert instance.function_triggered is True

    # f = pathlib.Path("{}/tests/static_files/image.png".format(os.path.realpath(os.getcwd()))).open("r")
    # ct, encoding = mimetypes.guess_type(str(f.name))

    # response = await client.get("/static/image.png")
    # assert response is not None
    # assert response.status == 200
    # assert response.headers.get("Content-Type") == "image/png"
    # assert response.headers.get("Content-Type") == ct

    # with open(str(f.name), "rb") as fobj:
    #     data = fobj.read(20000)
    #     assert (await response.read()) == data


    # f = pathlib.Path("{}/tests/static_files/image.png".format(os.path.realpath(os.getcwd()))).open("r")
    # ct, encoding = mimetypes.guess_type(str(f.name))

    # response = await client.get("/download/image.png/image")
    # assert response is not None
    # assert response.status == 200
    # assert response.headers.get("Content-Type") == "image/png"
    # assert response.headers.get("Content-Type") == ct

    # with open(str(f.name), "rb") as fobj:
    #     data = fobj.read(20000)
    #     assert (await response.read()) == data

    response = await client.get("/static/image-404.png")
    assert response is not None
    assert response.status == 404

    assert instance.websocket_connected is False
    ws = await client.ws_connect("/websocket-simple")
    await ws.close()
    assert instance.websocket_connected is True

    assert instance.websocket_header is None
    ws = await client.ws_connect("/websocket-header")
    await ws.close()
    assert instance.websocket_header is not None
    assert "Python" in instance.websocket_header
    assert "aiohttp" in instance.websocket_header

    ws = await client.ws_connect("/websocket-data")
    data = "9e2546ef-7fe1-4f94-a3fc-5dc85a771a17"
    assert instance.websocket_received_data != data
    await ws.send_str(data)
    await ws.close()
    assert instance.websocket_received_data == data



def test_access_log(monkeypatch: Any, loop: Any) -> None:
    log_path = "/tmp/03c2ad00-d47d-4569-84a3-0958f88f6c14.log"

    logging.basicConfig(format="%(asctime)s (%(name)s): %(message)s", level=logging.INFO)
    logging.Formatter(fmt="%(asctime)s.%(msecs).03d", datefmt="%Y-%m-%d %H:%M:%S")

    services, future = start_service("tests/services/http_access_log_service.py", monkeypatch)
    instance = services.get("test_http")
    port = instance.context.get("_http_port")

    assert os.path.exists(log_path) is True
    with open(log_path) as file:
        content = file.read()
        assert "Listening [http] on http://127.0.0.1:{}/\n".format(port) in content

    async def _async(loop: Any) -> None:
        async with aiohttp.ClientSession(loop=loop) as client:
            await client.get("http://127.0.0.1:{}/test_ignore_all".format(port))
            with open(log_path) as file:
                content = file.read()
                assert '[http] [200] 127.0.0.1 - "GET /test_ignore_all HTTP/1.1" 8 -' not in content

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.post("http://127.0.0.1:{}/test_ignore_one".format(port), data="200")
            assert await response.read() == b"test-200"
            with open(log_path) as file:
                content = file.read()
                assert '[http] [200] 127.0.0.1 - "GET /test_ignore_all HTTP/1.1" 8 -' not in content
                assert '[http] [200] 127.0.0.1 - "POST /test_ignore_one HTTP/1.1" 8 -' not in content

        async with aiohttp.ClientSession(loop=loop) as client:
            response = await client.post("http://127.0.0.1:{}/test_ignore_one".format(port))
            assert await response.read() == b"test-201"
            with open(log_path) as file:
                content = file.read()
                assert '[http] [200] 127.0.0.1 - "GET /test_ignore_all HTTP/1.1" 8 -' not in content
                assert '[http] [200] 127.0.0.1 - "POST /test_ignore_one HTTP/1.1" 8 0' not in content
                assert '[http] [201] 127.0.0.1 - "POST /test_ignore_one HTTP/1.1" 8 0' in content

        async with aiohttp.ClientSession(loop=loop) as client:
            await client.get("http://127.0.0.1:{}/test".format(port))
            with open(log_path) as file:
                content = file.read()
                assert '[http] [200] 127.0.0.1 - "GET /test HTTP/1.1" 4 -' in content
                assert '[http] [404] 127.0.0.1 - "GET /404 HTTP/1.1" 8 -' not in content

        async with aiohttp.ClientSession(loop=loop) as client:
            await client.get("http://127.0.0.1:{}/404".format(port))
            with open(log_path) as file:
                content = file.read()
                assert '[http] [200] 127.0.0.1 - "GET /test HTTP/1.1" 4 -' in content
                assert '[http] [404] 127.0.0.1 - "GET /404 HTTP/1.1" 8 -' in content

        async with aiohttp.ClientSession(loop=loop) as client:
            await client.post("http://127.0.0.1:{}/zero-post".format(port), data=b"")
            with open(log_path) as file:
                content = file.read()
                assert '[http] [404] 127.0.0.1 - "POST /zero-post HTTP/1.1" 8 0' in content

        async with aiohttp.ClientSession(loop=loop) as client:
            await client.post("http://127.0.0.1:{}/post".format(port), data=b"RANDOMDATA")
            with open(log_path) as file:
                content = file.read()
                assert '[http] [404] 127.0.0.1 - "POST /post HTTP/1.1" 8 10' in content

    with open(log_path) as file:
        content = file.read()
        assert "Listening [http] on http://127.0.0.1:{}/\n".format(port) in content

    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)

    assert os.path.exists(log_path) is False


@pytest.mark.service(service_class=HttpService)
async def test_http_service(test_service):
    test_client, service = test_service
    response = await test_client.get("/test")
    assert response.status == 200
    assert response.headers.get("Server") == "tomodachi"
    assert await response.text() == "test"

    ws = await test_client.ws_connect("/websocket-data")
    data = "9e2546ef-7fe1-4f94-a3fc-5dc85a771a17"
    assert service.websocket_received_data != data
    await ws.send_str(data)
    await ws.close()
    assert service.websocket_received_data == data

    filename = "static_files/image.png"
    filepath = pathlib.Path(__file__).parent / filename
    ct, encoding = mimetypes.guess_type(str(filename))
    response = await test_client.get("/static/image.png")
    assert response.status == 200
    assert response.headers.get("Content-Type") == "image/png"
    assert response.headers.get("Content-Type") == ct

