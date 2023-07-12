import asyncio
import datetime
import importlib
import os
import platform
import shlex
import signal
import sys
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Set, Union, cast

import tomodachi
import tomodachi.__version__
import tomodachi.container
import tomodachi.importer
import tomodachi.invoker
from tomodachi import get_services, logging
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


TOMODACHI_ASCII = """
███████████████████████████████████████████████████
█─▄─▄─█─▄▄─█▄─▀█▀─▄█─▄▄─█▄─▄▄▀██▀▄─██─▄▄▄─█─█─█▄─▄█
███─███─██─██─█▄█─██─██─██─██─██─▀─██─███▀█─▄─██─██
▀▀▄▄▄▀▀▄▄▄▄▀▄▄▄▀▄▄▄▀▄▄▄▄▀▄▄▄▄▀▀▄▄▀▄▄▀▄▄▄▄▄▀▄▀▄▀▄▄▄▀
"""

TOMODACHI_ASCII = """
█████████████████████████████████████████████████████████████████████████
████████████─▄─▄─█─▄▄─█▄─▀█▀─▄█─▄▄─█▄─▄▄▀██▀▄─██─▄▄▄─█─█─█▄─▄████████████
██████████████─███─██─██─█▄█─██─██─██─██─██─▀─██─███▀█─▄─██─█████████████
▀▀▀▀▀▀▀▀▀▀▀▀▀▄▄▄▀▀▄▄▄▄▀▄▄▄▀▄▄▄▀▄▄▄▄▀▄▄▄▄▀▀▄▄▀▄▄▀▄▄▄▄▄▀▄▀▄▀▄▄▄▀▀▀▀▀▀▀▀▀▀▀▀
"""

TOMODACHI_ASCII = """
███████████████████████████████████████████████████████████████████████████████
███████████████─▄─▄─█─▄▄─█▄─▀█▀─▄█─▄▄─█▄─▄▄▀██▀▄─██─▄▄▄─█─█─█▄─▄███████████████
█████████████████─███─██─██─█▄█─██─██─██─██─██─▀─██─███▀█─▄─██─████████████████
▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▄▄▄▀▀▄▄▄▄▀▄▄▄▀▄▄▄▀▄▄▄▄▀▄▄▄▄▀▀▄▄▀▄▄▀▄▄▄▄▄▀▄▀▄▀▄▄▄▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
"""

TOMODACHI_ASCII_ = """

▀▀█▀▀ █▀▀█ █▀▄▀█ █▀▀█ █▀▀▄ █▀▀█ █▀▀ █──█ ─▀─
──█── █──█ █─▀─█ █──█ █──█ █▄▄█ █── █▀▀█ ▀█▀
──▀── ▀▀▀▀ ▀───▀ ▀▀▀▀ ▀▀▀─ ▀──▀ ▀▀▀ ▀──▀ ▀▀▀
"""


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

        # logging.basicConfig(level=logging.DEBUG)

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
                        ServiceImporter.import_service_file(file)
                    except (SyntaxError, IndentationError) as e:
                        # logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                        error_filename = getattr(e, "filename", "")
                        if error_filename.startswith(cwd):
                            error_filename = error_filename[len(cwd) :].lstrip("/")
                        error_lineno = getattr(e, "lineno", None)
                        error_location = error_filename + (":" + str(error_lineno)) if error_lineno else ""

                        logging.getLogger("tomodachi.watcher").error(
                            "indentation error in file" if type(e) is IndentationError else "syntax error in file",
                            error_location=error_location if error_filename else Ellipsis,
                        )
                        traceback.print_exception(e, limit=0)
                        logging.getLogger("tomodachi.watcher").warning(
                            "restart failed due to error",
                            error_location=error_location if error_filename else Ellipsis,
                        )
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
                                    ServiceImporter.import_module(file)
                        except (SyntaxError, IndentationError) as e:
                            # logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                            # logging.getLogger("tomodachi.watcher").warning("cannot restart due to errors")
                            error_filename = getattr(e, "filename", "")
                            if error_filename.startswith(cwd):
                                error_filename = error_filename[len(cwd) :].lstrip("/")
                            error_lineno = getattr(e, "lineno", None)
                            error_location = error_filename + (":" + str(error_lineno)) if error_lineno else ""

                            logging.getLogger("tomodachi.watcher").error(
                                "indentation error in file" if type(e) is IndentationError else "syntax error in file",
                                error_location=error_location if error_filename else Ellipsis,
                            )
                            traceback.print_exception(e, limit=0)
                            logging.getLogger("tomodachi.watcher").warning(
                                "restart failed due to error",
                                error_location=error_location if error_filename else Ellipsis,
                            )
                            cls.restart_services = False
                            return

                logging.getLogger("tomodachi.watcher").warning("restarting services")
                cls.stop_services()

            watcher_future = loop.run_until_complete(watcher.watch(loop=loop, callback_func=_watcher_restart))

        cls.restart_services = True
        init_modules = [m for m in sys.modules.keys()]

        restarting = False
        while cls.restart_services:
            init_timestamp = time.time()
            init_timestamp_str = datetime.datetime.utcfromtimestamp(init_timestamp).isoformat() + "Z"

            process_id = os.getpid()

            event_loop_alias = ""
            event_loop_version = ""
            try:
                if "uvloop." in str(loop.__class__):
                    event_loop_alias = "uvloop"
                    import uvloop  # noqa  # isort:skip

                    event_loop_version = str(uvloop.__version__)  # type: ignore
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
                tz: Any = None
                utc_tz: Any = None

                try:
                    import pytz  # noqa  # isort:skip
                    import tzlocal  # noqa  # isort:skip

                    utc_tz = pytz.UTC
                    try:
                        tz = tzlocal.get_localzone()
                        if not tz:
                            tz = pytz.UTC
                    except Exception:
                        tz = pytz.UTC
                except Exception:
                    pass

                init_local_datetime = (
                    datetime.datetime.fromtimestamp(init_timestamp)
                    if tz and tz is not utc_tz and str(tz) != "UTC"
                    else datetime.datetime.utcfromtimestamp(init_timestamp)
                )

                print("---")

                print(TOMODACHI_ASCII)

                arg0 = sys.argv[0]
                if arg0.endswith("/__main__.py"):
                    for path in sys.path:
                        if arg0.startswith(path + "/"):
                            arg0 = arg0.split(path + "/", 1)[-1].rsplit("/__main__.py", 1)[0]
                            break

                    arg0 = arg0.replace("/", ".")
                    process_cmd = ["python", "-m", arg0] + sys.argv[1:]
                else:
                    process_cmd = [arg0.rsplit(os.sep, 1)[-1]] + sys.argv[1:]

                actual_file_paths = []
                potential_file_paths = set()

                for file_path in service_files:
                    file_path_ = file_path
                    potential_file_paths.add(file_path)

                    try:

                        async def _import_module() -> Any:
                            logging.disable_logger("tomodachi.importer")
                            return ServiceImporter.import_service_file(file_path)

                        service_import = loop.run_until_complete(_import_module())
                        if service_import and service_import.__file__:
                            file_path_ = service_import.__file__
                            potential_file_paths.add(file_path_)
                            if file_path_.endswith(".pyc"):
                                file_path_ = file_path_[:-1]
                                potential_file_paths.add(file_path_)

                            if file_path_.startswith(os.getcwd() + "/"):
                                file_path_ = file_path_.split(os.getcwd() + "/", 1)[-1]
                                potential_file_paths.add(file_path_)
                    except tomodachi.importer.ServicePackageError:
                        pass
                    except (SyntaxError, IndentationError):
                        pass
                    except Exception:
                        pass

                    if file_path_ not in actual_file_paths:
                        actual_file_paths.append(file_path_)

                for file_path in potential_file_paths:
                    if file_path in process_cmd:
                        process_cmd = [arg for arg in process_cmd if arg != file_path]
                        if "<...>" not in process_cmd:
                            process_cmd.append("<...>")

                for value in ("-c", "--config"):
                    if value in process_cmd:
                        config_file_path = (process_cmd[process_cmd.index(value, 0) :] + ["..."])[1]
                        if config_file_path.endswith(".json"):
                            process_cmd = [arg if arg != config_file_path else "<...>" for arg in process_cmd]

                process_cmd = [arg for arg in process_cmd if arg.strip()]
                process_cmd_str: str
                while True:
                    process_cmd_str = shlex.join(process_cmd).replace("'<...>'", "<...>")
                    if len(process_cmd_str) <= 40:
                        break
                    process_cmd = [arg for arg in process_cmd if arg.strip() and arg != "..."][:-1] + ["..."]

                pid_str = f"[pid: {process_id}]"
                print(f" process {pid_str:<14} ⇢ `{process_cmd_str}`")

                for file_path in actual_file_paths:
                    file_path_ = file_path
                    while True:
                        if len(file_path_) <= 50:
                            break
                        file_path_ = ".../" + "/".join(file_path_.replace(".../", "").split("/")[1:])

                    print(f' service file           ⇢ "{file_path_}"')

                venv_prompt = ""
                if "venv" in sys.exec_prefix or "virtualenv" in sys.exec_prefix:
                    venv_config = open(os.path.join(sys.exec_prefix, "pyvenv.cfg"), "r").read()
                    for line in venv_config.split("\n"):
                        if line.startswith("prompt = "):
                            venv_prompt = line.split("prompt = ", 1)[-1]
                            break

                init_local_time_str = init_local_datetime.strftime("%B %d, %Y - %H:%M:%S") + " " + str(tz)
                print("")
                print(
                    f" python runtime         ⇢ {platform.python_implementation()} {platform.python_version()} (build: {platform.python_build()[1]})"
                )
                print(
                    f" tomodachi version      ⇢ {tomodachi.__version__}"
                    + (f" [in venv: {venv_prompt}]" if venv_prompt else "")
                )
                print(
                    f" event loop             ⇢ {event_loop_alias}"
                    + (f" {event_loop_version}" if event_loop_version else "")
                )
                if tz:
                    print(f" local time             ⇢ {init_local_time_str}")
                print(f" start timestamp        ⇢ {init_timestamp_str}")
                print("")
                print(" ---- file watcher is enabled (code changes will auto restart services)")
                print(" ---- stop running services with <ctrl+c> (graceful teardown)")
                print("")
                sys.exit(0)
                #         process [pid: 876140]         ⇢ `tomodachi run --loop asyncio ...`
                # print(f'process [pid: 1]      ⇢ "tomodachi run --loop uvloop ..."')

                # process [pid: 1]      ⇢ "tomodachi run --loop uvloop ..."
                # service file          ⇢ "examples/basic_examples/scheduler_example.py"
                #
                # tomodachi version     ⇢ 0.25.0 (released 3 months ago)
                # python runtime        ⇢ CPython 3.11.4 [venv: "tomodachi-py3.11"]
                # event loop impl.      ⇢ asyncio (auto)
                # local time            ⇢ Wed July 12, 2023 - 10:21:39 Europe/Stockholm
                # timestamp in UTC      ⇢ 2023-07-12T08:21:39.552710Z
                #
                # ---- file watcher is enabled (code changes will auto restart services)
                # ---- stop running services with <ctrl+c> (graceful teardown)

                # ---- service file ⇢ "examples/basic_examples/scheduler_example.py" ----
                #    print(f' ---- service file ⇢ "{file_path_}"')

                # : {', '.join(service_files)}")

                # print(f"    pid ⇢ {process_id}")
                # print(process_cmd)
                # print(sys.argv[0].rsplit(os.sep, 1)[-1])
                # print(" ".join(sys.argv[1:]))

                # print("Starting tomodachi services (pid: {}) ...".format(process_id))
                # for file in service_files:
                #     print("* {}".format(file))

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
                if tz:
                    print("Local time: {} {}".format(init_local_datetime.strftime("%B %d, %Y - %H:%M:%S,%f"), str(tz)))
                print("Timestamp in UTC: {}".format(init_timestamp_str))
                print()
                print("File watcher is active - code changes will automatically restart services")
                print("Quit running services with <ctrl+c>")
                print()

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
                # logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                # logging.getLogger("tomodachi.watcher").warning("cannot restart due to errors")
                cwd = os.getcwd()
                error_filename = getattr(e, "filename", "")
                if error_filename.startswith(cwd):
                    error_filename = error_filename[len(cwd) :].lstrip("/")
                error_lineno = getattr(e, "lineno", None)
                error_location = error_filename + (":" + str(error_lineno)) if error_lineno else ""

                logging.getLogger("tomodachi").error(
                    "indentation error in file" if type(e) is IndentationError else "syntax error in file",
                    error_location=error_location if error_filename else Ellipsis,
                )
                traceback.print_exception(e, limit=0)
                if not cls.restart_services:
                    tomodachi.SERVICE_EXIT_CODE = 1
            except Exception as e:
                logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))

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
