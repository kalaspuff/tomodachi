import functools
from typing import Any, Dict, List, Tuple, Union, Optional, Callable, SupportsInt, Awaitable  # noqa


def decorator(include_function=False) -> Callable:
    fn = None
    if include_function and callable(include_function):
        fn = include_function
        include_function = False

    def _decorator(decorator_func: Callable) -> Callable:
        def _wrapper(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*a: Any, **kw: Any) -> Any:
                if not include_function:
                    return_value = decorator_func(*a, **kw)
                else:
                    return_value = decorator_func(func, *a, **kw)

                return_value = (await return_value) if isinstance(return_value, Awaitable) else return_value
                if return_value is True or return_value is None:
                    routine = func(*a, **kw)
                    return (await routine) if isinstance(routine, Awaitable) else routine
                return return_value

            return wrapper
        return _wrapper

    if fn:
        return _decorator(fn)
    return _decorator
