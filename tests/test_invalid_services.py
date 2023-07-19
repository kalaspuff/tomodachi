from typing import Any

import pytest

from run_test_service_helper import start_service


def test_invalid_filename(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    with pytest.raises(OSError):
        services, future = start_service("tests/services/no_service_existing.py", monkeypatch, loop=loop)

    out, err = capsys.readouterr()
    assert "no such service file" in (out + err)


def test_invalid_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    with pytest.raises(NameError):
        services, future = start_service("tests/services/invalid_service.py", monkeypatch, loop=loop)

    out, err = capsys.readouterr()
    assert "unable to load service file" in (out + err)


def test_syntax_error_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    with pytest.raises(SyntaxError):
        services, future = start_service("tests/services/syntax_error_service.py", monkeypatch, loop=loop)

    out, err = capsys.readouterr()
    assert "unable to load service file" in (out + err)


def test_import_error(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    with pytest.raises(ImportError):
        services, future = start_service("tests/services/import_error_service.py", monkeypatch, loop=loop)

    out, err = capsys.readouterr()
    assert "unable to load service file" in (out + err)
