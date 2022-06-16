from typing import AsyncIterator, Iterator, Tuple

import pytest
from _pytest.config import Config
import inspect
from aiohttp.test_utils import TestClient, TestServer
from tomodachi import Service
from tomodachi.transport.http import HttpTransport
from tomodachi.invoker import FUNCTION_ATTRIBUTE, INVOKER_TASK_START_KEYWORD, START_ATTRIBUTE

def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers",
        "service(service_class=Service): "
    )


@pytest.fixture
async def test_service(request: pytest.FixtureRequest) -> AsyncIterator[Tuple[TestClient, Service]]:
    gpl_client_marker = request.node.get_closest_marker("service")

    if not gpl_client_marker:
        raise ValueError("Missing required service class argument")

    service_class = gpl_client_marker.kwargs["service_class"]
    service = service_class()

    # Populate http routes from decorated functions
    start_functions = []
    for name, fn in inspect.getmembers(service_class):
        if inspect.isfunction(fn) and getattr(fn, FUNCTION_ATTRIBUTE, None):
            invoker_func = getattr(service, name)
            # Populate _http_routes in service context
            func = await invoker_func(**{INVOKER_TASK_START_KEYWORD: True})
            if func is not None:
                start_functions.append(func)

    # Invoke all start functions after the initiation loop
    __ = [await func() for func in start_functions]

    # Start aiohttp test server and run Tomodachi start up hooks
    app, __ = await HttpTransport.get_server(service.context)
    client = TestClient(TestServer(app))
    await client.start_server()
    if hasattr(service, "_started_service"):
        await service._started_service()

    yield client, service

    # Close the aiohttp server and run Tomodachi cleanup hooks
    await client.close()
    if hasattr(service, "_stop_service"):
        await service._stop_service()

    if hasattr(service, "_stopped_service"):
        await service._stopped_service()
