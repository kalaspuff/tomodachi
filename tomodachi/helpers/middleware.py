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
        async def func_callable(*ma: Any, **mkw: Any) -> Any:
            if getattr(func, TOMODACHI_MIDDLEWARE_FUNCTION_ATTRIBUTE, None) is None:
                values = inspect.getfullargspec(inspect.unwrap(func))
                func_kwargs = set(values.args + values.kwonlyargs)
                has_varkw = True if values.varkw else False

                setattr(func, TOMODACHI_MIDDLEWARE_FUNCTION_ATTRIBUTE, (func_kwargs, has_varkw))
            else:
                func_kwargs, has_varkw = cast(
                    Tuple[Set[str], bool], getattr(func, TOMODACHI_MIDDLEWARE_FUNCTION_ATTRIBUTE)
                )

            if has_varkw:
                return await routine_func(*ma, **{**mkw, **init_kwargs})

            mkw = {k: v for k, v in {**mkw, **init_kwargs}.items() if k in func_kwargs}
            return await routine_func(*ma, **mkw)

        async def middleware_bubble(idx: int = 0, *ma: Any, **mkw: Any) -> Any:
            @functools.wraps(func)
            async def _func(*a: Any, **kw: Any) -> Any:
                return await middleware_bubble(idx + 1, *a, **{**mkw, **kw})

            middleware: Callable = middlewares[idx]
            arg_len: int
            middleware_kwargs: Set[str]
            has_varargs: bool
            has_varkw: bool

            if getattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE, None) is None:
                values = inspect.getfullargspec(inspect.unwrap(middleware))
                defaults = values.defaults or ()
                arg_len = len(values.args) - len(defaults)
                middleware_kwargs = set(values.args + values.kwonlyargs)
                has_varargs = True if values.varargs else False
                has_varkw = True if values.varkw else False

                setattr(
                    middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE, (arg_len, middleware_kwargs, has_varargs, has_varkw)
                )
            else:
                arg_len, middleware_kwargs, has_varargs, has_varkw = cast(
                    Tuple[int, Set[str], bool, bool], getattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE)
                )

            if has_varargs:
                arg_len = 2 + len(args)
                ma = ()
            middleware_arguments = [_func, *args, middleware_context][0:arg_len]

            if middlewares and len(middlewares) <= idx + 1:

                @functools.wraps(func)
                async def _func_callable(*a: Any, **kw: Any) -> Any:
                    return await func_callable(*a, **{**mkw, **kw})

                middleware_arguments[0] = _func_callable

            mkw_cleaned = {**mkw, **init_kwargs}
            if not has_varkw:
                mkw_cleaned = {k: v for k, v in mkw_cleaned.items() if k in middleware_kwargs}

            return await middleware(*middleware_arguments, *ma, **mkw_cleaned)

        return_value = await middleware_bubble()
    else:
        return_value = await routine_func()

    return return_value
