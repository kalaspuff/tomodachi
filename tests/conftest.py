import asyncio
import os
import sys
from typing import Generator

import pytest

os.environ["TOMODACHI_NO_COLOR"] = "1"


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    try:
        from tomodachi.logging import ConsoleFormatter

        plugin = config.pluginmanager.get_plugin("logging-plugin")
        if plugin:
            plugin.caplog_handler.setFormatter(ConsoleFormatter)
            plugin.report_handler.setFormatter(ConsoleFormatter)
    except Exception as exc:
        import logging

        logging.warning("Unable to import tomodachi.logging.DefaultHandler: {}".format(str(exc)))


@pytest.fixture(scope="session", autouse=True)
def setup_logger() -> None:
    import logging

    logging.addLevelName(logging.NOTSET, "notset")
    logging.addLevelName(logging.DEBUG, "debug")
    logging.addLevelName(logging.INFO, "info")
    logging.addLevelName(logging.WARN, "warn")
    logging.addLevelName(logging.WARNING, "warning")
    logging.addLevelName(logging.ERROR, "error")
    logging.addLevelName(logging.FATAL, "fatal")
    logging.addLevelName(logging.CRITICAL, "critical")

    try:
        from tomodachi.logging import NoColorConsoleFormatter, StderrHandler

        hdlr = StderrHandler()
        hdlr.setFormatter(NoColorConsoleFormatter)
        logging.root.setLevel(logging.INFO)
        logging.root.addHandler(hdlr)  # captures stderr
    except Exception as exc:
        logging.warning("Unable to import tomodachi.logging.DefaultHandler: {}".format(str(exc)))


@pytest.fixture(scope="module")
def loop() -> Generator:
    loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    yield loop

    try:
        if loop and not loop.is_closed():
            loop.close()
        if sys.version_info.major == 3 and sys.version_info.minor < 10:
            loop = asyncio.get_event_loop()
        else:
            loop = asyncio.get_running_loop()
            asyncio.set_event_loop(loop)
        if loop and not loop.is_closed():
            loop.close()
    except RuntimeWarning:
        pass
    except RuntimeError:
        pass


@pytest.fixture(scope="function", autouse=True)
def reset_logger_context() -> None:
    import tomodachi.logging

    tomodachi.logging.reset_context()
