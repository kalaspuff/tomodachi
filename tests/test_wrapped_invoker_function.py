import asyncio
import time
from typing import Any

from run_test_service_helper import start_service


def test_wrapped_invoker_functions(capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/wrapped_invoker_function_service.py", loop=loop)

    assert services is not None
    assert len(services) == 1
    instance = services.get("service")
    assert instance is not None

    async def _async(loop: Any) -> None:
        loop_until = time.time() + 10
        while loop_until > time.time():
            if all(
                [
                    len(instance.test_received_from_topics) == 2,
                    instance.test_http_handler_called,
                    instance.test_http_endpoint_response == "the-expected-response",
                ]
            ):
                break
            await asyncio.sleep(0.5)

    loop.run_until_complete(_async(loop))

    instance.stop_service()
    loop.run_until_complete(future)

    assert instance.test_received_from_topics == {"test-wrapped-invoker", "test-wrapped-invoker-2"}
