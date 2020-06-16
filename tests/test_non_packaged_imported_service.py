import os
import signal
import sys
from typing import Any

import pytest

import tomodachi
from run_test_service_helper import start_service


def test_non_named_sub_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/test-copy/test.py', monkeypatch)

    assert services is not None
    assert len(services) == 1
    instance = services.get('test_dummy')
    assert instance is not None
    assert instance.start is True
    assert instance.started is True
    assert instance.stop is False

    async def _async_kill():
        os.kill(os.getpid(), signal.SIGINT)

    loop.create_task(_async_kill())
    loop.run_until_complete(future)

    assert instance.stop is True


def test_non_named_sub_service_without_py_ending(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/test-copy/test', monkeypatch)

    instance = services.get('test_dummy')
    assert instance is not None

    async def _async_kill():
        os.kill(os.getpid(), signal.SIGINT)

    loop.create_task(_async_kill())
    loop.run_until_complete(future)


def test_non_named_same_named_sub_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/test-copy/test-copy.py', monkeypatch)

    assert services is not None
    assert len(services) == 1
    instance = services.get('test_dummy')
    assert instance is not None
    assert instance.start is True
    assert instance.started is True
    assert instance.stop is False

    async def _async_kill():
        os.kill(os.getpid(), signal.SIGINT)

    loop.create_task(_async_kill())
    loop.run_until_complete(future)

    assert instance.stop is True


def test_non_named_same_named_sub_service_without_py_ending(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/test-copy/test-copy', monkeypatch)

    instance = services.get('test_dummy')
    assert instance is not None

    async def _async_kill():
        os.kill(os.getpid(), signal.SIGINT)

    loop.create_task(_async_kill())
    loop.run_until_complete(future)


@pytest.mark.skipif(sys.version_info >= (3, 7, 0), reason="Test skipped on Python 3.7+")
def test_sub_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    with pytest.raises(tomodachi.importer.ServicePackageError):
        services, future = start_service('tests/services/test/service.py', monkeypatch)


@pytest.mark.skipif(sys.version_info >= (3, 7, 0), reason="Test skipped on Python 3.7+")
def test_sub_service_without_py_ending(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    with pytest.raises(tomodachi.importer.ServicePackageError):
        services, future = start_service('tests/services/test/service', monkeypatch)


@pytest.mark.skipif(sys.version_info >= (3, 7, 0), reason="Test skipped on Python 3.7+")
def test_same_named_sub_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    with pytest.raises(tomodachi.importer.ServicePackageError):
        services, future = start_service('tests/services/test/test.py', monkeypatch)


@pytest.mark.skipif(sys.version_info >= (3, 7, 0), reason="Test skipped on Python 3.7+")
def test_same_named_sub_service_without_py_ending(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    with pytest.raises(tomodachi.importer.ServicePackageError):
        services, future = start_service('tests/services/test/test', monkeypatch)


def test_sub_service_with_reserved_name(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    with pytest.raises(tomodachi.importer.ServicePackageError):
        services, future = start_service('tests/services/os/os.py', monkeypatch)


def test_sub_service_with_reserved_name_without_py_ending(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    with pytest.raises(tomodachi.importer.ServicePackageError):
        services, future = start_service('tests/services/os/os', monkeypatch)
