from typing import Any, Dict

__cached_defs: Dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    import importlib  # noqa  # isort:skip

    if name in __cached_defs:
        return __cached_defs[name]

    if name == "AWSSNSRegistration":
        module = importlib.import_module(".aws_sns_registration", "tomodachi.discovery")
    elif name == "DummyRegistry":
        module = importlib.import_module(".dummy_registry", "tomodachi.discovery")
    else:
        raise AttributeError("module 'tomodachi.discovery' has no attribute '{}'".format(name))

    __cached_defs[name] = getattr(module, name)
    return __cached_defs[name]


__all__ = ["DummyRegistry", "AWSSNSRegistration"]
