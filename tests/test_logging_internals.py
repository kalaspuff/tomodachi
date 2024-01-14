import asyncio
import json
import sys
from typing import Any, Dict

import pytest
import structlog

import tomodachi


class TestException(Exception):
    __test__ = False


def exception_func() -> None:
    raise TestException("test exception")


def test_internal_default_logger(capsys: Any) -> None:
    logger = tomodachi.logging._get_logger(logger_type="json")
    assert logger is not None

    logger.info("info message")
    out, err = capsys.readouterr()

    assert json.loads(out) == {
        "level": "info",
        "logger": "default",
        "message": "info message",
        "timestamp": json.loads(out).get("timestamp"),
    }

    logger.warning("this is a warning")
    out, err = capsys.readouterr()

    assert json.loads(out) == {
        "level": "warning",
        "logger": "default",
        "message": "this is a warning",
        "timestamp": json.loads(out).get("timestamp"),
    }

    logger.error("error log")
    out, err = capsys.readouterr()

    assert json.loads(out) == {
        "level": "error",
        "logger": "default",
        "message": "error log",
        "timestamp": json.loads(out).get("timestamp"),
    }

    try:
        exception_func()
    except TestException:
        logger.exception("this is the message")

    out, err = capsys.readouterr()

    structlog_version = tuple(map(lambda v: int(v) if v.isdigit() else v, structlog.__version__.split(".")))
    exception_level = "error" if structlog_version >= (24, 0, 0) else "exception"

    assert json.loads(out) == {
        "level": exception_level,
        "logger": "default",
        "message": "this is the message",
        "exception": "TestException('test exception')",
        "exc_type": "TestException",
        "exc_message": "test exception",
        "tb_module_name": "test_logging_internals",
        "tb_function_name": "exception_func",
        "tb_location": "./tests/test_logging_internals.py:17",
        "stacktrace": [
            {
                "module_name": "test_logging_internals",
                "function_name": "test_internal_default_logger",
                "location": "./tests/test_logging_internals.py:55",
            },
            {
                "module_name": "test_logging_internals",
                "function_name": "exception_func",
                "location": "./tests/test_logging_internals.py:17",
            },
        ],
        "timestamp": json.loads(out).get("timestamp"),
    }


def test_internal_logger_name(capsys: Any) -> None:
    logger = tomodachi.logging._get_logger(logger_type="json")
    assert logger.name == "default"

    logger2 = logger.bind(logger="tomodachi.test.logger")
    assert logger2.name == "tomodachi.test.logger"
    assert logger.name == "default"

    logger3 = logger2.bind(x=4711, y=1338)

    logger2.info(z=0)
    out, err = capsys.readouterr()

    assert json.loads(out) == {
        "level": "info",
        "logger": "tomodachi.test.logger",
        "z": 0,
        "timestamp": json.loads(out).get("timestamp"),
    }

    logger3.info(a=9001)
    out, err = capsys.readouterr()

    assert json.loads(out) == {
        "level": "info",
        "logger": "tomodachi.test.logger",
        "x": 4711,
        "y": 1338,
        "a": 9001,
        "timestamp": json.loads(out).get("timestamp"),
    }

    logger3.bind(z=3.14).info(a=9002, x=Ellipsis)
    out, err = capsys.readouterr()

    assert json.loads(out) == {
        "level": "info",
        "logger": "tomodachi.test.logger",
        "y": 1338,
        "z": 3.14,
        "a": 9002,
        "timestamp": json.loads(out).get("timestamp"),
    }


def test_internal_logger_context(capsys: Any, loop: Any) -> None:
    async def _async_b() -> None:
        tomodachi.logging._get_logger("tomodachi.test.logger", logger_type="json").info("beginning of _async_b")
        out, err = capsys.readouterr()

        await asyncio.sleep(1.0)

        tomodachi.logging._get_logger("tomodachi.test.logger", logger_type="json").bind(value="def")

        await asyncio.sleep(0.5)

        tomodachi.logging._get_logger("tomodachi.test.logger", logger_type="json").info("end of _async_b")
        out, err = capsys.readouterr()

    async def _async_a() -> None:
        logger = tomodachi.logging._get_logger("tomodachi.test.logger", logger_type="json").bind(value="abc")
        logger.info("in _async_a")
        out, err = capsys.readouterr()

        assert json.loads(out) == {
            "level": "info",
            "message": "in _async_a",
            "logger": "tomodachi.test.logger",
            "value": "abc",
            "timestamp": json.loads(out).get("timestamp"),
        }

        task1 = asyncio.create_task(_async_b())
        await asyncio.sleep(0.6)

        tomodachi.logging._get_logger("tomodachi.test.logger", logger_type="json").bind(
            value="xyz", tasks_started=1
        ).info("during task1")
        out, err = capsys.readouterr()

        assert json.loads(out) == {
            "level": "info",
            "message": "during task1",
            "logger": "tomodachi.test.logger",
            "value": "xyz",
            "tasks_started": 1,
            "timestamp": json.loads(out).get("timestamp"),
        }

        task2 = asyncio.create_task(_async_b())
        tomodachi.logging._get_logger("tomodachi.test.logger", logger_type="json").bind(tasks_started=2)
        await asyncio.sleep(0.6)

        tomodachi.logging._get_logger("tomodachi.test.logger", logger_type="json").info("during task2")
        out, err = capsys.readouterr()

        assert json.loads(out) == {
            "level": "info",
            "message": "during task2",
            "logger": "tomodachi.test.logger",
            "value": "xyz",
            "tasks_started": 2,
            "timestamp": json.loads(out).get("timestamp"),
        }

        await task1
        await task2

        tomodachi.logging._get_logger("tomodachi.test.logger", logger_type="json").info("after tasks")
        out, err = capsys.readouterr()

        assert json.loads(out) == {
            "level": "info",
            "message": "after tasks",
            "logger": "tomodachi.test.logger",
            "value": "xyz",
            "tasks_started": 2,
            "timestamp": json.loads(out).get("timestamp"),
        }

    tomodachi.logging._get_logger("tomodachi.test.logger", logger_type="json").info("before coro")
    out, err = capsys.readouterr()

    assert json.loads(out) == {
        "level": "info",
        "message": "before coro",
        "logger": "tomodachi.test.logger",
        "timestamp": json.loads(out).get("timestamp"),
    }

    loop.run_until_complete(_async_a())

    tomodachi.logging._get_logger("tomodachi.test.logger", logger_type="json").info("after coro")
    out, err = capsys.readouterr()

    assert json.loads(out) == {
        "level": "info",
        "message": "after coro",
        "logger": "tomodachi.test.logger",
        "timestamp": json.loads(out).get("timestamp"),
    }


def test_default_formatter_settings(capsys: Any) -> None:
    default_value = tomodachi.logging.TOMODACHI_LOGGER_TYPE

    try:
        tomodachi.logging.set_default_formatter(logger_type="console")

        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == "console"
        assert getattr(tomodachi.logging.DefaultHandler.formatter, "_logger_type", None) == "console"
        assert tomodachi.logging.DefaultHandler.formatter == tomodachi.logging.ConsoleFormatter
        assert repr(tomodachi.logging.DefaultHandler.formatter) == "ConsoleFormatter"

        tomodachi.logging.set_default_formatter(logger_type="json")

        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == "json"
        assert getattr(tomodachi.logging.DefaultHandler.formatter, "_logger_type", None) == "json"
        assert tomodachi.logging.DefaultHandler.formatter == tomodachi.logging.JSONFormatter
        assert repr(tomodachi.logging.DefaultHandler.formatter) == "JSONFormatter"

        tomodachi.logging.set_default_formatter(logger_type="python")

        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == "python"
        assert tomodachi.logging.DefaultHandler.formatter == tomodachi.logging.PythonLoggingFormatter
        assert repr(tomodachi.logging.DefaultHandler.formatter) == "PythonLoggingFormatter"
    finally:
        tomodachi.logging.set_default_formatter(logger_type=default_value)
        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == default_value


def test_python_logging_hook(capsys: Any) -> None:
    import logging as logging_

    default_value = tomodachi.logging.TOMODACHI_LOGGER_TYPE

    try:
        logger = tomodachi.logging.get_logger("tomodachi.test.json_logger")
        for hdlr in logger.handlers:
            logger.handlers.remove(hdlr)
        logger._logger.propagate = False
        assert logger.propagate is False
        logger.addHandler(tomodachi.logging.DefaultRootLoggerHandler)
        tomodachi.logging.set_default_formatter(logger_type="json")
        assert tomodachi.logging.DefaultRootLoggerHandler.formatter == tomodachi.logging.JSONFormatter

        logger.info("log msg from tomodachi.logging module")

        out, err = capsys.readouterr()

        assert json.loads(err) == {
            "level": "info",
            "message": "log msg from tomodachi.logging module",
            "logger": "tomodachi.test.json_logger",
            "timestamp": json.loads(err).get("timestamp"),
        }

        logging_.getLogger("tomodachi.test.json_logger").info("log msg from python logging module")

        out, err = capsys.readouterr()

        assert json.loads(err) == {
            "level": "info",
            "message": "log msg from python logging module",
            "logger": "tomodachi.test.json_logger",
            "timestamp": json.loads(err).get("timestamp"),
        }

        logging_.getLogger("tomodachi.test.json_logger_").info("log msg from python logging module")

        out, err = capsys.readouterr()

        assert "[info     ] log msg from python logging module [tomodachi.test.json_logger_]" in err
    finally:
        tomodachi.logging.set_default_formatter(logger_type=default_value)
        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == default_value


def test_console_formatter(capsys: Any) -> None:
    import logging as logging_

    default_value = tomodachi.logging.TOMODACHI_LOGGER_TYPE

    try:
        logger = tomodachi.logging.get_logger("tomodachi.test.console_logger")
        for hdlr in logger.handlers:
            logger.handlers.remove(hdlr)
        logger._logger.propagate = False
        assert logger.propagate is False
        logger.addHandler(tomodachi.logging.DefaultRootLoggerHandler)
        tomodachi.logging.set_default_formatter(logger_type="no_color_console")
        assert tomodachi.logging.DefaultRootLoggerHandler.formatter == tomodachi.logging.NoColorConsoleFormatter

        logger.info("log msg from tomodachi.logging module", value="test")

        out, err = capsys.readouterr()

        assert "[info     ] log msg from tomodachi.logging module [tomodachi.test.console_logger] value=test" in err

        logging_.getLogger("tomodachi.test.console_logger").info(
            "log msg from python logging module", extra={"value": "test"}
        )

        out, err = capsys.readouterr()

        assert (
            "[info     ] log msg from python logging module [tomodachi.test.console_logger] extra={'value': 'test'}"
            in err
        )
    finally:
        tomodachi.logging.set_default_formatter(logger_type=default_value)
        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == default_value


def test_python_logging_formatter(capsys: Any) -> None:
    import logging as logging_

    default_value = tomodachi.logging.TOMODACHI_LOGGER_TYPE

    try:
        logger = tomodachi.logging.get_logger("tomodachi.test.python_logger")
        for hdlr in logger.handlers:
            logger.handlers.remove(hdlr)
        logger._logger.propagate = False
        assert logger.propagate is False
        logger.addHandler(tomodachi.logging.DefaultRootLoggerHandler)
        tomodachi.logging.set_default_formatter(logger_type="python")
        assert tomodachi.logging.DefaultRootLoggerHandler.formatter == tomodachi.logging.PythonLoggingFormatter

        logger.info("log msg from tomodachi.logging module", value="test")

        out, err = capsys.readouterr()

        assert "tomodachi.test.python_logger" in err
        assert "log msg from tomodachi.logging module" in err
        assert "value=test" not in err
        assert "{'value': 'test'}" not in err

        logging_.getLogger("tomodachi.test.python_logger").info(
            "log msg from python logging module", extra={"value": "test"}
        )

        out, err = capsys.readouterr()

        assert "tomodachi.test.python_logger" in err
        assert "log msg from python logging module" in err
        assert "value=test" not in err
        assert "{'value': 'test'}" not in err

        tomodachi.logging.set_default_formatter(formatter=logging_.Formatter(fmt=tomodachi.logging.DEFAULT_FORMAT))

        logger.info("log msg from tomodachi.logging with logging.Formatter DEFAULT_FORMAT", value="test")

        out, err = capsys.readouterr()

        assert (
            "[info     ] log msg from tomodachi.logging with logging.Formatter DEFAULT_FORMAT [tomodachi.test.python_logger]"
            in err
        )
        assert "value=test" not in err
        assert "{'value': 'test'}" not in err

        logging_.getLogger("tomodachi.test.python_logger").info(
            "log msg with logging.Formatter DEFAULT_FORMAT", extra={"value": "test"}
        )

        out, err = capsys.readouterr()

        assert "[info     ] log msg with logging.Formatter DEFAULT_FORMAT [tomodachi.test.python_logger]" in err
        assert "value=test" not in err
        assert "{'value': 'test'}" not in err

        tomodachi.logging.set_default_formatter(formatter=logging_.Formatter(fmt=logging_.BASIC_FORMAT))

        logger.info("log msg from tomodachi.logging with logging.Formatter BASIC_FORMAT", value="test")

        out, err = capsys.readouterr()

        assert (
            "info:tomodachi.test.python_logger:log msg from tomodachi.logging with logging.Formatter BASIC_FORMAT"
            == err.strip()
        )

        logging_.getLogger("tomodachi.test.python_logger").info(
            "log msg with logging.Formatter BASIC_FORMAT", extra={"value": "test"}
        )

        out, err = capsys.readouterr()

        assert "info:tomodachi.test.python_logger:log msg with logging.Formatter BASIC_FORMAT" == err.strip()
    finally:
        tomodachi.logging.set_default_formatter(logger_type=default_value)
        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == default_value


def test_custom_logger(capsys: Any) -> None:
    import logging as logging_

    default_value = tomodachi.logging.TOMODACHI_LOGGER_TYPE
    default_custom_logger = tomodachi.logging.TOMODACHI_CUSTOM_LOGGER

    try:

        class CustomLogger:
            def __init__(self, ctx: Dict[str, Any]) -> None:
                pass

            def info(self, msg: str, **kwargs: Any) -> None:
                print("custom-logger", "info", msg, kwargs, file=sys.stderr)

        tomodachi.logging.set_custom_logger_factory(CustomLogger)

        logger = tomodachi.logging.get_logger("tomodachi.test.custom_logger")
        for hdlr in logger.handlers:
            logger.handlers.remove(hdlr)
        logger._logger.propagate = False
        assert logger.propagate is False
        logger.addHandler(tomodachi.logging.DefaultRootLoggerHandler)
        tomodachi.logging.set_default_formatter(logger_type="custom")
        assert tomodachi.logging.DefaultRootLoggerHandler.formatter == tomodachi.logging.CustomLoggerFormatter

        logger.info("log msg from tomodachi.logging module", value="test")

        out, err = capsys.readouterr()

        assert err.startswith(
            "custom-logger info log msg from tomodachi.logging module {'logger': 'tomodachi.test.custom_logger', 'value': 'test', 'timestamp': '"
        )

        logging_.getLogger("tomodachi.test.custom_logger").info(
            "log msg from python logging module", extra={"value": "test"}
        )

        out, err = capsys.readouterr()

        assert err.startswith(
            "custom-logger info log msg from python logging module {'logger': 'tomodachi.test.custom_logger', 'extra': {'value': 'test'}, 'timestamp': '"
        )

        logging_.getLogger("tomodachi.test.custom_logger").info("log msg from python logging module without extra")

        out, err = capsys.readouterr()

        assert err.startswith(
            "custom-logger info log msg from python logging module without extra {'logger': 'tomodachi.test.custom_logger', 'timestamp': '"
        )
    finally:
        tomodachi.logging.set_default_formatter(logger_type=default_value)
        tomodachi.logging.set_custom_logger_factory(default_custom_logger)
        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == default_value


def test_invalid_formatter_values() -> None:
    with pytest.raises(Exception):
        tomodachi.logging.set_default_formatter(logger_type="invalid")  # type: ignore

    with pytest.raises(Exception):
        tomodachi.logging.set_default_formatter(logger_type="console", formatter=tomodachi.logging.ConsoleFormatter)  # type: ignore

    with pytest.raises(TypeError):
        tomodachi.logging.set_default_formatter("console", formatter=tomodachi.logging.ConsoleFormatter)  # type: ignore

    with pytest.raises(TypeError):
        tomodachi.logging.set_default_formatter(tomodachi.logging.ConsoleFormatter, logger_type="console")  # type: ignore


def test_valid_formatter_values() -> None:
    default_value = tomodachi.logging.TOMODACHI_LOGGER_TYPE

    try:
        tomodachi.logging.set_default_formatter("json")

        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == "json"
        assert getattr(tomodachi.logging.DefaultHandler.formatter, "_logger_type", None) == "json"
        assert tomodachi.logging.DefaultHandler.formatter == tomodachi.logging.JSONFormatter
        assert repr(tomodachi.logging.DefaultHandler.formatter) == "JSONFormatter"

        tomodachi.logging.set_default_formatter(tomodachi.logging.ConsoleFormatter)

        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == "console"
        assert getattr(tomodachi.logging.DefaultHandler.formatter, "_logger_type", None) == "console"
        assert tomodachi.logging.DefaultHandler.formatter == tomodachi.logging.ConsoleFormatter
        assert repr(tomodachi.logging.DefaultHandler.formatter) == "ConsoleFormatter"

        tomodachi.logging.set_default_formatter(formatter=tomodachi.logging.JSONFormatter)

        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == "json"
        assert getattr(tomodachi.logging.DefaultHandler.formatter, "_logger_type", None) == "json"
        assert tomodachi.logging.DefaultHandler.formatter == tomodachi.logging.JSONFormatter
        assert repr(tomodachi.logging.DefaultHandler.formatter) == "JSONFormatter"

    finally:
        tomodachi.logging.set_default_formatter(logger_type=default_value)
        logger_type = tomodachi.logging.TOMODACHI_LOGGER_TYPE
        assert logger_type == default_value
