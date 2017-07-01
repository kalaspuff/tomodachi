from typing import Any
from run_test_service_helper import start_service


def test_exception_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/exception_service.py', monkeypatch)

    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert 'fail in _start_service()' in err
