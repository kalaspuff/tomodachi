import sys
from typing import Any

from tomodachi._importer import _install_import_finder

_install_import_finder({"tomodachi.transport.awssnssqs": "tomodachi.transport.aws_sns_sqs"})


def __getattr__(name: str) -> Any:
    fullname = f"tomodachi.transport.{name}"
    if fullname in sys.modules and sys.modules[fullname]:
        if fullname == sys.modules[fullname].__name__:
            return sys.modules[fullname]

        fullname = sys.modules[fullname].__name__
        if fullname in sys.modules:
            return sys.modules[fullname]

        name = fullname.rpartition(".")[2]

    import importlib  # noqa  # isort:skip

    try:
        module = importlib.import_module(f"tomodachi.transport.{name}")
    except ModuleNotFoundError:
        raise ImportError(f"cannot import name '{name}' from 'tomodachi.transport' ({__file__})") from None

    return module


__all__ = ["amqp", "aws_sns_sqs", "awssnssqs", "http", "schedule"]
