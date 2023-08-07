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
        "tb_location": "./tests/test_logging_internals.py:12",
        "stacktrace": [
            {
                "module_name": "test_logging_internals",
                "function_name": "test_internal_default_logger",
                "location": "./tests/test_logging_internals.py:50",
            },
            {
                "module_name": "test_logging_internals",
                "function_name": "exception_func",
                "location": "./tests/test_logging_internals.py:12",
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
