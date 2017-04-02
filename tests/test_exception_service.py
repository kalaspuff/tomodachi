import asyncio
from run_test_service_helper import start_service


def test_exception_service(monkeypatch, capsys):
    services, future = start_service('tests/services/exception_service.py', monkeypatch)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert 'fail in _start_service()' in err
