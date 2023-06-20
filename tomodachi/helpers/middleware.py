import functools
import inspect
from typing import Any, Callable, Dict, List, Set, Tuple, cast

TOMODACHI_MIDDLEWARE_FUNCTION_ATTRIBUTE = "_tomodachi_middleware_function_attribute"
TOMODACHI_MIDDLEWARE_ATTRIBUTE = "_tomodachi_middleware_attribute"


async def execute_middlewares(
    func: Callable, routine_func: Callable, middlewares: List, *args: Any, **init_kwargs: Any
) -> Any:
    if middlewares:
        middleware_context: Dict = {}

        @functools.wraps(func)
        async def func_wrapper(*ma: Any, **mkw: Any) -> Any:
            if getattr(func, TOMODACHI_MIDDLEWARE_FUNCTION_ATTRIBUTE, None) is None:
                values = inspect.getfullargspec(inspect.unwrap(func))
                arg_len = len(values.args) - len(values.defaults or ())
                func_kwargs = set(values.args + values.kwonlyargs)
                has_defaults = True if values.defaults else False
                has_varargs = True if values.varargs else False
                has_varkw = True if values.varkw else False

                setattr(
                    func,
                    TOMODACHI_MIDDLEWARE_FUNCTION_ATTRIBUTE,
                    (arg_len, func_kwargs, has_defaults, has_varargs, has_varkw),
                )
            else:
                arg_len, func_kwargs, has_defaults, has_varargs, has_varkw = cast(
                    Tuple[int, Set[str], bool, bool, bool], getattr(func, TOMODACHI_MIDDLEWARE_FUNCTION_ATTRIBUTE)
                )

            if has_varargs and not has_defaults:
                arg_len = len(args)

            middleware_arguments = args[0:arg_len]

            if has_varkw:
                return await routine_func(*middleware_arguments, **{**mkw, **init_kwargs})

            mkw = {k: v for k, v in {**mkw, **init_kwargs}.items() if k in func_kwargs}
            return await routine_func(*middleware_arguments, **mkw)

        async def middleware_wrapper(idx: int = 0, *ma: Any, **mkw: Any) -> Any:
            middleware: Callable = middlewares[idx]
            arg_len: int
            middleware_kwargs: Set[str]
            has_varargs: bool
            has_varkw: bool

            if getattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE, None) is None:
                values = inspect.getfullargspec(inspect.unwrap(middleware))
                arg_len = len(values.args) - len(values.defaults or ())
                middleware_kwargs = set(values.args + values.kwonlyargs)
                has_defaults = True if values.defaults else False
                has_varargs = True if values.varargs else False
                has_varkw = True if values.varkw else False

                setattr(
                    middleware,
                    TOMODACHI_MIDDLEWARE_ATTRIBUTE,
                    (arg_len, middleware_kwargs, has_defaults, has_varargs, has_varkw),
                )
            else:
                arg_len, middleware_kwargs, has_defaults, has_varargs, has_varkw = cast(
                    Tuple[int, Set[str], bool, bool, bool], getattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE)
                )

            if has_varargs and not has_defaults:
                arg_len = 2 + len(args)

            if middlewares and len(middlewares) <= idx + 1:

                @functools.wraps(func)
                async def _func_wrapper(*a: Any, **kw: Any) -> Any:
                    return await func_wrapper(*a, **{**mkw, **kw})

                middleware_arguments = [_func_wrapper, *args, middleware_context][0:arg_len]
            else:

                @functools.wraps(func)
                async def _middleware_wrapper(*a: Any, **kw: Any) -> Any:
                    return await middleware_wrapper(idx + 1, *a, **{**mkw, **kw})

                middleware_arguments = [_middleware_wrapper, *args, middleware_context][0:arg_len]

            mkw_cleaned = {**mkw, **init_kwargs}
            if not has_varkw:
                mkw_cleaned = {k: v for k, v in mkw_cleaned.items() if k in middleware_kwargs}

            return await middleware(*middleware_arguments, **mkw_cleaned)

        return_value = await middleware_wrapper()
    else:
        return_value = await routine_func()

    return return_value
