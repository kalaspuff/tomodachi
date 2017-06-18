import types
import functools
from typing import Any, Callable, Optional, Dict, List  # noqa

FUNCTION_ATTRIBUTE = 'TOMODACHI_INVOKER'
START_ATTRIBUTE = 'TOMODACHI_INVOKER_START'


class Invoker(object):
    context = {}  # type: Dict

    @classmethod
    def decorator(cls, cls_func: Callable) -> Callable:
        def _wrapper(*args: Any, **kwargs: Any) -> Callable:
            def wrapper(func: Callable) -> Callable:
                @functools.wraps(func)
                async def _decorator(obj: Any, *a: Any, **kw: Any) -> Any:
                    if not getattr(_decorator, START_ATTRIBUTE, None):
                        return await func(obj, *a, **kw)

                    setattr(_decorator, START_ATTRIBUTE, False)
                    if not cls.context.get(obj, None):
                        cls.context[obj] = {i: getattr(obj, i) for i in dir(obj) if not callable(i) and not i.startswith("__") and not isinstance(getattr(obj, i), types.MethodType)}
                    context = cls.context[obj]
                    obj.context = context
                    start_func = await cls_func(cls, obj, context, func, *args, **kwargs)
                    return start_func

                setattr(_decorator, FUNCTION_ATTRIBUTE, True)
                return _decorator

            if not kwargs and len(args) == 1 and callable(args[0]):
                func = args[0]
                args = ()
                return wrapper(func)
            else:
                return wrapper
        return _wrapper
