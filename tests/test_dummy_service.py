from typing import Any

import tomodachi
from run_test_service_helper import start_service


def test_dummy_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/dummy_service.py", monkeypatch, loop=loop)

    assert services is not None
    assert len(services) == 1
    instance = services.get("test_dummy")
    assert instance is not None
    assert instance.start is True
    assert instance.started is True
    assert instance.stop is False

    assert tomodachi.get_instance() == instance
    assert tomodachi.get_service() == instance
    assert tomodachi.get_service("test_dummy") == instance
    assert tomodachi.get_service("test_dummy_nonexistant") is None

    async def _async_kill():
        tomodachi.exit()

    loop.create_task(_async_kill())
    loop.run_until_complete(future)

    assert instance.stop is True


def test_dummy_service_without_py_ending(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/dummy_service", monkeypatch, loop=loop)

    instance = services.get("test_dummy")
    assert instance is not None

    async def _async_kill():
        tomodachi.exit()

    loop.create_task(_async_kill())
    loop.run_until_complete(future)
