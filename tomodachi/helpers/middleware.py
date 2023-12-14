import asyncio
import functools
import inspect
from typing import Any, Callable, Dict, List, Set, Tuple, cast

from tomodachi import get_contextvar, logging

TOMODACHI_MIDDLEWARE_ATTRIBUTE = "_tomodachi_middleware_attribute"


async def execute_middlewares(
    func: Callable, routine_func: Callable, middlewares: List, *args: Any, **init_kwargs: Any
) -> Any:
    if middlewares:
        logger = logging.getLogger()

        middleware_context: Dict = {}

        async def middleware_wrapper(idx: int = 0, *ma: Any, **mkw: Any) -> Any:
            middleware: Callable = middlewares[idx]

            logging.bind_logger(
                logger.bind(
                    middleware=(
                        getattr(middleware, "name", Ellipsis)
                        if hasattr(middleware, "name")
                        else (
                            middleware.__name__
                            if hasattr(middleware, "__name__")
                            else (
                                type(middleware).__name__
                                if hasattr(type(middleware), "__name__")
                                else str(type(middleware))
                            )
                        )
                    )
                )
            )
            get_contextvar("service.logger").set(logger._context["logger"])

            if getattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE, None) is None:
                values = inspect.getfullargspec(inspect.unwrap(middleware))
                middleware_kwargs = set(values.args + values.kwonlyargs)
                middleware_args = values.args
                has_defaults = True if values.defaults else False
                has_varargs = True if values.varargs else False
                has_varkw = True if values.varkw else False

                is_bound_method = bool(
                    inspect.ismethod(middleware)
                    or getattr(middleware, "__self__", None) is middleware
                    or inspect.ismethod(getattr(middleware, "__call__", None))
                )
                arg_start = 0 if is_bound_method else 1
                arg_len = len(values.args) - len(values.defaults or ()) + arg_start
                middleware_args_offset = 2 if is_bound_method else 1

                setattr(
                    middleware,
                    TOMODACHI_MIDDLEWARE_ATTRIBUTE,
                    (
                        arg_len,
                        arg_start,
                        middleware_kwargs,
                        middleware_args,
                        has_defaults,
                        has_varargs,
                        has_varkw,
                        is_bound_method,
                        middleware_args_offset,
                    ),
                )
            else:
                (
                    arg_len,
                    arg_start,
                    middleware_kwargs,
                    middleware_args,
                    has_defaults,
                    has_varargs,
                    has_varkw,
                    is_bound_method,
                    middleware_args_offset,
                ) = cast(
                    Tuple[int, int, Set[str], List[str], bool, bool, bool, bool, int],
                    getattr(middleware, TOMODACHI_MIDDLEWARE_ATTRIBUTE),
                )

            if has_varargs and not has_defaults:
                arg_len = 3 + len(args)

            if middlewares and len(middlewares) <= idx + 1:

                @functools.wraps(func)
                async def _func_wrapper(*a: Any, **kw: Any) -> Any:
                    return await asyncio.create_task(routine_func(*args, **{**mkw, **kw, **init_kwargs}))

                middleware_arguments = [middleware, _func_wrapper, *args, middleware_context][arg_start:arg_len]
            else:

                @functools.wraps(func)
                async def _middleware_wrapper(*a: Any, **kw: Any) -> Any:
                    return await asyncio.create_task(middleware_wrapper(idx + 1, *a, **{**mkw, **kw, **init_kwargs}))

                middleware_arguments = [middleware, _middleware_wrapper, *args, middleware_context][arg_start:arg_len]

            mkw_cleaned = {k: v for k, v in mkw.items() if has_varkw or k in middleware_kwargs}

            for i, key in enumerate(
                middleware_args[middleware_args_offset : len(middleware_arguments)], middleware_args_offset
            ):
                if key in mkw_cleaned:
                    middleware_arguments[i] = mkw_cleaned.pop(key)

            if is_bound_method:
                return await asyncio.create_task(middleware(*middleware_arguments[1:], **mkw_cleaned))

            return await asyncio.create_task(middleware(*middleware_arguments, **mkw_cleaned))

        return_value = await asyncio.create_task(middleware_wrapper(**init_kwargs))
    else:
        return_value = await asyncio.create_task(routine_func(*args, **init_kwargs))

    return return_value
