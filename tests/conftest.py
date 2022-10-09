import asyncio
import sys
from typing import Generator

import pytest

# def pytest_keyboard_interrupt(excinfo):
#     breakpoint()


@pytest.fixture(scope="module")
def loop() -> Generator:
    loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    yield loop

    try:
        if loop and not loop.is_closed():
            loop.close()
        if sys.version_info.major == 3 and sys.version_info.minor < 10:
            loop = asyncio.get_event_loop()
        else:
            loop = asyncio.get_running_loop()
            asyncio.set_event_loop(loop)
        if loop and not loop.is_closed():
            loop.close()
    except RuntimeWarning:
        pass
    except RuntimeError:
        pass
