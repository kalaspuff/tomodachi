from typing import Any, Dict

__cached_defs: Dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    if name in __cached_defs:
        return __cached_defs[name]

    import importlib  # noqa  # isort:skip

    name_ = name
    result: Any
    if name in ("AWSSNSRegistration", "awssns", "aws_sns"):
        name = "AWSSNSRegistration"
        module = importlib.import_module(".aws_sns_registration", "tomodachi.discovery")
        result = getattr(module, name)
    elif name in ("DummyRegistry", "dummy", "example"):
        name = "DummyRegistry"
        module = importlib.import_module(".dummy_registry", "tomodachi.discovery")
        result = getattr(module, name)
    elif name in ("aws_sns_registration",):
        name = "aws_sns_registration"
        module = importlib.import_module(".aws_sns_registration", "tomodachi.discovery")
        result = module
    elif name in ("dummy_registry",):
        name = "dummy_registry"
        module = importlib.import_module(".dummy_registry", "tomodachi.discovery")
        result = module
    else:
        raise AttributeError("module 'tomodachi.discovery' has no attribute '{}'".format(name))

    __cached_defs[name] = __cached_defs[name_] = result
    return __cached_defs[name]


__all__ = [
    "AWSSNSRegistration",
    "awssns",
    "aws_sns",
    "DummyRegistry",
    "dummy",
    "example",
    "aws_sns_registration",
    "dummy_registry",
]
