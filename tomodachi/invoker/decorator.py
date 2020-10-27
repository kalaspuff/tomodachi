import types
from functools import wraps
from typing import Any, Awaitable, Callable  # noqa


class DecorationClass(object):
    def __getattribute__(self, name: str) -> Any:
        if name == "__class__":
            return types.FunctionType
        return super(DecorationClass, self).__getattribute__(name)

    def __init__(self, fn: Any, decorator_fn: Any, include_function: bool) -> None:
        self.__closure__ = fn.__closure__
        self.__code__ = fn.__code__
        self.__doc__ = fn.__doc__
        self.__name__ = fn.__name__
        self.__qualname__ = fn.__qualname__
        self.__defaults__ = fn.__defaults__
        self.__annotations__ = fn.__annotations__
        self.__kwdefaults__ = fn.__kwdefaults__

        self.args: Any = None
        self.kwargs: Any = None
        self.function = fn
        self.decorator_function = decorator_fn
        self.include_function = include_function

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.args = args
        self.kwargs = kwargs

        if not self.include_function:
            return_value = self.decorator_function(*args, **kwargs)
        else:
            return_value = self.decorator_function(self.function, *args, **kwargs)
        return_value = (await return_value) if isinstance(return_value, Awaitable) else return_value
        if return_value is True or return_value is None:
            routine = self.function(*args, **kwargs)
            return (await routine) if isinstance(routine, Awaitable) else routine
        return return_value

    def __repr__(self) -> str:
        return "<function {} at {}>".format(self.__qualname__, hex(id(self)))


def decorator(include_function: Any = False) -> Callable:
    fn = None
    if include_function and callable(include_function):
        fn = include_function
        include_function = False

    def _decorator(decorator_func: Callable) -> Callable:
        def _wrapper(func: Callable) -> Callable:
            class_func = DecorationClass(func, decorator_func, include_function)
            wraps(func)(class_func)
            return class_func

        return _wrapper

    if fn:
        return _decorator(fn)
    return _decorator
