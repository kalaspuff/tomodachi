import asyncio
from typing import Generator

import pytest
import uvloop


@pytest.yield_fixture(scope='module')
def loop() -> Generator:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    try:
        if loop and not loop.is_closed():
            loop.close()
    except RuntimeWarning:
        pass
