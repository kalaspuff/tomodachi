from typing import Any

from run_test_service_helper import start_service


def test_exception_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/exception_service.py", monkeypatch, loop=loop)

    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert "fail in __init__()" not in (out + err)
    assert "fail in _start_service()" in (out + err)


def test_exception_service_in_init(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/exception_service_init.py", monkeypatch, loop=loop)

    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert "fail in _start_service()" not in (out + err)
    assert "fail in __init__()" in (out + err)
