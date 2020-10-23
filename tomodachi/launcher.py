import asyncio
import datetime
import importlib
import logging
import os
import platform
import signal
import sys
import time
from typing import Any, Dict, List, Optional, Union, cast

import multidict  # noqa
import pytz
import tzlocal
import yarl  # noqa

import tomodachi.__version__
import tomodachi.container
import tomodachi.importer
import tomodachi.invoker
import tomodachi.watcher
from tomodachi.container import ServiceContainer
from tomodachi.helpers.execution_context import clear_execution_context, clear_services, set_execution_context
from tomodachi.importer import ServiceImporter

try:
    CancelledError = asyncio.exceptions.CancelledError  # type: ignore
except Exception:

    class CancelledError(Exception):  # type: ignore
        pass


class ServiceLauncher(object):
    _close_waiter = None  # type: Union[None, asyncio.Future]
    _stopped_waiter = None  # type: Union[None, asyncio.Future]
    restart_services = False
    services = set()  # type: set

    @classmethod
    def run_until_complete(
        cls,
        service_files: Union[List, set],
        configuration: Optional[Dict] = None,
        watcher: Optional[tomodachi.watcher.Watcher] = None,
    ) -> None:
        def stop_services() -> None:
            asyncio.ensure_future(_stop_services())

        async def _stop_services() -> None:
            if cls._close_waiter and not cls._close_waiter.done():
                cls._close_waiter.set_result(None)
                for service in cls.services:
                    try:
                        service.stop_service()
                    except Exception:
                        pass
                if cls._stopped_waiter:
                    cls._stopped_waiter.set_result(None)
            if cls._stopped_waiter:
                await cls._stopped_waiter

        def sigintHandler(*args: Any) -> None:
            sys.stdout.write("\b\b\r")
            sys.stdout.flush()
            logging.getLogger("system").warning("Received <ctrl+c> interrupt [SIGINT]")
            cls.restart_services = False

        def sigtermHandler(*args: Any) -> None:
            logging.getLogger("system").warning("Received termination signal [SIGTERM]")
            cls.restart_services = False

        logging.basicConfig(level=logging.DEBUG)

        loop = asyncio.get_event_loop()
        if loop and loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for signame in ("SIGINT", "SIGTERM"):
            loop.add_signal_handler(getattr(signal, signame), stop_services)

        signal.siginterrupt(signal.SIGTERM, False)
        signal.siginterrupt(signal.SIGUSR1, False)
        signal.signal(signal.SIGINT, sigintHandler)
        signal.signal(signal.SIGTERM, sigtermHandler)

        if watcher:

            async def _watcher_restart(updated_files: Union[List, set]) -> None:
                cls.restart_services = True

                for file in service_files:
                    try:
                        ServiceImporter.import_service_file(file)
                    except (SyntaxError, IndentationError) as e:
                        logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                        logging.getLogger("watcher.restart").warning("Service cannot restart due to errors")
                        cls.restart_services = False
                        return

                pre_import_current_modules = [m for m in sys.modules.keys()]
                cwd = os.getcwd()
                for file in updated_files:
                    if file.lower().endswith(".py"):
                        module_name = file[:-3].replace("/", ".")
                        module_name_full_path = "{}/{}".format(os.path.realpath(cwd), file)[:-3].replace("/", ".")
                        try:
                            for m in pre_import_current_modules:
                                if m == module_name or (len(m) > len(file) and module_name_full_path.endswith(m)):
                                    ServiceImporter.import_module(file)
                        except (SyntaxError, IndentationError) as e:
                            logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                            logging.getLogger("watcher.restart").warning("Service cannot restart due to errors")
                            cls.restart_services = False
                            return

                logging.getLogger("watcher.restart").warning("Restarting services")
                stop_services()

            watcher_future = loop.run_until_complete(watcher.watch(loop=loop, callback_func=_watcher_restart))

        cls.restart_services = True
        init_modules = [m for m in sys.modules.keys()]
        safe_modules = [
            "typing",
            "importlib.util",
            "time",
            "logging",
            "re",
            "traceback",
            "types",
            "inspect",
            "functools",
        ]

        restarting = False
        while cls.restart_services:
            try:
                tz = tzlocal.get_localzone()
                if not tz:
                    tz = pytz.UTC
            except Exception:
                tz = pytz.UTC

            init_timestamp = time.time()
            init_timestamp_str = datetime.datetime.utcfromtimestamp(init_timestamp).isoformat() + "Z"

            process_id = os.getpid()

            event_loop_alias = ""
            event_loop_version = ""
            try:
                if "uvloop." in str(loop.__class__):
                    event_loop_alias = "uvloop"
                    import uvloop

                    event_loop_version = str(uvloop.__version__)
                elif "asyncio." in str(loop.__class__):
                    event_loop_alias = "asyncio"
                else:
                    event_loop_alias = "{}.{}".format(loop.__class__.__module__, loop.__class__.__name__)
            except Exception:
                event_loop_alias = str(loop)

            clear_services()
            clear_execution_context()
            set_execution_context(
                {
                    "tomodachi_version": tomodachi.__version__,
                    "python_version": platform.python_version(),
                    "system_platform": platform.system(),
                    "process_id": process_id,
                    "init_timestamp": init_timestamp_str,
                    "event_loop": event_loop_alias,
                }
            )

            if event_loop_alias == "uvloop" and event_loop_version:
                set_execution_context(
                    {
                        "uvloop_version": event_loop_version,
                    }
                )

            if watcher:
                init_local_datetime = (
                    datetime.datetime.fromtimestamp(init_timestamp)
                    if tz is not pytz.UTC
                    else datetime.datetime.utcfromtimestamp(init_timestamp)
                )

                print("---")
                print("Starting tomodachi services (pid: {}) ...".format(process_id))
                for file in service_files:
                    print("* {}".format(file))

                print()
                print(
                    "Current version: tomodachi {} on Python {}".format(
                        tomodachi.__version__, platform.python_version()
                    )
                )
                print(
                    "Event loop implementation: {}{}".format(
                        event_loop_alias, " {}".format(event_loop_version) if event_loop_version else ""
                    )
                )
                print("Local time: {} {}".format(init_local_datetime.strftime("%B %d, %Y - %H:%M:%S,%f"), str(tz)))
                print("Timestamp in UTC: {}".format(init_timestamp_str))
                print()
                print("File watcher is active - code changes will automatically restart services")
                print("Quit running services with <ctrl+c>")
                print()

            cls._close_waiter = asyncio.Future()
            cls._stopped_waiter = asyncio.Future()
            cls.restart_services = False

            try:
                cls.services = set(
                    [
                        ServiceContainer(ServiceImporter.import_service_file(file), configuration)
                        for file in service_files
                    ]
                )
                result = loop.run_until_complete(
                    asyncio.wait([asyncio.ensure_future(service.run_until_complete()) for service in cls.services])
                )
                exception = [v.exception() for v in [value for value in result if value][0] if v.exception()]
                if exception:
                    raise cast(Exception, exception[0])
            except tomodachi.importer.ServicePackageError:
                pass
            except Exception as e:
                logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                if restarting:
                    logging.getLogger("watcher.restart").warning("Service cannot restart due to errors")
                    logging.getLogger("watcher.restart").warning("Trying again in 1.5 seconds")
                    loop.run_until_complete(asyncio.wait([asyncio.sleep(1.5)]))
                    if cls._close_waiter and not cls._close_waiter.done():
                        cls.restart_services = True
                    else:
                        for signame in ("SIGINT", "SIGTERM"):
                            loop.remove_signal_handler(getattr(signal, signame))
                else:
                    for signame in ("SIGINT", "SIGTERM"):
                        loop.remove_signal_handler(getattr(signal, signame))

            current_modules = [m for m in sys.modules.keys()]
            for m in current_modules:
                if m not in init_modules and m not in safe_modules:
                    del sys.modules[m]

            importlib.reload(tomodachi.container)
            importlib.reload(tomodachi.invoker)
            importlib.reload(tomodachi.invoker.base)
            importlib.reload(tomodachi.importer)

            restarting = True

        if watcher:
            if not watcher_future.done():
                try:
                    watcher_future.set_result(None)
                except RuntimeError:  # pragma: no cover
                    watcher_future.cancel()
                if not watcher_future.done():  # pragma: no cover
                    try:
                        loop.run_until_complete(watcher_future)
                    except (Exception, CancelledError):
                        pass
