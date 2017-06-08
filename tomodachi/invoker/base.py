import types
import functools

FUNCTION_ATTRIBUTE = 'TOMODACHI_INVOKER'


class Invoker(object):
    context = {}

    @classmethod
    def decorator(cls, cls_func):
        def _wrapper(*args, **kwargs):
            def wrapper(func):
                @functools.wraps(func)
                async def _decorator(obj):
                    if not cls.context.get(obj, None):
                        cls.context[obj] = {i: getattr(obj, i) for i in dir(obj) if not callable(i) and not i.startswith("__") and not isinstance(getattr(obj, i), types.MethodType)}
                    context = cls.context[obj]
                    obj.context = context
                    start_func = await cls_func(cls, obj, context, func, *args, **kwargs)
                    return start_func

                setattr(_decorator, FUNCTION_ATTRIBUTE, True)
                return _decorator

            if not kwargs and len(args) == 1 and isinstance(args[0], types.FunctionType):
                func = args[0]
                args = ()
                return wrapper(func)
            else:
                return wrapper
        return _wrapper
