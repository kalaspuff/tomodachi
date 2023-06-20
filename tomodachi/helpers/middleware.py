import functools
import inspect
from typing import Any, Callable, Dict, List, Set, Tuple, cast

TOMODACHI_MIDDLEWARE_ATTRIBUTE = "_tomodachi_middleware_attribute"


async def execute_middlewares(
    func: Callable, routine_func: Callable, middlewares: List, *args: Any, **init_kwargs: Any
) -> Any:
    if middlewares:
        middleware_context: Dict = {}

        async def middleware_wrapper(idx: int = 0, *ma: Any, **mkw: Any) -> Any:
            middleware: Callable = middlewares[idx]

            if getattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE, None) is None:
                values = inspect.getfullargspec(inspect.unwrap(middleware))
                arg_len = len(values.args) - len(values.defaults or ())
                middleware_kwargs = set(values.args + values.kwonlyargs)
                middleware_args = values.args
                has_defaults = True if values.defaults else False
                has_varargs = True if values.varargs else False
                has_varkw = True if values.varkw else False

                setattr(
                    middleware,
                    TOMODACHI_MIDDLEWARE_ATTRIBUTE,
                    (arg_len, middleware_kwargs, middleware_args, has_defaults, has_varargs, has_varkw),
                )
            else:
                arg_len, middleware_kwargs, middleware_args, has_defaults, has_varargs, has_varkw = cast(
                    Tuple[int, Set[str], List[str], bool, bool, bool],
                    getattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE),
                )

            if has_varargs and not has_defaults:
                arg_len = 2 + len(args)

            if middlewares and len(middlewares) <= idx + 1:

                @functools.wraps(func)
                async def _func_wrapper(*a: Any, **kw: Any) -> Any:
                    return await routine_func(*args, **{**mkw, **kw, **init_kwargs})

                middleware_arguments = [_func_wrapper, *args, middleware_context][0:arg_len]
            else:

                @functools.wraps(func)
                async def _middleware_wrapper(*a: Any, **kw: Any) -> Any:
                    return await middleware_wrapper(idx + 1, *a, **{**mkw, **kw, **init_kwargs})

                middleware_arguments = [_middleware_wrapper, *args, middleware_context][0:arg_len]

            mkw_cleaned = {k: v for k, v in mkw.items() if has_varkw or k in middleware_kwargs}

            for i, key in enumerate(middleware_args[1 : len(middleware_arguments)], 1):
                if key in mkw_cleaned:
                    middleware_arguments[i] = mkw_cleaned.pop(key)

            return await middleware(*middleware_arguments, **mkw_cleaned)

        return_value = await middleware_wrapper(**init_kwargs)
    else:
        return_value = await routine_func(*args, **init_kwargs)

    return return_value
