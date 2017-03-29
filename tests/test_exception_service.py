from run_test_service_helper import start_service


def test_exception_service(monkeypatch, capsys):
    services, future = start_service('tests/services/exception_service.py', monkeypatch)

    out, err = capsys.readouterr()
    assert 'fail in _start_service()' in err
