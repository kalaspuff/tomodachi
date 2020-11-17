import functools
import inspect
from typing import Any, Callable, Dict, List

TOMODACHI_MIDDLEWARE_ATTRIBUTE = "_tomodachi_middleware_argument_length"


async def execute_middlewares(func: Callable, routine_func: Callable, middlewares: List, *args: Any) -> Any:
    if middlewares:
        middleware_context: Dict = {}

        async def middleware_bubble(idx: int = 0, *ma: Any, **mkw: Any) -> Any:
            @functools.wraps(func)
            async def _func(*a: Any, **kw: Any) -> Any:
                return await middleware_bubble(idx + 1, *a, **kw)

            if middlewares and len(middlewares) <= idx + 1:
                _func = routine_func  # noqa

            middleware: Callable = middlewares[idx]

            if getattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE, None) is None:
                arg_len = len(inspect.getfullargspec(middleware).args)
                defaults = inspect.getfullargspec(middleware).defaults
                if defaults:
                    arg_len = arg_len - len(defaults)
                setattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE, arg_len)
            else:
                arg_len = getattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE, None)

            middleware_arguments = [_func, *args, middleware_context][0:arg_len]

            return await middleware(*middleware_arguments, *ma, **mkw)

        return_value = await middleware_bubble()
    else:
        return_value = await routine_func()

    return return_value
