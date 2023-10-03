import asyncio
import datetime
import importlib
import os
import platform
import signal
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional, Set, Union, cast

import tomodachi
import tomodachi.container
import tomodachi.importer
import tomodachi.invoker
from tomodachi import logging
from tomodachi.container import ServiceContainer
from tomodachi.helpers.execution_context import clear_execution_context, clear_services, set_execution_context
from tomodachi.helpers.safe_modules import SAFE_MODULES
from tomodachi.importer import ServiceImporter

CancelledError = asyncio.CancelledError
try:
    asyncioexceptions = getattr(asyncio, "exceptions")
    if asyncioexceptions:
        _CancelledError = asyncioexceptions.CancelledError
except (Exception, ModuleNotFoundError, ImportError):
    _CancelledError = asyncio.CancelledError


class ServiceLauncher(object):
    _close_waiter: Optional[asyncio.Future] = None
    _stopped_waiter: Optional[asyncio.Future] = None
    stop_services_pre_hook: Optional[Callable] = None
    stop_services_post_hook: Optional[Callable] = None
    restart_services = False
    services: Set = set()

    @classmethod
    def stop_services(cls) -> None:
        asyncio.ensure_future(cls._stop_services())

    @classmethod
    async def _stop_services(cls) -> None:
        if cls.stop_services_pre_hook:
            await cls.stop_services_pre_hook()
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
        if cls.stop_services_post_hook:
            await cls.stop_services_post_hook()

    @classmethod
    def run_until_complete(
        cls,
        service_files: Union[List, set],
        configuration: Optional[Dict] = None,
        watcher: Any = None,
    ) -> None:
        def sigintHandler(*args: Any) -> None:
            sys.stdout.write("\b\b\r")
            sys.stdout.flush()
            logging.getLogger("tomodachi.signal").warning(
                "interrupt signal <ctrl+c>", signal="SIGINT", process_id=os.getpid()
            )
            cls.restart_services = False

        def sigtermHandler(*args: Any) -> None:
            logging.getLogger("tomodachi.signal").warning(
                "received termination signal", signal="SIGTERM", process_id=os.getpid()
            )
            cls.restart_services = False

        loop: asyncio.AbstractEventLoop
        if sys.version_info.major == 3 and sys.version_info.minor < 10:
            loop = asyncio.get_event_loop()
        else:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop and loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for signame in ("SIGINT", "SIGTERM"):
            loop.add_signal_handler(getattr(signal, signame), cls.stop_services)

        signal.siginterrupt(signal.SIGTERM, False)
        signal.siginterrupt(signal.SIGUSR1, False)
        signal.signal(signal.SIGINT, sigintHandler)
        signal.signal(signal.SIGTERM, sigtermHandler)

        watcher_future = None
        if watcher:

            async def _watcher_restart(updated_files: Union[List, set]) -> None:
                cls.restart_services = True

                cwd = os.getcwd()
                for file in service_files:
                    try:
                        ServiceImporter.import_service_file(file, no_exec=True)
                    except (SyntaxError, IndentationError) as e:
                        error_filename = getattr(e, "filename", "")
                        if cwd.rstrip("/") and error_filename.startswith(cwd):
                            error_filename = "./" + error_filename[len(cwd) :].lstrip("/")
                        error_lineno = getattr(e, "lineno", None)
                        error_location = error_filename + (":" + str(error_lineno)) if error_lineno else ""

                        logging.getLogger("tomodachi.watcher").error(
                            "indentation error in file" if type(e) is IndentationError else "syntax error in file",
                            error_location=error_location if error_filename else Ellipsis,
                        )
                        traceback.print_exception(type(e), e, e.__traceback__, limit=0)
                        logging.getLogger("tomodachi.watcher").warning(
                            "restart failed due to error",
                            error_location=error_location if error_filename else Ellipsis,
                        )
                        cls.restart_services = False
                        return
                    except Exception:
                        logging.getLogger("tomodachi.watcher").warning("restart failed due to error")
                        cls.restart_services = False
                        return

                pre_import_current_modules = [m for m in sys.modules.keys()]
                for file in updated_files:
                    if file.lower().endswith(".py"):
                        module_name = file[:-3].replace("/", ".")
                        module_name_full_path = "{}/{}".format(os.path.realpath(cwd), file)[:-3].replace("/", ".")
                        try:
                            for m in pre_import_current_modules:
                                if m == module_name or (len(m) > len(file) and module_name_full_path.endswith(m)):
                                    ServiceImporter.import_module(file, no_exec=True)
                            for m in pre_import_current_modules:
                                if m == module_name or (len(m) > len(file) and module_name_full_path.endswith(m)):
                                    ServiceImporter.import_module(file)
                        except (SyntaxError, IndentationError) as e:
                            error_filename = getattr(e, "filename", "")
                            if cwd.rstrip("/") and error_filename.startswith(cwd):
                                error_filename = "./" + error_filename[len(cwd) :].lstrip("/")
                            error_lineno = getattr(e, "lineno", None)
                            error_location = error_filename + (":" + str(error_lineno)) if error_lineno else ""

                            logging.getLogger("tomodachi.watcher").error(
                                "indentation error in file" if type(e) is IndentationError else "syntax error in file",
                                error_location=error_location if error_filename else Ellipsis,
                            )
                            traceback.print_exception(type(e), e, e.__traceback__, limit=0)
                            logging.getLogger("tomodachi.watcher").warning(
                                "restart failed due to error",
                                error_location=error_location if error_filename else Ellipsis,
                            )
                            cls.restart_services = False
                            return
                        except Exception:
                            logging.getLogger("tomodachi.watcher").warning("restart failed due to error")
                            cls.restart_services = False
                            return

                for file in service_files:
                    try:
                        ServiceImporter.import_service_file(file)
                    except (SyntaxError, IndentationError) as e:
                        error_filename = getattr(e, "filename", "")
                        if cwd.rstrip("/") and error_filename.startswith(cwd):
                            error_filename = "./" + error_filename[len(cwd) :].lstrip("/")
                        error_lineno = getattr(e, "lineno", None)
                        error_location = error_filename + (":" + str(error_lineno)) if error_lineno else ""

                        logging.getLogger("tomodachi.watcher").error(
                            "indentation error in file" if type(e) is IndentationError else "syntax error in file",
                            error_location=error_location if error_filename else Ellipsis,
                        )
                        traceback.print_exception(type(e), e, e.__traceback__, limit=0)
                        logging.getLogger("tomodachi.watcher").warning(
                            "restart failed due to error",
                            error_location=error_location if error_filename else Ellipsis,
                        )
                        cls.restart_services = False
                        return
                    except Exception:
                        logging.getLogger("tomodachi.watcher").warning("restart failed due to error")
                        cls.restart_services = False
                        return

                logging.getLogger("tomodachi.watcher").warning("restarting services")
                cls.stop_services()

            watcher_future = loop.run_until_complete(watcher.watch(loop=loop, callback_func=_watcher_restart))

        cls.restart_services = True
        init_modules = [m for m in sys.modules.keys()]

        restarting = False
        while cls.restart_services:
            if restarting:
                log_level = logging.INFO
                tomodachi.logging.set_default_formatter()
                tomodachi.logging.configure(log_level=log_level)

            init_timestamp_str = (
                datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
            )

            process_id = os.getpid()

            event_loop_alias = ""
            event_loop_version = ""
            try:
                if "uvloop." in str(loop.__class__):
                    event_loop_alias = "uvloop"
                    import uvloop  # noqa  # isort:skip

                    event_loop_version = str(getattr(uvloop, "__version__", ""))
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
                    "cwd": os.getcwd(),
                    "watcher_enabled": True if watcher else False,
                }
            )

            if event_loop_version:
                set_execution_context(
                    {
                        "event_loop_version": event_loop_version,
                    }
                )

            if event_loop_alias == "uvloop" and event_loop_version:
                set_execution_context(
                    {
                        "uvloop_version": event_loop_version,
                    }
                )

            if watcher:
                from tomodachi.helpers.banner import render_banner  # noqa  # isort:skip

                render_banner(service_files=service_files)

            tomodachi.get_contextvar("exit_code").set(-1)
            tomodachi.SERVICE_EXIT_CODE = tomodachi.DEFAULT_SERVICE_EXIT_CODE

            async def _set_waiters() -> None:
                cls._close_waiter = asyncio.Future()
                cls._stopped_waiter = asyncio.Future()

            loop.run_until_complete(_set_waiters())
            cls.restart_services = False

            try:
                cls.services = set(
                    [
                        ServiceContainer(ServiceImporter.import_service_file(file), configuration)
                        for file in service_files
                    ]
                )

                async def _run_until_complete() -> Any:
                    return await asyncio.wait(
                        [asyncio.ensure_future(service.run_until_complete()) for service in cls.services]
                    )

                result = loop.run_until_complete(_run_until_complete())
                exception = [v.exception() for v in [value for value in result if value][0] if v.exception()]
                if exception:
                    raise cast(Exception, exception[0])
                elif restarting and tomodachi.SERVICE_EXIT_CODE and cls._close_waiter and not cls._close_waiter.done():
                    cls.restart_services = True
                    logging.getLogger("tomodachi.watcher").warning("service exited due to errors")
                    logging.getLogger("tomodachi.watcher").warning("trying again in 1.5 seconds")
                    loop.run_until_complete(asyncio.sleep(1.5))

            except tomodachi.importer.ServicePackageError:
                pass
            except (SyntaxError, IndentationError) as e:
                cwd = os.getcwd()
                error_filename = getattr(e, "filename", "")
                if error_filename.startswith(cwd):
                    error_filename = error_filename[len(cwd) :].lstrip("/")
                error_lineno = getattr(e, "lineno", None)
                error_location = error_filename + (":" + str(error_lineno)) if error_lineno else ""

                logging.getLogger("exception").error(
                    "indentation error in file" if type(e) is IndentationError else "syntax error in file",
                    error_location=error_location if error_filename else Ellipsis,
                )
                traceback.print_exception(type(e), e, e.__traceback__, limit=0)
                if not cls.restart_services:
                    tomodachi.SERVICE_EXIT_CODE = 1
            except Exception as e:
                logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))

                if isinstance(e, ModuleNotFoundError):  # pragma: no cover
                    missing_module_name = str(getattr(e, "name", None) or "")
                    if missing_module_name:
                        color = ""
                        color_reset = ""
                        try:
                            import colorama  # noqa  # isort:skip

                            color = colorama.Fore.WHITE + colorama.Back.RED
                            color_reset = colorama.Style.RESET_ALL
                        except Exception:
                            pass

                        print("")
                        print(
                            "{}[fatal error] The '{}' package is missing or cannot be imported.{}".format(
                                color, missing_module_name, color_reset
                            )
                        )
                        print("")

                if restarting:
                    logging.getLogger("tomodachi.watcher").warning("cannot restart due to errors")
                    logging.getLogger("tomodachi.watcher").warning("trying again in 1.5 seconds")
                    loop.run_until_complete(asyncio.sleep(1.5))
                    if cls._close_waiter and not cls._close_waiter.done():
                        cls.restart_services = True
                    else:
                        for signame in ("SIGINT", "SIGTERM"):
                            loop.remove_signal_handler(getattr(signal, signame))
                else:
                    for signame in ("SIGINT", "SIGTERM"):
                        loop.remove_signal_handler(getattr(signal, signame))

                if not cls.restart_services:
                    tomodachi.SERVICE_EXIT_CODE = 1

            if cls.restart_services:
                # log handler cleanup
                logging.remove_handlers()
                tomodachi.logging.reset_context()

            current_modules = [m for m in sys.modules.keys()]
            for m in current_modules:
                if m not in init_modules and m not in SAFE_MODULES:
                    del sys.modules[m]

            importlib.reload(tomodachi.container)
            importlib.reload(tomodachi.invoker)
            importlib.reload(tomodachi.invoker.base)
            importlib.reload(tomodachi.importer)

            restarting = True

        if watcher:
            if watcher_future and not watcher_future.done():
                try:
                    watcher_future.set_result(None)
                except RuntimeError:  # pragma: no cover
                    watcher_future.cancel()
                if not watcher_future.done():  # pragma: no cover
                    try:
                        loop.run_until_complete(watcher_future)
                    except (Exception, CancelledError, _CancelledError):
                        pass
