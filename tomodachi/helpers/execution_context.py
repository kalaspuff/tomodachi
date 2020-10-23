from typing import Any, Dict, Optional, cast

_services = {}
_current_service = {}
_context: Dict[str, Any] = {}


def set_service(name: str, instance: Any) -> None:
    _services[name] = instance
    _current_service[0] = instance


def unset_service(name: str) -> None:
    del _services[name]


def clear_services() -> None:
    for name in list(_services.keys()):
        del _services[name]
    if _current_service:
        del _current_service[0]


def get_service(name: Optional[str] = None) -> Any:
    if name is None:
        if _current_service and len(_current_service):
            return _current_service[0]

        for k, v in _services.items():
            name = k
            break

    return _services.get(name) if name else None


def get_instance(name: Optional[str] = None) -> Any:
    # alias for tomodachi.get_service()
    return get_service(name)


def set_execution_context(values: Dict[str, Any]) -> None:
    for key, value in values.items():
        _context[key] = value


def get_execution_context() -> Dict[str, Any]:
    return _context


def clear_execution_context() -> None:
    for key in list(_context.keys()):
        del _context[key]


def increase_execution_context_value(key: str, value: int = 1) -> int:
    if key not in _context:
        _context[key] = 0
    if not isinstance(_context[key], int):
        raise Exception("Cannot increase non-integer context value")
    _context[key] += value
    return cast(int, _context[key])


def decrease_execution_context_value(key: str, value: int = 1) -> int:
    return increase_execution_context_value(key, -value)
