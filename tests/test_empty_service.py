from typing import Any

from run_test_service_helper import start_service


def test_empty_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/empty_service.py", monkeypatch)

    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert "No transports defined in service file" in err


def test_non_decorated_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/non_decorated_service.py", monkeypatch)

    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert "No transports defined in service file" in err
