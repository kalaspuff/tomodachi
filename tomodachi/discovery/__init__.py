from typing import Any, Dict

__cached_defs: Dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    import importlib  # noqa  # isort:skip

    if name in __cached_defs:
        return __cached_defs[name]

    name_ = name
    if name in ("AWSSNSRegistration", "awssns", "aws_sns"):
        name = "AWSSNSRegistration"
        module = importlib.import_module(".aws_sns_registration", "tomodachi.discovery")
    elif name in ("DummyRegistry", "dummy", "example"):
        name = "DummyRegistry"
        module = importlib.import_module(".dummy_registry", "tomodachi.discovery")
    else:
        raise AttributeError("module 'tomodachi.discovery' has no attribute '{}'".format(name))

    __cached_defs[name] = __cached_defs[name_] = getattr(module, name)
    return __cached_defs[name]


__all__ = ["AWSSNSRegistration", "awssns", "aws_sns", "DummyRegistry", "dummy", "example"]
