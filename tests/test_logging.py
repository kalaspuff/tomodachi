import os
from typing import Any

import pytest

from run_test_service_helper import start_service


def test_logging_service(capsys: Any, loop: Any) -> None:
    log_path = "/tmp/7815c7d6-5637-4bfd-ad76-324f4329a6b8.log"

    services, future = start_service("tests/services/logging_service.py", loop=loop)

    assert services is not None
    instance = services.get("test_logging")
    assert instance is not None

    loop.run_until_complete(future)

    # logging to file is deprecated and does not work anymore so nothing should be written to log file
    with pytest.raises(FileNotFoundError):
        open(log_path)

    try:
        os.remove(log_path)
    except OSError:
        pass
