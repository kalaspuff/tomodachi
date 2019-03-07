import functools
import inspect
from typing import Callable, List, Any, Dict


async def execute_middlewares(func: Callable, routine_func: Callable, middlewares: List, *args: Any) -> Any:
    if middlewares:
        middleware_context = {}  # type: Dict

        async def middleware_bubble(idx: int = 0, *ma: Any, **mkw: Any) -> Any:
            @functools.wraps(func)
            async def _func(*a: Any, **kw: Any) -> Any:
                return await middleware_bubble(idx + 1, *a, **kw)

            if middlewares and len(middlewares) <= idx + 1:
                _func = routine_func

            middleware = middlewares[idx]  # type: Callable

            arg_len = len(inspect.getfullargspec(middleware).args) - (len(inspect.getfullargspec(middleware).defaults) if inspect.getfullargspec(middleware).defaults else 0)
            middleware_arguments = [_func, *args, middleware_context][0:arg_len]

            return await middleware(*middleware_arguments, *ma, **mkw)

        return_value = await middleware_bubble()
    else:
        return_value = await routine_func()

    return return_value
