from typing import Any, Dict

__cached_defs: Dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    import importlib  # noqa  # isort:skip

    if name in __cached_defs:
        return __cached_defs[name]

    if name in ("JsonBase", "ProtobufBase"):
        module = importlib.import_module("tomodachi.envelope")
    else:
        raise AttributeError("module 'tomodachi.protocol' has no attribute '{}'".format(name))

    __cached_defs[name] = getattr(module, name)
    return __cached_defs[name]


__all__ = ["JsonBase", "ProtobufBase"]
