from typing import Any, Dict

__cached_defs: Dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    import importlib  # noqa  # isort:skip

    if name in __cached_defs:
        return __cached_defs[name]

    if name == "JsonBase":
        module = importlib.import_module(".json_base", "tomodachi.envelope")
    elif name == "ProtobufBase":
        try:
            module = importlib.import_module(".protobuf_base", "tomodachi.envelope")
        except Exception:  # pragma: no cover
            from typing import Any  # noqa  # isort:skip

            class ProtobufBase(object):  # type: ignore
                @classmethod
                def validate(cls, **kwargs: Any) -> None:
                    raise Exception("google.protobuf package not installed")

            __cached_defs[name] = ProtobufBase
            return __cached_defs[name]
    else:
        raise AttributeError("module 'tomodachi.envelope' has no attribute '{}'".format(name))

    __cached_defs[name] = getattr(module, name)
    return __cached_defs[name]


__all__ = ["JsonBase", "ProtobufBase"]
