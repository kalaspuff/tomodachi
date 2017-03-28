import asyncio
from run_test_service_helper import start_service


def test_dummy_service(monkeypatch, capsys):
    services, future = start_service('tests/dummy_service.py', monkeypatch)

    assert services is not None
    assert len(services) == 1
    instance = services.get('dummy')
    assert instance is not None
    assert instance.start is True
    assert instance.started is True
    assert instance.stop is True

    loop = asyncio.get_event_loop()
    loop.run_until_complete(future)


def test_dummy_service_without_py_ending(monkeypatch, capsys):
    services, future = start_service('tests/dummy_service', monkeypatch)

    assert services is not None
    assert len(services) == 1
    instance = services.get('dummy')
    assert instance is not None
    assert instance.start is True
    assert instance.started is True
    assert instance.stop is True

    loop = asyncio.get_event_loop()
    loop.run_until_complete(future)
