from run_test_service_helper import start_service


def test_empty_service(monkeypatch, capsys):
    services, future = start_service('tests/services/empty_service.py', monkeypatch)

    out, err = capsys.readouterr()
    assert 'No transports defined in service file' in err


def test_non_decorated_service(monkeypatch, capsys):
    services, future = start_service('tests/services/non_decorated_service.py', monkeypatch)

    out, err = capsys.readouterr()
    assert 'No transports defined in service file' in err
