import asyncio
import json
from typing import Any

import tomodachi


class TestException(Exception):
    __test__ = False


def exception_func() -> None:
    raise TestException("test exception")


def test_internal_default_logger(capsys: Any) -> None:
    logger = tomodachi.logging.get_logger(logger_type="json")
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

    assert json.loads(out) == {
        "level": "exception",
        "logger": "default",
        "message": "this is the message",
        "exception": "TestException('test exception')",
        "exc_type": "TestException",
        "exc_message": "test exception",
        "tb_module_name": "test_logging_internals",
        "tb_function_name": "exception_func",
        "tb_location": "./tests/test_logging_internals.py:13",
        "stacktrace": [
            {
                "module_name": "test_logging_internals",
                "function_name": "test_internal_default_logger",
                "location": "./tests/test_logging_internals.py:51",
            },
            {
                "module_name": "test_logging_internals",
                "function_name": "exception_func",
                "location": "./tests/test_logging_internals.py:13",
            },
        ],
        "timestamp": json.loads(out).get("timestamp"),
    }


def test_internal_logger_name(capsys: Any) -> None:
    logger = tomodachi.logging.get_logger(logger_type="json")
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
        tomodachi.logging.get_logger("tomodachi.test.logger", logger_type="json").info("beginning of _async_b")
        out, err = capsys.readouterr()

        await asyncio.sleep(1.0)

        tomodachi.logging.get_logger("tomodachi.test.logger", logger_type="json").bind(value="def")

        await asyncio.sleep(0.5)

        tomodachi.logging.get_logger("tomodachi.test.logger", logger_type="json").info("end of _async_b")
        out, err = capsys.readouterr()

    async def _async_a() -> None:
        logger = tomodachi.logging.get_logger("tomodachi.test.logger", logger_type="json").bind(value="abc")
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

        tomodachi.logging.get_logger("tomodachi.test.logger", logger_type="json").bind(
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
        tomodachi.logging.get_logger("tomodachi.test.logger", logger_type="json").bind(tasks_started=2)
        await asyncio.sleep(0.6)

        tomodachi.logging.get_logger("tomodachi.test.logger", logger_type="json").info("during task2")
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

        tomodachi.logging.get_logger("tomodachi.test.logger", logger_type="json").info("after tasks")
        out, err = capsys.readouterr()

        assert json.loads(out) == {
            "level": "info",
            "message": "after tasks",
            "logger": "tomodachi.test.logger",
            "value": "xyz",
            "tasks_started": 2,
            "timestamp": json.loads(out).get("timestamp"),
        }

    tomodachi.logging.get_logger("tomodachi.test.logger", logger_type="json").info("before coro")
    out, err = capsys.readouterr()

    assert json.loads(out) == {
        "level": "info",
        "message": "before coro",
        "logger": "tomodachi.test.logger",
        "timestamp": json.loads(out).get("timestamp"),
    }

    loop.run_until_complete(_async_a())

    tomodachi.logging.get_logger("tomodachi.test.logger", logger_type="json").info("after coro")
    out, err = capsys.readouterr()

    assert json.loads(out) == {
        "level": "info",
        "message": "after coro",
        "logger": "tomodachi.test.logger",
        "timestamp": json.loads(out).get("timestamp"),
    }
