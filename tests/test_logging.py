import os
from typing import Any

from run_test_service_helper import start_service


def test_logging_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    log_path = "/tmp/7815c7d6-5637-4bfd-ad76-324f4329a6b8.log"

    services, future = start_service("tests/services/logging_service.py", monkeypatch)

    assert services is not None
    instance = services.get("test_logging")
    assert instance is not None

    loop.run_until_complete(future)

    with open(log_path) as f:
        log_content = str(f.read().strip())

        assert "_start_service" in log_content
        assert "_started_service" in log_content
        assert "_stop_service" in log_content

    try:
        os.remove(log_path)
    except OSError:
        pass
