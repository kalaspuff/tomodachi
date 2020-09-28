import os
import signal
from typing import Any

from run_test_service_helper import start_service


def test_relative_import_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/relative_service.py", monkeypatch)

    assert services is not None
    assert len(services) == 1
    instance = services.get("test_relative")
    assert instance is not None
    assert instance.start is True
    assert instance.started is True
    assert instance.stop is False

    async def _async_kill():
        os.kill(os.getpid(), signal.SIGINT)

    loop.create_task(_async_kill())
    loop.run_until_complete(future)

    assert instance.stop is True


def test_relative_import_service_without_py_ending(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/relative_service", monkeypatch)

    instance = services.get("test_relative")
    assert instance is not None

    async def _async_kill():
        os.kill(os.getpid(), signal.SIGINT)

    loop.create_task(_async_kill())
    loop.run_until_complete(future)
