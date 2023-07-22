from typing import Any, Dict

from tomodachi._importer import _install_import_finder

_install_import_finder({"tomodachi.transport.awssnssqs": "tomodachi.transport.aws_sns_sqs"})
__cached_defs: Dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    if name in __cached_defs:
        return __cached_defs[name]

    import importlib  # noqa  # isort:skip

    try:
        module = importlib.import_module(name, "tomodachi.transport")
    except ModuleNotFoundError:
        raise ImportError(f"cannot import name '{name}' from 'tomodachi.transport' ({__file__})") from None

    __cached_defs[name] = module
    return __cached_defs[name]


__all__ = ["amqp", "aws_sns_sqs", "awssnssqs", "http", "schedule"]
