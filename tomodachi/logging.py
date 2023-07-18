from __future__ import annotations

import datetime
import json
import logging
import sys
from contextvars import ContextVar
from logging import CRITICAL, DEBUG, ERROR, FATAL, INFO, NOTSET, WARN, WARNING
from typing import Any, Dict, KeysView, Literal, Optional, Protocol, Sequence, Tuple, Union, cast

import structlog

LOGGER_DISABLED_KEY = "_logger_disabled"
RENAME_KEYS: Sequence[Tuple[str, str]] = (("event", "message"), ("event_", "event"), ("class_", "class"))
EXCEPTION_KEYS: Sequence[str] = ("exception", "exc", "error", "message")
TOMODACHI_LOGGER: Literal["json", "console"] = "console"

_context: ContextVar[Union[LoggerContext, Dict]] = ContextVar("tomodachi.logging._context", default={})
_loggers: ContextVar[Dict] = ContextVar("tomodachi.logging._loggers", default={})


class LogProcessorTimestamp:
    __slots__ = ("key",)

    def __init__(
        self,
        key: str = "timestamp",
    ) -> None:
        self.key = key

    def __call__(
        self, logger: structlog.typing.WrappedLogger, method_name: str, event_dict: structlog.typing.EventDict
    ) -> structlog.typing.EventDict:
        event_dict[self.key] = datetime.datetime.utcnow().isoformat(timespec="microseconds") + "Z"
        return event_dict


class AddMissingDictKey:
    __slots__ = ("key",)

    def __init__(
        self,
        key: str,
    ) -> None:
        self.key = key

    def __call__(
        self, logger: structlog.typing.WrappedLogger, method_name: str, event_dict: structlog.typing.EventDict
    ) -> structlog.typing.EventDict:
        if self.key not in event_dict:
            event_dict[self.key] = ""
        return event_dict


class RemoveDictKey:
    __slots__ = ("key",)

    def __init__(
        self,
        key: str,
    ) -> None:
        self.key = key

    def __call__(
        self, logger: structlog.typing.WrappedLogger, method_name: str, event_dict: structlog.typing.EventDict
    ) -> structlog.typing.EventDict:
        if self.key in event_dict:
            event_dict.pop(self.key)
        return event_dict


class SquelchDisabledLogger:
    def __call__(
        self, logger: structlog.typing.WrappedLogger, method_name: str, event_dict: structlog.typing.EventDict
    ) -> structlog.typing.EventDict:
        is_disabled = False
        name = event_dict.get("logger")
        if name:
            ctx = get_context(str(name))
            if LOGGER_DISABLED_KEY in ctx:
                is_disabled = bool(ctx.get(LOGGER_DISABLED_KEY))
                event_dict.pop(LOGGER_DISABLED_KEY, None)
            else:
                is_disabled = event_dict.pop(LOGGER_DISABLED_KEY, False)
        else:
            event_dict.pop(LOGGER_DISABLED_KEY, None)
        if is_disabled:
            _func = getattr(logger, method_name, None)

            def func(self: structlog.typing.WrappedLogger, message: str) -> None:
                setattr(logger, method_name, _func)

            setattr(logger, method_name, func.__get__(logger))

        return event_dict


class RenameKeys:
    __slots__ = ("pairs",)

    def __init__(
        self,
        pairs: Union[Sequence[Tuple[str, str]], Dict[str, str]],
    ) -> None:
        if not isinstance(pairs, dict):
            pairs = {k: v for k, v in pairs}
        self.pairs = pairs

    def __call__(
        self, logger: structlog.typing.WrappedLogger, method_name: str, event_dict: structlog.typing.EventDict
    ) -> structlog.typing.EventDict:
        return {(self.pairs.get(k, k)): v for k, v in event_dict.items()}
        # for old_key, new_key in self.pairs:
        #     if old_key in event_dict:
        #         event_dict[new_key] = event_dict.pop(old_key)
        # return event_dict


_ordered_items = structlog.processors._items_sorter(
    sort_keys=False, key_order=("timestamp", "logger", "level", "message"), drop_missing=True
)


def serializer_func(event_dict: structlog.typing.EventDict, **dumps_kw: Any) -> str:
    return json.dumps(dict(_ordered_items(event_dict)), **dumps_kw)


def merge_contextvars(
    logger: structlog.typing.WrappedLogger, method_name: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    ctx = structlog.contextvars._CONTEXT_VARS.copy()

    for k, v in ctx.items():
        if k.startswith(structlog.contextvars.STRUCTLOG_KEY_PREFIX) and v.get() is not Ellipsis:
            event_dict[k[structlog.contextvars.STRUCTLOG_KEY_PREFIX_LEN :]] = v.get()

    return event_dict


def add_exception_info(
    logger: structlog.typing.WrappedLogger, method_name: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    exception = None
    for key in EXCEPTION_KEYS:
        if key in event_dict and isinstance(event_dict.get(key), BaseException):
            exception = event_dict.get(key)
            break

    exc_info = event_dict.get("exc_info")

    if method_name == "error" and exc_info is True:
        method_name = "exception"

    if exception and isinstance(exception, BaseException):
        exc_info = (type(exception), exception, exception.__traceback__)
    elif (
        not isinstance(exception, BaseException)
        and isinstance(exc_info, (tuple, list))
        and len(exc_info) == 3
        and isinstance(exc_info[1], BaseException)
    ):
        exception = exc_info[1]
    elif method_name == "exception":
        exc_info = sys.exc_info()
        exception = exc_info[1] if exc_info and isinstance(exc_info[1], BaseException) else None

    if not exception or not isinstance(exception, BaseException):
        return event_dict

    for key in EXCEPTION_KEYS:
        if key in event_dict and exception == event_dict.get(key):
            event_dict.pop(key)

    tb = exception.__traceback__

    event_dict["exception"] = exception
    if "exc_info" not in event_dict:
        event_dict["exc_info"] = exc_info
    if "exc_type" not in event_dict:
        event_dict["exc_type"] = (
            type(exception).__name__ if hasattr(type(exception), "__name__") else str(type(exception))
        )
    if "exc_message" not in event_dict:
        event_dict["exc_message"] = str(exception)
    if "tb_module_name" not in event_dict:
        event_dict["tb_module_name"] = tb.tb_frame.f_globals.get("__name__", "<unknown>") if tb else "<unknown>"
    if "tb_function_name" not in event_dict:
        event_dict["tb_function_name"] = (
            getattr(tb.tb_frame.f_code, "co_qualname", tb.tb_frame.f_code.co_name) if tb else "<unknown>"
        )
    if "tb_lineno" not in event_dict:
        event_dict["tb_lineno"] = tb.tb_lineno if tb else -1
    if "tb_filename" not in event_dict:
        event_dict["tb_filename"] = tb.tb_frame.f_code.co_filename if tb else "<unknown>"

    return event_dict


def remove_ellipsis_values(
    logger: structlog.typing.WrappedLogger, method_name: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    return {k: v for k, v in event_dict.items() if v is not Ellipsis}


def modify_logger(
    logger: structlog.typing.WrappedLogger, method_name: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    name = str(event_dict.get("logger") or "")
    if name:
        event_dict["logger"] = name.split("tomodachi.", 1)[-1]  # .split("service.", 1)[-1]
    return event_dict


class LoggerContext(dict):
    def __init__(self, *a: Any, **kw: Any) -> None:
        if a:
            self.__data = {**a[0], **kw}
        else:
            self.__data = {**kw}

        name = self._data.get("logger")
        if name and kw:
            ctx = _loggers.get().get(name)
            if ctx != self:
                _loggers.set({**_loggers.get(), **{self._data["logger"]: self}})
                if name and name == _context.get().get("logger"):
                    _context.set(self)

    def __str__(self) -> str:
        return str(self._data)

    def __repr__(self) -> str:
        return str(self._data)

    def __getitem__(self, item: str) -> Any:
        value = self._data.get(item)
        return value

    def __setitem__(self, item: str, value: Any) -> None:
        self.__data[item] = value

    def __delitem__(self, item: str) -> None:
        del self._data[item]

    def __getattr__(self, item: str) -> Any:
        return self.__getitem__(item)

    def __bool__(self) -> bool:
        if self._data:
            return True
        else:
            return False

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Any:
        return self._data.__iter__()

    def __contains__(self, item: Any) -> Any:
        return self._data.__contains__(item)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, LoggerContext):
            return bool(self._data == other._data)
        elif isinstance(other, dict):
            return bool(self._data == other)
        else:
            return False

    def __ne__(self, other: Any) -> bool:
        return not self == other

    def keys(self) -> KeysView:  # type: ignore
        return self._data.keys()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def copy(self) -> dict:
        return {**self._data}

    def update(self, *a: Any, **kw: Any) -> None:
        self._data.update(*a, **kw)

    def pop(self, item: str, *default: Any) -> Any:
        if not default:
            return self._data.pop(item)
        return self._data.pop(item, default[0])

    def clear(self) -> None:
        self._data.clear()

    @property
    def _data(self) -> Dict[str, Any]:
        return self.__data


class Logger(structlog.stdlib.BoundLogger):
    @property
    def name(self) -> str:
        name: str = self._context.get("logger") or ""
        if not name:
            return str(self._logger.name or "")
        return name

    @property
    def level(self) -> int:
        try:
            return int(self._logger.level)
        except AttributeError:
            name = self._context.get("logger") or None
            return logging.getLogger(name).level

    @property
    def parent(self) -> Any:
        try:
            return self._logger.parent
        except AttributeError:
            name = self._context.get("logger") or None
            return logging.getLogger(name).parent

    @property
    def propagate(self) -> bool:
        try:
            return bool(self._logger.propagate)
        except AttributeError:
            name = self._context.get("logger") or None
            return logging.getLogger(name).propagate

    @property
    def handlers(self) -> Any:
        try:
            return self._logger.handlers
        except AttributeError:
            name = self._context.get("logger") or None
            return logging.getLogger(name).handlers

    @property
    def disabled(self) -> int:
        try:
            return int(bool(self._logger.disabled))
        except AttributeError:
            name = self._context.get("logger") or None
            return logging.getLogger(name).disabled

    def setLevel(self, level: int) -> None:
        name = self._context.get("logger") or None
        logging.getLogger(name).setLevel(level)

        try:
            self._logger.setLevel(level)
        except AttributeError:
            pass

    def findCaller(self, stack_info: bool = False) -> Tuple[str, int, str, Optional[str]]:
        try:
            return cast(Tuple[str, int, str, Optional[str]], self._logger.findCaller(stack_info=stack_info))  # type: ignore
        except AttributeError:
            name = self._context.get("logger") or None
            return logging.getLogger(name).findCaller(stack_info=stack_info)

    def makeRecord(
        self,
        name: str,
        level: int,
        fn: str,
        lno: int,
        msg: str,
        args: tuple[Any, ...],
        exc_info: structlog.typing.ExcInfo,
        func: str | None = None,
        extra: Any = None,
    ) -> logging.LogRecord:
        try:
            return cast(  # type: ignore
                logging.LogRecord,
                self._logger.makeRecord(name, level, fn, lno, msg, args, exc_info, func=func, extra=extra),
            )
        except AttributeError:
            name_ = self._context.get("logger") or None
            return logging.getLogger(name_).makeRecord(
                name, level, fn, lno, msg, args, exc_info, func=func, extra=extra
            )

    def handle(self, record: logging.LogRecord) -> None:
        try:
            self._logger.handle(record)
        except AttributeError:
            name = self._context.get("logger") or None
            logging.getLogger(name).handle(record)

    def addHandler(self, hdlr: logging.Handler) -> None:
        try:
            self._logger.addHandler(hdlr)
        except AttributeError:
            name = self._context.get("logger") or None
            logging.getLogger(name).addHandler(hdlr)

    def removeHandler(self, hdlr: logging.Handler) -> None:
        try:
            self._logger.removeHandler(hdlr)
        except AttributeError:
            name = self._context.get("logger") or None
            logging.getLogger(name).removeHandler(hdlr)

    def hasHandlers(self) -> bool:
        try:
            return bool(self._logger.hasHandlers())
        except AttributeError:
            name = self._context.get("logger") or None
            return logging.getLogger(name).hasHandlers()

    def callHandlers(self, record: logging.LogRecord) -> None:
        try:
            self._logger.callHandlers(record)
        except AttributeError:
            name = self._context.get("logger") or None
            logging.getLogger(name).callHandlers(record)

    def getEffectiveLevel(self) -> int:
        try:
            return int(self._logger.getEffectiveLevel())
        except AttributeError:
            name = self._context.get("logger") or None
            return logging.getLogger(name).getEffectiveLevel()

    def isEnabledFor(self, level: int) -> bool:
        try:
            return bool(self._logger.isEnabledFor(level))
        except AttributeError:
            name = self._context.get("logger") or None
            return logging.getLogger(name).isEnabledFor(level)

    def getChild(self, suffix: str) -> logging.Logger:
        try:
            return cast(logging.Logger, self._logger.getChild(suffix))  # type: ignore
        except AttributeError:
            name = self._context.get("logger") or None
            return logging.getLogger(name).getChild(suffix)


class LoggerProtocol(Protocol):
    def info(self, *args: Any, **kwargs: Any) -> None:
        ...

    def debug(self, *args: Any, **kwargs: Any) -> None:
        ...

    def warning(self, *args: Any, **kwargs: Any) -> None:
        ...

    def error(self, *args: Any, **kwargs: Any) -> None:
        ...

    def critical(self, *args: Any, **kwargs: Any) -> None:
        ...

    def exception(self, *args: Any, **kwargs: Any) -> None:
        ...


console_logger: Logger = structlog.wrap_logger(
    None,
    processors=[
        structlog.processors.add_log_level,
        merge_contextvars,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        LogProcessorTimestamp(),
        RenameKeys(pairs=RENAME_KEYS),
        add_exception_info,
        AddMissingDictKey(key="message"),
        remove_ellipsis_values,
        SquelchDisabledLogger(),
        # modify_logger,
        structlog.dev.ConsoleRenderer(sort_keys=False, event_key="message"),
    ],
    wrapper_class=Logger,
    context_class=LoggerContext,
    cache_logger_on_first_use=False,
)

json_logger: Logger = structlog.wrap_logger(
    None,
    processors=[
        structlog.processors.add_log_level,
        merge_contextvars,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        LogProcessorTimestamp(),
        RenameKeys(pairs=RENAME_KEYS),
        add_exception_info,
        RemoveDictKey(key="exc_info"),
        remove_ellipsis_values,
        SquelchDisabledLogger(),
        structlog.processors.JSONRenderer(serializer=serializer_func),
    ],
    wrapper_class=Logger,
    context_class=LoggerContext,
    cache_logger_on_first_use=False,
)


def get_context(logger: Union[LoggerContext, Dict, structlog.BoundLoggerBase, str]) -> Union[LoggerContext, Dict]:
    if isinstance(logger, structlog.BoundLoggerBase):
        if not isinstance(logger._context, LoggerContext):
            return cast(dict, logger._context)
        return logger._context
    elif isinstance(logger, (LoggerContext, dict)):
        return logger
    elif isinstance(logger, str):
        ctx = _loggers.get().get(logger)
        if not ctx:
            ctx = LoggerContext(logger=logger, **{LOGGER_DISABLED_KEY: False})
        return ctx
    else:
        raise TypeError(f"Unsupported logger type: {type(logger)}")


def bind_logger(logger: Union[LoggerContext, Dict, structlog.BoundLoggerBase, str]) -> None:
    _context.set(get_context(logger))


def disable_logger(logger: Union[LoggerContext, Dict, structlog.BoundLoggerBase, str]) -> None:
    ctx = get_context(logger)
    # ctx[LOGGER_DISABLED_KEY] = True
    get_logger(ctx["logger"]).bind(**{LOGGER_DISABLED_KEY: True})


def enable_logger(logger: LoggerContext | dict | structlog.BoundLoggerBase | str) -> None:
    ctx = get_context(logger)
    # ctx[LOGGER_DISABLED_KEY] = False
    get_logger(ctx["logger"]).bind(**{LOGGER_DISABLED_KEY: False})


def is_logger_disabled(logger: Union[LoggerContext, Dict, structlog.BoundLoggerBase, str]) -> bool:
    return True if get_context(logger).get(LOGGER_DISABLED_KEY) else False


def is_logger_enabled(logger: Union[LoggerContext, Dict, structlog.BoundLoggerBase, str]) -> bool:
    return not is_logger_disabled(logger)


def get_logger(name: Optional[str] = None) -> Logger:
    logger = console_logger if TOMODACHI_LOGGER == "console" else json_logger if TOMODACHI_LOGGER == "json" else None
    if not logger:
        raise Exception("Invalid TOMODACHI_LOGGER value: '{}' (exected 'console' or 'json')".format(TOMODACHI_LOGGER))

    if name:
        ctx = _loggers.get().get(name)
        if ctx:
            return cast(Logger, logger.new(**ctx))

        return cast(Logger, logger.new(**LoggerContext(logger=name, **{LOGGER_DISABLED_KEY: False})))

    return cast(Logger, logger.new(**_context.get()))


# CamelCase alias for `get_logger`.
getLogger = get_logger

# Set default logger context
_context.set(LoggerContext(logger="default", **{LOGGER_DISABLED_KEY: False}))


__all__ = [
    "get_logger",
    "getLogger",
    "bind_logger",
    "disable_logger",
    "enable_logger",
    "is_logger_disabled",
    "is_logger_enabled",
    "CRITICAL",
    "DEBUG",
    "ERROR",
    "FATAL",
    "INFO",
    "NOTSET",
    "WARN",
    "WARNING",
]
