from typing import Any, Dict

__cached_defs: Dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    if name in __cached_defs:
        return __cached_defs[name]

    import importlib  # noqa  # isort:skip

    name_ = name
    if name in ("awssnssqs",):
        name = "aws_sns_sqs"

    try:
        module = importlib.import_module(f".{name}", "tomodachi.transport")
    except ModuleNotFoundError:
        raise ImportError(f"cannot import name '{name}' from 'tomodachi.transport' ({__file__})") from None

    __cached_defs[name] = __cached_defs[name_] = module  # getattr(module, name)
    return __cached_defs[name]


__all__ = ["amqp", "aws_sns_sqs", "awssnssqs", "http", "schedule"]
