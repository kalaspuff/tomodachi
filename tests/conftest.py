import asyncio
from typing import Generator

import pytest
import inspect

from aiohttp.test_utils import TestClient, TestServer
from run_test_service_helper import start_service
from services.http_service import HttpService
from tomodachi.transport.http import HttpTransport
from tomodachi.invoker import FUNCTION_ATTRIBUTE, INVOKER_TASK_START_KEYWORD, START_ATTRIBUTE
import aiohttp

@pytest.fixture(scope="module")
def loop() -> Generator:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    yield loop

    try:
        if loop and not loop.is_closed():
            loop.close()
        loop = asyncio.get_event_loop()
        if loop and not loop.is_closed():
            loop.close()
    except RuntimeWarning:
        pass
    except RuntimeError:
        pass
