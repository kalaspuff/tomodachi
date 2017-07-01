from typing import Any
from run_test_service_helper import start_service


def test_start_amqp_service_invalid_credentials(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/amqp_service_invalid_credentials.py', monkeypatch)

    assert services is not None
    assert len(services) == 1
    instance = services.get('test_amqp')
    assert instance is not None

    assert instance.uuid is not None
    instance.stop_service()
    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert 'Unable to connect [amqp] to 127.0.0.1:54321' in err
    assert out == ''
