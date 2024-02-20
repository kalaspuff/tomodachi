from __future__ import annotations

import datetime
import importlib.metadata
import json
import logging
import os
import sys
import warnings
from contextvars import ContextVar
from functools import wraps
from io import StringIO
from logging import CRITICAL, DEBUG, ERROR, FATAL, INFO, NOTSET, WARN, WARNING
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    KeysView,
    Literal,
    Optional,
    Protocol,
    Sequence,
    TextIO,
    Tuple,
    Type,
    Union,
    cast,
    overload,
)

import structlog
from structlog._log_levels import _LEVEL_TO_NAME, _NAME_TO_LEVEL
from structlog.exceptions import DropEvent

from tomodachi.helpers.colors import NO_COLOR

if TYPE_CHECKING:  # pragma: no cover
    try:
        from structlog.typing import Context, EventDict, ExcInfo, Processor, WrappedLogger
    except (ImportError, ModuleNotFoundError):
        from structlog.types import Context, EventDict, ExcInfo, Processor, WrappedLogger

MAX_STACKTRACE_DEPTH = 50
RENAME_KEYS: Sequence[Tuple[str, str]] = (("event", "message"), ("event_", "event"), ("class_", "class"))
EXCEPTION_KEYS: Sequence[str] = ("exception", "exc", "error", "message")
CONSOLE_QUOTE_KEYS = ("tb_location", "error_location", "tb_filename", "co_filename", "co_location", "error_filename")
TOMODACHI_LOGGER_TYPE: Literal["json", "console", "no_color_console", "custom", "python", "disabled"] = "console"
TOMODACHI_CUSTOM_LOGGER: Optional[Union[str, ModuleType, type, object]] = None

STD_LOGGER_FIELDS = set(
    [
        "name",
        "levelno",
        "levelname",
        "pathname",
        "filename",
        "module",
        "lineno",
        "funcName",
        "created",
        "asctime",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "taskName",
        "process",
        "message",
        "args",
        "exc_text",
        "stack_info",
        "msg",
        "processName",
        "exc_info",
    ]
)

_context: ContextVar[Union[LoggerContext, Dict]] = ContextVar("tomodachi.logging._context", default={})
_loggers: ContextVar[Dict] = ContextVar("tomodachi.logging._loggers", default={})


class LogProcessorTimestamp:
    __slots__ = ("key",)

    def __init__(
        self,
        key: str = "timestamp",
    ) -> None:
        self.key = key

    def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
        if self.key not in event_dict:
            event_dict[self.key] = (
                datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
            )
        return event_dict


class AddMissingDictKey:
    __slots__ = ("key",)

    def __init__(
        self,
        key: str,
    ) -> None:
        self.key = key

    def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
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

    def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
        if self.key in event_dict:
            event_dict.pop(self.key)
        return event_dict


class LinkQuoteStrings:
    __slots__ = ("keys",)

    def __init__(
        self,
        keys: Iterable[str],
    ) -> None:
        self.keys = keys

    def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
        return {k: f"<{v}>" if k in self.keys and v and not v.startswith("<") else v for k, v in event_dict.items()}


class RenameKeys:
    __slots__ = ("pairs",)

    def __init__(
        self,
        pairs: Union[Sequence[Tuple[str, str]], Dict[str, str]],
    ) -> None:
        if not isinstance(pairs, dict):
            pairs = {k: v for k, v in pairs}
        self.pairs = pairs

    def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
        return {(self.pairs.get(k, k)): v for k, v in event_dict.items()}


_ordered_items = structlog.processors._items_sorter(
    sort_keys=False, key_order=("timestamp", "logger", "level", "message"), drop_missing=True
)


def serializer_func(event_dict: EventDict, **dumps_kw: Any) -> str:
    return json.dumps(dict(_ordered_items(event_dict)), **dumps_kw)


def merge_contextvars(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    ctx = structlog.contextvars._CONTEXT_VARS.copy()

    for k, v in ctx.items():
        if k.startswith(structlog.contextvars.STRUCTLOG_KEY_PREFIX) and v.get() is not Ellipsis:
            event_dict[k[structlog.contextvars.STRUCTLOG_KEY_PREFIX_LEN :]] = v.get()

    return event_dict


def add_exception_info(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    exception = None
    for key in EXCEPTION_KEYS:
        if key in event_dict and isinstance(event_dict.get(key), BaseException):
            exception = event_dict.get(key)
            break

    exc_info = event_dict.get("exc_info")

    if method_name == "error" and exc_info is True:
        method_name = "exception"

    if exception and isinstance(exception, BaseException):
        pass
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

    exc_info = (type(exception), exception, exception.__traceback__)

    event_dict["exception"] = exception
    event_dict["exc_info"] = exc_info

    if "exc_type" not in event_dict:
        event_dict["exc_type"] = (
            type(exception).__name__ if hasattr(type(exception), "__name__") else str(type(exception))
        )
    if "exc_message" not in event_dict:
        event_dict["exc_message"] = str(exception)

    tb = exception.__traceback__
    while tb and tb.tb_next:
        tb = tb.tb_next

    if "tb_module_name" not in event_dict:
        event_dict["tb_module_name"] = tb.tb_frame.f_globals.get("__name__", "<unknown>") if tb else "<unknown>"
    if "tb_function_name" not in event_dict:
        event_dict["tb_function_name"] = (
            getattr(tb.tb_frame.f_code, "co_qualname", tb.tb_frame.f_code.co_name) if tb else "<unknown>"
        )
    if "tb_location" not in event_dict:
        co_filename = tb.tb_frame.f_code.co_filename if tb else "<unknown>"
        if tb:
            cwd = os.getcwd()
            if cwd.rstrip("/") and co_filename.startswith(cwd):
                co_filename = "./" + co_filename[len(cwd) :].lstrip("/")

        event_dict["tb_location"] = f"{co_filename}:{tb.tb_lineno}" if tb else "<unknown>"

    return event_dict


def add_stacktrace_info(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    exception = event_dict.get("exception")

    if not exception or not isinstance(exception, BaseException):
        return event_dict

    if "stacktrace" in event_dict:
        return event_dict

    stacktrace = []
    cwd = os.getcwd()

    tb = exception.__traceback__
    while tb:
        co_filename = tb.tb_frame.f_code.co_filename or "<unknown>"
        if cwd.rstrip("/") and co_filename.startswith(cwd):
            co_filename = "./" + co_filename[len(cwd) :].lstrip("/")

        stacktrace.append(
            {
                "module_name": tb.tb_frame.f_globals.get("__name__", "<unknown>"),
                "function_name": getattr(tb.tb_frame.f_code, "co_qualname", tb.tb_frame.f_code.co_name),
                "location": f"{co_filename}:{tb.tb_lineno}",
            }
        )
        tb = tb.tb_next

    if len(stacktrace) > MAX_STACKTRACE_DEPTH:
        stacktrace = stacktrace[len(stacktrace) - MAX_STACKTRACE_DEPTH :]

    event_dict["stacktrace"] = stacktrace
    return event_dict


def remove_ellipsis_values(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    return {k: v for k, v in event_dict.items() if v is not Ellipsis}


def to_logger_args_kwargs(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> Tuple[Tuple, Dict[str, Any]]:
    return ((event_dict.get("event") or "",), {"extra": {"logger.context": event_dict}})


def to_custom_logger(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> Union[str, Tuple[Tuple, Dict[str, Any]]]:
    if isinstance(logger, logging.Logger):
        if event_dict.get("extra", {}).get("_processed"):
            return str(event_dict["extra"].get("logger.context", {}).get("event", ""))
        args, kwargs = to_logger_args_kwargs(logger, method_name, event_dict)
        kwargs["extra"]["_processed"] = True
        getattr(logger, method_name)(args, kwargs)
    else:
        event = event_dict.pop("event", "") or ""
        getattr(logger, method_name)(event, **event_dict)

    raise DropEvent


def disabled_logger_processor(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    raise DropEvent


class _PythonLoggingLoggerFormatter(logging.Formatter):
    style: Union[logging.PercentStyle, logging.StrFormatStyle, logging.StringTemplateStyle]
    fmt: str

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: str = "%",
        validate: bool = True,
        *,
        defaults: Optional[Dict[str, Any]] = None,
    ):
        if style not in logging._STYLES:
            raise ValueError("Style must be one of: %s" % ",".join(logging._STYLES.keys()))
        style_cls = cast(
            Union[Type[logging.PercentStyle], Type[logging.StrFormatStyle], Type[logging.StringTemplateStyle]],
            logging._STYLES[style][0],
        )
        self.style = style_cls(fmt or "")
        if defaults and sys.version_info.major == 3 and sys.version_info.minor >= 10:
            setattr(self.style, "_defaults", defaults)

        if validate:
            self.style.validate()

        self.fmt = self.style._fmt
        self.datefmt = datefmt

    @property
    def _style(self) -> Union[logging.PercentStyle, logging.StrFormatStyle, logging.StringTemplateStyle]:  # type: ignore
        if self.style._fmt != self.fmt:
            self.fmt = self.style._fmt
        return self.style

    @property  # type: ignore
    def _fmt(self) -> str:
        if self.style._fmt != self.fmt:
            self.fmt = self._style._fmt
        return self.fmt

    @_fmt.setter
    def _fmt(self, fmt: str) -> None:
        self.fmt = fmt
        self.style._fmt = fmt

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        return (
            datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )

    def __repr__(self) -> str:
        return "PythonLoggingFormatter"


class _StdLoggingFormatter(logging.Formatter):
    _logger_type: Literal["json", "console", "no_color_console", "custom", "python", "disabled"]

    def __init__(
        self,
        logger_type: Literal[
            "json", "console", "no_color_console", "custom", "python", "disabled"
        ] = TOMODACHI_LOGGER_TYPE,
        name: str = "",
        *a: Any,
        **kw: Any,
    ) -> None:
        self._logger_type = logger_type
        self._name = name

    def format(self, record: logging.LogRecord) -> str:
        if "logger.context" in record.__dict__:
            kw: Dict[str, Any] = record.__dict__["logger.context"]
        else:
            extra_keys = set(record.__dict__.keys() - STD_LOGGER_FIELDS)
            if (
                record.__dict__.get("args")
                and isinstance(record.__dict__.get("args"), dict)
                and record.__dict__.get("args", {}).get("extra", {})
            ):
                kw = {
                    "extra": {
                        **{k: v for k, v in record.__dict__.items() if k in extra_keys},
                        **record.__dict__.get("args", {}).get("extra", {}),
                    }
                }
            else:
                kw = {"extra": {k: v for k, v in record.__dict__.items() if k in extra_keys}}
            if record.exc_info and "exception" not in kw:
                kw["exception"] = record.exc_info[1]
                kw["exc_info"] = True

        if "timestamp" not in kw:
            kw["timestamp"] = self.formatTime(record)
        if "event" not in kw:
            kw["event"] = record.getMessage()

        kw["logger"] = record.name

        if "extra" in kw and isinstance(kw["extra"], dict) and len(kw["extra"]) == 0:
            kw.pop("extra")

        method_name = _LEVEL_TO_NAME[record.levelno]
        if method_name == "error" and kw and kw.get("exc_info") is True:
            method_name = "exception"

        logger = _get_logger(record.name, logger_type=self._logger_type)

        try:
            args, _ = logger._process_event(
                method_name,
                None,
                kw,
            )
            return cast(str, args[0])
        except DropEvent:
            if record.module == "_base":
                raise
            return ""

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        return (
            datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )

    def __repr__(self) -> str:
        name = self._name or self.__class__.__name__
        return name


class StderrHandler(logging.StreamHandler):
    def __init__(self, level: int = NOTSET) -> None:
        logging.Handler.__init__(self, level)

    @property
    def stream(self) -> TextIO:  # type: ignore
        return sys.stderr


DEFAULT_FORMAT = "%(asctime)s [%(levelname)-9s] %(message)-30s [%(name)s]"
_default_fmt = DEFAULT_FORMAT
try:
    if len(logging.root.handlers) and logging.root.handlers[0].formatter and logging.root.handlers[0].formatter._fmt:
        _default_fmt = logging.root.handlers[0].formatter._fmt
except AttributeError:
    pass

PythonLoggingFormatter = _PythonLoggingLoggerFormatter(fmt=_default_fmt)

ConsoleFormatter = _StdLoggingFormatter(logger_type="console", name="ConsoleFormatter")
NoColorConsoleFormatter = _StdLoggingFormatter(logger_type="no_color_console", name="NoColorConsoleFormatter")
JSONFormatter = _StdLoggingFormatter(logger_type="json", name="JSONFormatter")
DisabledFormatter = _StdLoggingFormatter(logger_type="disabled", name="DisabledFormatter")
CustomLoggerFormatter = _StdLoggingFormatter(logger_type="custom", name="CustomLoggerFormatter")

DefaultHandler = DefaultRootLoggerHandler = _defaultHandler = StderrHandler()


@overload
def set_default_formatter(
    *, logger_type: Literal["json", "console", "no_color_console", "custom", "python", "disabled"]
) -> None: ...


@overload
def set_default_formatter(
    logger_type: Literal["json", "console", "no_color_console", "custom", "python", "disabled"],
    /,
) -> None: ...


@overload
def set_default_formatter(*, formatter: logging.Formatter) -> None: ...


@overload
def set_default_formatter(formatter: logging.Formatter, /) -> None: ...


@overload
def set_default_formatter(_arg: Literal[None] = None, /) -> None: ...


def set_default_formatter(
    _arg: Optional[
        Union[logging.Formatter, Literal["json", "console", "no_color_console", "custom", "python", "disabled"]]
    ] = None,
    /,
    *,
    logger_type: Optional[Literal["json", "console", "no_color_console", "custom", "python", "disabled"]] = None,
    formatter: Optional[logging.Formatter] = None,
) -> None:
    if _arg is not None and (logger_type is not None or formatter is not None):
        raise TypeError("Invalid combination of arguments given to set_default_formatter()")
    if logger_type is not None and formatter is not None:
        raise TypeError("Invalid combination of arguments given to set_default_formatter()")

    global TOMODACHI_LOGGER_TYPE

    if _arg is None and logger_type is None and formatter is None:
        logger_type = TOMODACHI_LOGGER_TYPE

    if _arg is not None:
        if isinstance(_arg, logging.Formatter):
            formatter = _arg
        elif isinstance(_arg, str):
            logger_type = _arg
        else:
            raise TypeError("Invalid logger type or formatter given")

    if logger_type is not None:
        formatter = (
            JSONFormatter
            if logger_type == "json"
            else (
                ConsoleFormatter
                if logger_type == "console"
                else (
                    NoColorConsoleFormatter
                    if logger_type == "no_color_console"
                    else (
                        CustomLoggerFormatter
                        if logger_type == "custom"
                        else (
                            DisabledFormatter
                            if logger_type == "disabled"
                            else PythonLoggingFormatter if logger_type == "python" else None
                        )
                    )
                )
            )
        )

        if not formatter:
            raise Exception(
                "Invalid logger type: '{}' (exected 'console', 'json', 'custom', 'python' or 'disabled')".format(
                    logger_type
                )
            )

    if not formatter:
        raise Exception("Argument formatter missing (expected instance of logging.Formatter)')")

    if isinstance(formatter, _StdLoggingFormatter):
        TOMODACHI_LOGGER_TYPE = formatter._logger_type
    else:
        TOMODACHI_LOGGER_TYPE = "python"

    DefaultHandler.setFormatter(formatter)


set_default_formatter()


def _patch_structlog_callsite_parameter_adder_processor() -> None:
    # patch structlog to ignore tomodachi.logger when adding callsite information
    cls_init = structlog.processors.CallsiteParameterAdder.__init__

    if getattr(cls_init, "__wrapped__", None):
        return

    @wraps(cls_init)
    def __init__(self: structlog.processors.CallsiteParameterAdder, *a: Any, **kw: Any) -> None:
        cls_init(self, *a, **kw)
        if "tomodachi.logging" not in self._additional_ignores:
            self._additional_ignores.append("tomodachi.logging")

    setattr(structlog.processors.CallsiteParameterAdder, "__init__", __init__)


_patch_structlog_callsite_parameter_adder_processor()


def set_custom_logger_factory(
    logger_factory: Optional[Union[str, ModuleType, type, object]] = TOMODACHI_CUSTOM_LOGGER,
) -> None:
    if logger_factory is not None and logger_factory:
        logger_factory_ = _CustomLogger.get_logger_factory(logger_factory)
        if logger_factory_ is sys.modules[__name__]:
            # cannot set custom logger factory to tomodachi.logger itself
            logger_factory = None
            set_default_formatter("console")
        else:
            # patch structlog logger to ignore tomodachi.logger when adding callsite information
            for processor in structlog.get_config().get("processors", []):
                if isinstance(processor, structlog.processors.CallsiteParameterAdder):
                    if "tomodachi.logging" not in processor._additional_ignores:
                        processor._additional_ignores.append("tomodachi.logging")

    global TOMODACHI_CUSTOM_LOGGER
    TOMODACHI_CUSTOM_LOGGER = logger_factory


set_custom_logger_factory()


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


class _CustomLogger:
    _logger_factory_cache: Dict[str, Any] = {}

    @classmethod
    def get_logger_factory(cls, custom_logger_factory: Optional[Union[str, ModuleType, type, object]]) -> Any:
        if not custom_logger_factory:
            raise Exception("Custom logger not set")

        logger_factory: Any

        if isinstance(custom_logger_factory, str):
            if custom_logger_factory in cls._logger_factory_cache:
                return cls._logger_factory_cache[custom_logger_factory]

            if custom_logger_factory in sys.modules:
                module_name = custom_logger_factory
                logger_factory = sys.modules[module_name]
            elif "." in custom_logger_factory:
                module_name, module_attr = custom_logger_factory.rsplit(".", 1)
                if module_name in sys.modules:
                    logger_factory = sys.modules[module_name].__dict__.get(module_attr)
                else:
                    logger_factory = __import__(
                        module_name, globals=None, locals=None, fromlist=(module_attr), level=0
                    ).__dict__.get(module_attr)
            else:
                module_name = custom_logger_factory
                if module_name in sys.modules:
                    logger_factory = sys.modules[module_name]
                else:
                    logger_factory = __import__(module_name, globals=None, locals=None, fromlist=(), level=0)

            if not logger_factory:
                raise Exception("Invalid path to custom logger")
        else:
            logger_factory = custom_logger_factory

        if not any(
            [
                (isinstance(logger_factory, ModuleType) and logger_factory.__name__ == "logging"),
                isinstance(logger_factory, type),
                hasattr(logger_factory, "new"),
                hasattr(logger_factory, "bind"),
                hasattr(logger_factory, "get_logger"),
            ]
        ):
            raise Exception("Invalid custom logger factory")

        if isinstance(custom_logger_factory, str):
            cls._logger_factory_cache[custom_logger_factory] = logger_factory

        return logger_factory

    @classmethod
    def get_logger(cls, context: Union[LoggerContext, Context]) -> Any:
        if not TOMODACHI_CUSTOM_LOGGER:
            raise Exception("Custom logger not set")

        logger_factory: Any

        if isinstance(TOMODACHI_CUSTOM_LOGGER, str):
            logger_factory = cls.get_logger_factory(TOMODACHI_CUSTOM_LOGGER or "")
        else:
            logger_factory = TOMODACHI_CUSTOM_LOGGER

        if isinstance(logger_factory, ModuleType) and logger_factory.__name__ == "logging":
            return logger_factory.getLogger(context.get("logger", "default"))
        elif isinstance(logger_factory, type):
            return logger_factory(context)
        elif hasattr(logger_factory, "new"):
            return logger_factory.new(**context)
        elif hasattr(logger_factory, "bind"):
            return logger_factory.bind(**context)
        elif hasattr(logger_factory, "get_logger"):
            logger_cls = logger_factory.get_logger()
            if hasattr(logger_cls, "new"):
                return logger_cls.new(**context)

        raise Exception("Invalid custom logger factory")


class Logger(structlog.stdlib.BoundLogger):
    def __init__(
        self,
        logger: WrappedLogger,
        processors: Iterable[Processor],
        context: Union[LoggerContext, Context],
    ):
        if (
            logger
            and isinstance(logger, logging.Logger)
            and logger.name == "default"
            and context.get("logger", "default") != "default"
        ):
            logger = logging.getLogger(context.get("logger"))

        if logger is _CustomLogger:
            logger = _CustomLogger.get_logger(context)

        super().__init__(logger, processors, context)

    def _proxy_to_logger(self, method_name: str, event: Optional[str] = None, *event_args: Any, **event_kw: Any) -> Any:
        if method_name == "error" and event_kw and event_kw.get("exc_info") is True:
            method_name = "exception"

        try:
            if not self.isEnabledFor(_NAME_TO_LEVEL[method_name]):
                return None
        except Exception:
            try:
                level = self.level
            except Exception:
                try:
                    level = logging.root.level
                except Exception:
                    level = NOTSET

            try:
                if level > _NAME_TO_LEVEL[method_name]:
                    return None
            except Exception:
                pass

        return super()._proxy_to_logger(method_name, event, *event_args, **event_kw)

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
            return logging.getLogger(name).level or logging.root.level

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
        exc_info: ExcInfo,
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
    def info(self, *args: Any, **kwargs: Any) -> None: ...

    def debug(self, *args: Any, **kwargs: Any) -> None: ...

    def warning(self, *args: Any, **kwargs: Any) -> None: ...

    def error(self, *args: Any, **kwargs: Any) -> None: ...

    def critical(self, *args: Any, **kwargs: Any) -> None: ...

    def exception(self, *args: Any, **kwargs: Any) -> None: ...


ConsoleRenderer: type[structlog.dev.ConsoleRenderer]
try:
    _structlog_version = tuple(
        map(lambda v: int(v) if v.isdigit() else v, importlib.metadata.version("structlog").split("."))
    )
except Exception:  # pragma: no cover
    _structlog_version = tuple(map(lambda v: int(v) if v.isdigit() else v, structlog.__version__.split(".")))

if _structlog_version < (23, 3, 0):  # pragma: no cover
    # backport of structlog 23.x ConsoleRenderer to be usable with structlog 21.x+.

    class ConsoleRenderer_(structlog.dev.ConsoleRenderer):
        _colors: bool
        _level_to_color: Dict[str, str]
        _pad_event: int
        _event_key: str

        def __init__(
            self,
            **kw: Any,
        ):
            try:
                super().__init__(**kw)
                self._event_key = kw.get("event_key") or "event"
            except Exception:
                self._event_key = kw.pop("event_key", "event")
                super().__init__(**kw)

            self._colors = kw.get("colors", not NO_COLOR) and not NO_COLOR
            self._pad_event = kw.get("pad_event") or structlog.dev._EVENT_WIDTH

            level_styles = kw.get("level_styles")
            level_to_color = self.get_default_level_styles(self._colors) if level_styles is None else level_styles
            for key in level_to_color:
                level_to_color[key] += self._styles.bright
            self._level_to_color = level_to_color

        def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> str:
            sio = StringIO()

            _styles = self._styles
            _level_to_color = self._level_to_color

            ts = event_dict.pop("timestamp", None)
            if ts is not None:
                sio.write(_styles.timestamp + str(ts) + _styles.reset + " ")
            level = event_dict.pop("level", None)
            if level is not None:
                sio.write(
                    "["
                    + _level_to_color.get(level, "")
                    + structlog.dev._pad(level, self._longest_level)
                    + _styles.reset
                    + "] "
                )

            # force event to str for compatibility with standard library
            event = event_dict.pop(self._event_key, None)
            if not isinstance(event, str):
                event = str(event)

            if event_dict:
                event = structlog.dev._pad(event, self._pad_event) + _styles.reset + " "
            else:
                event += _styles.reset
            sio.write(_styles.bright + event)

            logger_name = event_dict.pop("logger", None)
            if logger_name is None:
                logger_name = event_dict.pop("logger_name", None)

            if logger_name is not None:
                sio.write("[" + _styles.logger_name + _styles.bright + logger_name + _styles.reset + "] ")

            stack = event_dict.pop("stack", None)
            exc = event_dict.pop("exception", None)
            exc_info = event_dict.pop("exc_info", None)

            event_dict_keys: Iterable[str] = event_dict.keys()
            if self._sort_keys:
                event_dict_keys = sorted(event_dict_keys)

            sio.write(
                " ".join(
                    _styles.kv_key
                    + key
                    + _styles.reset
                    + "="
                    + _styles.kv_value
                    + self._repr(event_dict[key])
                    + _styles.reset
                    for key in event_dict_keys
                )
            )

            if stack is not None:
                sio.write("\n" + stack)
                if exc_info or exc is not None:
                    sio.write("\n\n" + "=" * 79 + "\n")

            if exc_info:
                exc_info = structlog.processors._figure_out_exc_info(exc_info)

                self._exception_formatter(sio, exc_info)
            elif exc is not None:
                if self._exception_formatter is not structlog.dev.plain_traceback:
                    warnings.warn(
                        "Remove `format_exc_info` from your processor chain " "if you want pretty exceptions.",
                        stacklevel=2,
                    )
                sio.write("\n" + exc)

            return sio.getvalue()

    ConsoleRenderer = ConsoleRenderer_
else:
    ConsoleRenderer = structlog.dev.ConsoleRenderer

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
        LinkQuoteStrings(keys=CONSOLE_QUOTE_KEYS),
        ConsoleRenderer(colors=False if NO_COLOR else True, sort_keys=False, event_key="message"),
    ],
    wrapper_class=Logger,
    context_class=LoggerContext,
    cache_logger_on_first_use=False,
)

no_color_console_logger: Logger = structlog.wrap_logger(
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
        LinkQuoteStrings(keys=CONSOLE_QUOTE_KEYS),
        ConsoleRenderer(colors=False, sort_keys=False, event_key="message"),
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
        add_stacktrace_info,
        RemoveDictKey(key="exc_info"),
        remove_ellipsis_values,
        structlog.processors.JSONRenderer(serializer=serializer_func),
    ],
    wrapper_class=Logger,
    context_class=LoggerContext,
    cache_logger_on_first_use=False,
)

custom_logger: Logger = structlog.wrap_logger(
    _CustomLogger,
    processors=[remove_ellipsis_values, to_custom_logger],
    wrapper_class=Logger,
    context_class=LoggerContext,
    cache_logger_on_first_use=False,
)

forward_logger: Logger = structlog.wrap_logger(
    logging.getLogger("default"),
    processors=[remove_ellipsis_values, to_logger_args_kwargs],
    wrapper_class=Logger,
    context_class=LoggerContext,
    cache_logger_on_first_use=False,
)

python_logger: Logger = structlog.wrap_logger(
    logging.getLogger("default"),
    processors=[remove_ellipsis_values, to_logger_args_kwargs],
    wrapper_class=Logger,
    context_class=LoggerContext,
    cache_logger_on_first_use=False,
)

disabled_logger: Logger = structlog.wrap_logger(
    None,
    processors=[disabled_logger_processor],
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
            ctx = LoggerContext(logger=logger, **{})
        return ctx
    else:
        raise TypeError(f"Unsupported logger type: {type(logger)}")


def bind_logger(logger: Union[LoggerContext, Dict, structlog.BoundLoggerBase, str]) -> None:
    _context.set(get_context(logger))


def _get_logger(
    name: Optional[str] = None,
    *,
    logger_type: Literal["json", "console", "no_color_console", "custom", "forward", "python", "disabled"] = "forward",
) -> Logger:
    if logger_type == "forward" and TOMODACHI_LOGGER_TYPE == "python":
        logger_type = "python"

    logger = (
        json_logger
        if logger_type == "json"
        else (
            console_logger
            if logger_type == "console"
            else (
                no_color_console_logger
                if logger_type == "no_color_console"
                else (
                    custom_logger
                    if logger_type == "custom"
                    else (
                        python_logger
                        if logger_type == "python"
                        else (
                            disabled_logger
                            if logger_type == "disabled"
                            else forward_logger if logger_type == "forward" else None
                        )
                    )
                )
            )
        )
    )
    if not logger:
        raise Exception(
            "Invalid logger type: '{}' (exected 'console', 'json', 'custom', 'forward', 'python' or 'disabled')".format(
                logger_type
            )
        )

    if name:
        ctx = _loggers.get().get(name)
        if ctx:
            return cast(Logger, logger.new(**ctx))

        return cast(Logger, logger.new(**LoggerContext(logger=name, **{})))

    return cast(Logger, logger.new(**_context.get()))


def get_logger(
    name: Optional[str] = None,
) -> Logger:
    return _get_logger(name=name)


# CamelCase alias for `get_logger`.
def getLogger(name: Optional[str] = None) -> Logger:
    return _get_logger(name=name)


def configure(log_level: Union[int, str] = logging.INFO, force: bool = False) -> None:
    log_level_ = log_level
    if isinstance(log_level, str) and not log_level.isdigit():
        log_level_ = getattr(logging, log_level.upper(), None) or logging.NOTSET
    if isinstance(log_level, str) and log_level.isdigit():
        log_level_ = int(log_level)
    if type(log_level_) is not int or log_level_ == logging.NOTSET:
        raise Exception(
            f"Invalid log level: '{log_level}' (expected 'debug', 'info', 'warning', 'error' or 'critical')"
        )
    log_level = log_level_

    logging.addLevelName(logging.NOTSET, "notset")
    logging.addLevelName(logging.DEBUG, "debug")
    logging.addLevelName(logging.INFO, "info")
    logging.addLevelName(logging.WARN, "warn")
    logging.addLevelName(logging.WARNING, "warning")
    logging.addLevelName(logging.ERROR, "error")
    logging.addLevelName(logging.FATAL, "fatal")
    logging.addLevelName(logging.CRITICAL, "critical")

    global _default_fmt
    try:
        if (
            len(logging.root.handlers)
            and logging.root.handlers[0].formatter
            and logging.root.handlers[0].formatter._fmt
        ):
            _default_fmt = logging.root.handlers[0].formatter._fmt
    except AttributeError:
        pass

    if PythonLoggingFormatter._fmt != _default_fmt:
        PythonLoggingFormatter._fmt = _default_fmt

    try:
        logging.basicConfig(
            format=_default_fmt,
            level=log_level,
            handlers=[DefaultRootLoggerHandler],
            force=force,
        )
    except Exception as e:
        logging.getLogger().warning("Unable to set log config: {}".format(str(e)))


def remove_handlers() -> None:
    for name, logger in logging.Logger.manager.loggerDict.items():
        if name not in ("tomodachi",) and not name.startswith("tomodachi."):
            continue

        if isinstance(logger, logging.PlaceHolder):
            continue

        if not getattr(logger, "handlers", None) or not logger.handlers or not isinstance(logger.handlers, list):
            continue

        for handler in logger.handlers:
            logger.removeHandler(handler)
            try:
                handler.acquire()
                handler.flush()
                handler.close()
            except (OSError, ValueError):
                pass
            finally:
                handler.release()

    for handler in logging.root.handlers:
        if handler is not DefaultRootLoggerHandler:
            continue
        logging.root.removeHandler(handler)
        try:
            handler.acquire()
            handler.flush()
            handler.close()
        except (OSError, ValueError):
            pass
        finally:
            handler.release()


# Set default logger context
_context.set(LoggerContext(logger="default", **{}))


def reset_context() -> None:
    _loggers.set({})
    _context.set(LoggerContext(logger="default", **{}))


__all__ = [
    "get_logger",
    "_get_logger",
    "getLogger",
    "bind_logger",
    "reset_context",
    "Logger",
    "PythonLoggingFormatter",
    "ConsoleFormatter",
    "NoColorConsoleFormatter",
    "JSONFormatter",
    "DisabledFormatter",
    "CustomLoggerFormatter",
    "DefaultHandler",
    "DefaultRootLoggerHandler",
    "_defaultHandler",
    "StderrHandler",
    "configure",
    "set_default_formatter",
    "remove_handlers",
    "add_exception_info",
    "add_stacktrace_info",
    "DEFAULT_FORMAT",
    "CRITICAL",
    "DEBUG",
    "ERROR",
    "FATAL",
    "INFO",
    "NOTSET",
    "WARN",
    "WARNING",
]
