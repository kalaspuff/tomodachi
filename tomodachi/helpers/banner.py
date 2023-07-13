import asyncio
import datetime
import enum
import os
import platform
import shlex
import sys
import time
from typing import Any, List, Optional, Union, cast

import tomodachi
import tomodachi.__version__
import tomodachi.importer
from tomodachi import logging
from tomodachi.helpers.execution_context import get_execution_context
from tomodachi.importer import ServiceImporter

TOMODACHI_ASCII = """
███████████████████████████████████████████████████████████████████████████████
███████████████─▄─▄─█─▄▄─█▄─▀█▀─▄█─▄▄─█▄─▄▄▀██▀▄─██─▄▄▄─█─█─█▄─▄███████████████
█████████████████─███─██─██─█▄█─██─██─██─██─██─▀─██─███▀█─▄─██─████████████████
▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▄▄▄▀▀▄▄▄▄▀▄▄▄▀▄▄▄▀▄▄▄▄▀▄▄▄▄▀▀▄▄▀▄▄▀▄▄▄▄▄▀▄▀▄▀▄▄▄▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
""".strip()

TOMODACHI_ASCII = """
▀█▀ █▀█ █▀▄▀█ █▀█ █▀▄ ▄▀█ █▀▀ █░█ █
░█░ █▄█ █░▀░█ █▄█ █▄▀ █▀█ █▄▄ █▀█ █
""".strip()


class ColorFore:
    BLACK = ""
    RED = ""
    GREEN = ""
    YELLOW = ""
    BLUE = ""
    MAGENTA = ""
    CYAN = ""
    WHITE = ""
    RESET = ""

    LIGHTBLACK_EX = ""
    LIGHTRED_EX = ""
    LIGHTGREEN_EX = ""
    LIGHTYELLOW_EX = ""
    LIGHTBLUE_EX = ""
    LIGHTMAGENTA_EX = ""
    LIGHTCYAN_EX = ""
    LIGHTWHITE_EX = ""


class ColorBack:
    LIGHTGREEN_EX = ""
    LIGHTYELLOW_EX = ""
    LIGHTBLUE_EX = ""
    LIGHTWHITE_EX = ""


class ColorStyle:
    BRIGHT = ""
    DIM = ""
    NORMAL = ""
    RESET_ALL = ""


COLOR = ColorFore()
COLOR_BACK = ColorBack()
COLOR_STYLE = ColorStyle()
COLOR_RESET = ""
try:
    import colorama  # noqa  # isort:skip

    COLOR = colorama.Fore
    COLOR_BACK = colorama.Back
    COLOR_STYLE = colorama.Style
    COLOR_RESET = colorama.Style.RESET_ALL
except Exception:
    pass


def render_banner(
    service_files: Union[List, set],
    loop: Optional[asyncio.AbstractEventLoop] = None,
    init_timestamp: Optional[Union[float, str]] = None,
    process_id: Optional[int] = None,
    event_loop_alias: Optional[str] = None,
    event_loop_version: Optional[str] = None,
    cwd: Optional[str] = None,
    watcher_enabled: Optional[bool] = None,
) -> None:
    context = get_execution_context()
    if isinstance(init_timestamp, str):
        init_timestamp_str = init_timestamp
        init_timestamp = datetime.datetime.strptime(init_timestamp_str, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
    elif isinstance(init_timestamp, (int, float)):
        init_timestamp_str = datetime.datetime.utcfromtimestamp(init_timestamp).isoformat(timespec="microseconds") + "Z"
    elif init_timestamp is None:
        init_timestamp_str = context.get("init_timestamp") or ""
        if init_timestamp_str:
            init_timestamp = datetime.datetime.strptime(init_timestamp_str, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
        else:
            init_timestamp = time.time()
            init_timestamp_str = (
                datetime.datetime.utcfromtimestamp(init_timestamp).isoformat(timespec="microseconds") + "Z"
            )

    if process_id is None:
        process_id = context.get("process_id", os.getpid()) or os.getpid()

    if cwd is None:
        cwd = context.get("cwd", os.getcwd()) or os.getcwd()

    if loop is None:
        if sys.version_info.major == 3 and sys.version_info.minor < 10:
            loop = asyncio.get_event_loop()
        else:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()

    if event_loop_alias is None:
        event_loop_alias = context.get("event_loop")
    if event_loop_version is None:
        event_loop_version = context.get("event_loop_version")
    if event_loop_alias is None:
        event_loop_alias = ""
        try:
            if "uvloop." in str(loop.__class__):
                event_loop_alias = "uvloop"
                import uvloop  # noqa  # isort:skip

                if event_loop_version is None:
                    event_loop_version = str(uvloop.__version__)  # type: ignore
            elif "asyncio." in str(loop.__class__):
                event_loop_alias = "asyncio"
            else:
                event_loop_alias = "{}.{}".format(loop.__class__.__module__, loop.__class__.__name__)
        except Exception:
            event_loop_alias = str(loop)
    if event_loop_version is None:
        event_loop_version = ""

    if watcher_enabled is None:
        watcher_enabled = context.get("watcher_enabled", False)

    event_loop_setting = str(tomodachi.context("loop.setting") or "")

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

    # print("")
    # print("---")
    print("")
    print(
        COLOR_RESET
        + COLOR.RESET
        + COLOR.LIGHTBLACK_EX
        + COLOR_STYLE.BRIGHT
        + COLOR_STYLE.DIM
        + TOMODACHI_ASCII
        + COLOR_RESET
    )
    print("")

    arg0 = sys.argv[0]
    if arg0.endswith("/__main__.py"):
        for path in sys.path:
            if arg0.startswith(path + "/"):
                arg0 = arg0.split(path + "/", 1)[-1].rsplit("/__main__.py", 1)[0]
                break

        arg0 = arg0.replace("/", ".")
        process_cmd = ["python", "-m", arg0] + sys.argv[1:]
    else:
        process_cmd = [arg0.rsplit("/", 1)[-1]] + sys.argv[1:]

    actual_file_paths = []
    potential_file_paths = set()

    for file_path in service_files:
        file_path_ = file_path
        potential_file_paths.add(file_path)

        try:

            async def _import_module_without_logger() -> Any:
                logging.disable_logger("tomodachi.importer")
                return ServiceImporter.import_service_file(file_path)

            service_import = loop.run_until_complete(_import_module_without_logger())
            if service_import and service_import.__file__:
                file_path_ = service_import.__file__
                potential_file_paths.add(file_path_)
                if file_path_.endswith(".pyc"):
                    file_path_ = file_path_[:-1]
                    potential_file_paths.add(file_path_)

                if cwd.rstrip("/") and file_path_.startswith(cwd.rstrip("/") + "/"):
                    file_path_ = file_path_.split(cwd.rstrip("/") + "/", 1)[-1]
                    potential_file_paths.add(file_path_)
                    file_path_ = "./" + file_path_
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
        if len(process_cmd_str) <= 60:
            break
        process_cmd = [arg for arg in process_cmd if arg.strip() and arg != "..."][:-1] + ["..."]

    os_name = platform.system()
    if os_name == "Darwin":
        os_name = "macOS"

    machine = platform.machine() or platform.processor()
    node_name = platform.node() or os.environ.get("HOSTNAME", "") or "..."

    LABEL_HIGHLIGHT = f"{COLOR_RESET}{COLOR.LIGHTBLACK_EX}{COLOR_STYLE.BRIGHT}{COLOR_STYLE.DIM}"
    LABEL_HIGHLIGHT_BRIGHT = f"{COLOR_RESET}{COLOR.LIGHTBLACK_EX}{COLOR_STYLE.BRIGHT}{COLOR_STYLE.DIM}"
    LABEL_NORMAL = f"{COLOR_RESET}{COLOR.LIGHTBLACK_EX}{COLOR_STYLE.DIM}"  # LABEL_HIGHLIGHT  # f"{COLOR_RESET}{COLOR.LIGHTBLACK_EX}{COLOR_STYLE.DIM}"
    DELIMITER = f"{COLOR_RESET}{COLOR_STYLE.DIM}⇢{COLOR_RESET}"
    DELIMITER_BRIGHT = f"{COLOR_RESET}{COLOR_STYLE.BRIGHT}⇢{COLOR_RESET}"
    TOMODACHI_HIGHLIGHT = f"{COLOR_BACK.LIGHTWHITE_EX}{COLOR.BLACK}{COLOR_STYLE.BRIGHT}"
    TEXT_HIGHLIGHT = f"{COLOR_RESET}{COLOR_STYLE.DIM}{COLOR_STYLE.BRIGHT}"
    TEXT_HIGHLIGHT = f"{COLOR_RESET}{COLOR.LIGHTWHITE_EX}{COLOR_STYLE.BRIGHT}{COLOR_STYLE.DIM}"
    TEXT_HIGHLIGHT = f"{COLOR_RESET}{COLOR.LIGHTBLACK_EX}{COLOR_STYLE.BRIGHT}"
    NOTICE_TEXT = f"{COLOR_RESET}{COLOR.LIGHTBLACK_EX}{COLOR_STYLE.DIM}"  # LABEL_NORMAL  # f"{COLOR_RESET}{COLOR.LIGHTBLACK_EX}{COLOR_STYLE.DIM}"
    NOTICE_TEXT_HIGHLIGHT = f"{COLOR_RESET}{COLOR.WHITE}{COLOR_STYLE.NORMAL}"
    NOTICE_TEXT_TOPIC_WATCHER = f"{COLOR_RESET}{COLOR.LIGHTCYAN_EX}{COLOR_STYLE.DIM}{COLOR_STYLE.BRIGHT}"
    NOTICE_TEXT_TOPIC_EXIT = f"{COLOR_RESET}{COLOR.LIGHTYELLOW_EX}{COLOR_STYLE.DIM}{COLOR_STYLE.BRIGHT}"
    # PID_HIGHLIGHT = f"{colorama.Back.LIGHTYELLOW_EX}{COLOR.BLACK}{COLOR_STYLE.BRIGHT}"
    PID_HIGHLIGHT = TEXT_HIGHLIGHT  # f"{COLOR_RESET}{COLOR.WHITE}{COLOR_STYLE.BRIGHT}"
    pid_str = f"[pid: {process_id}]"
    pid_str = f"{pid_str:<14}"
    pid_str = (
        pid_str[0:1]
        + COLOR_RESET
        + PID_HIGHLIGHT
        + pid_str[1:4]
        + COLOR_RESET
        + PID_HIGHLIGHT
        + pid_str[4:6]
        + COLOR_RESET
        + PID_HIGHLIGHT
        + pid_str[6 : 6 + len(str(process_id))]
        + COLOR_RESET
        + LABEL_HIGHLIGHT
        + pid_str[6 + len(str(process_id)) :]
    )

    # print(f" {TOMODACHI_HIGHLIGHT}tomodachi{COLOR_RESET}")
    # print("")
    print(
        f"{LABEL_HIGHLIGHT_BRIGHT}process {pid_str}{COLOR_RESET} {DELIMITER} {colorama.Back.LIGHTWHITE_EX}{COLOR.BLACK}{COLOR_STYLE.BRIGHT}{TEXT_HIGHLIGHT}$ {process_cmd_str}{COLOR_RESET}"
    )

    for file_num, file_path in enumerate(actual_file_paths, 1):
        file_path_ = file_path
        while True:
            if len(file_path_) <= 60:
                break
            file_path_ = ".../" + "/".join(file_path_.replace(".../", "").split("/")[1:])

        if len(actual_file_paths) == 1:
            file_num = ""
        else:
            file_num = f"[{file_num}]"
        print(
            f"{LABEL_HIGHLIGHT_BRIGHT}service file {file_num:4s}      {DELIMITER} {COLOR.YELLOW}{COLOR_STYLE.BRIGHT}{TEXT_HIGHLIGHT}{file_path_}{COLOR_RESET}"
        )

    venv_prompt = ""
    venv_path = ""
    home_path = os.path.expanduser("~").rstrip("/")
    python_exec_prefix = sys.exec_prefix
    python_path = sys.executable
    venv_environ = os.environ.get("VIRTUAL_ENV", "")

    # venv_environ = os.getcwd() + "/.venv"
    # python_exec_prefix = os.getcwd() + "/.venv"
    # python_path = "/usr/local/bin/python"

    if "venv" in python_exec_prefix or "virtualenv" in python_exec_prefix or venv_environ:
        try:
            venv_path = python_exec_prefix
            if cwd.rstrip("/") and venv_path.startswith(cwd.rstrip("/") + "/"):
                venv_path = "./" + venv_path.split(cwd.rstrip("/") + "/", 1)[-1]
            elif home_path and venv_path.startswith(home_path + "/"):
                venv_path = "~/" + venv_path.split(home_path + "/", 1)[-1]
            venv_config = open(os.path.join(python_exec_prefix, "pyvenv.cfg"), "r").read()
            for line in venv_config.split("\n"):
                if line.startswith("prompt = "):
                    venv_prompt = line.split("prompt = ", 1)[-1].replace('"', "").replace("'", "")
                    break
        except (FileNotFoundError, PermissionError, Exception):
            pass

    if cwd.rstrip("/") and python_path.startswith(cwd.rstrip("/") + "/"):
        python_path = "./" + python_path.split(cwd.rstrip("/") + "/", 1)[-1]
    elif home_path and python_path.startswith(home_path + "/"):
        python_path = "~/" + python_path.split(home_path + "/", 1)[-1]

    poetry_venv = ""
    poetry_is_active = os.environ.get("POETRY_ACTIVE", "").lower() in ("1", "true") and venv_environ
    if poetry_is_active:
        if cwd.rstrip("/") and venv_environ.startswith(cwd.rstrip("/") + "/"):
            poetry_venv = venv_environ
            if cwd.rstrip("/") and poetry_venv.startswith(cwd.rstrip("/") + "/"):
                poetry_venv = "./" + poetry_venv.split(cwd.rstrip("/") + "/", 1)[-1]
            elif home_path and poetry_venv.startswith(home_path + "/"):
                poetry_venv = "~/" + poetry_venv.split(home_path + "/", 1)[-1]
        elif venv_path.rsplit("/", 1)[-1] in (".venv", "venv"):
            poetry_venv = venv_environ
        else:
            poetry_venv = venv_environ.rsplit("/", 1)[-1]

    if venv_path and python_path.startswith(venv_path + "/"):
        python_path = "$VIRTUAL_ENV/" + python_path.split(venv_path + "/", 1)[-1]
    elif poetry_venv and "/" in poetry_venv and python_path.startswith(poetry_venv + "/"):
        python_path = "$VIRTUAL_ENV/" + python_path.split(poetry_venv + "/", 1)[-1]

    init_local_time_str = init_local_datetime.strftime("%B %d, %Y - %H:%M:%S") + " " + str(tz)

    print("")

    print(
        f"{LABEL_HIGHLIGHT}operating system       {DELIMITER} {TEXT_HIGHLIGHT}{os_name} on {machine}{LABEL_NORMAL}"
        + (f" (hostname: {node_name})" if node_name else "")
        + COLOR_RESET
    )

    print(
        f"{LABEL_HIGHLIGHT}python runtime         {DELIMITER} {TEXT_HIGHLIGHT}{platform.python_implementation()} {platform.python_version()}{LABEL_NORMAL} (build: {platform.python_build()[1]}){COLOR_RESET}"
    )

    # print(
    #     f"{LABEL_HIGHLIGHT}tomodachi version      {DELIMITER} {TEXT_HIGHLIGHT}{tomodachi.__version__}{LABEL_NORMAL}"
    #     + (f" [in venv: {TEXT_HIGHLIGHT}{venv_prompt}{LABEL_NORMAL}]" if venv_prompt else "")
    #     + COLOR_RESET
    # )

    tomodachi_release_date = ""

    print(
        f"{LABEL_HIGHLIGHT}tomodachi version      {DELIMITER} {TEXT_HIGHLIGHT}{tomodachi.__version__}{LABEL_NORMAL}"
        + (f" ({tomodachi_release_date})" if tomodachi_release_date else " (local development version)")
        + COLOR_RESET
    )

    if poetry_venv and poetry_venv != venv_path and venv_path.rsplit("/", 1)[-1] not in (".venv", "venv"):
        print(
            f"{LABEL_HIGHLIGHT}virtualenv             {DELIMITER} {TEXT_HIGHLIGHT}poetry env{LABEL_NORMAL} (name: {poetry_venv})"
            + COLOR_RESET
        )
    elif poetry_venv:
        print(
            f"{LABEL_HIGHLIGHT}virtualenv path        {DELIMITER} {TEXT_HIGHLIGHT}{poetry_venv}{LABEL_NORMAL} (poetry active)"
            # + (f" [{venv_path}" if venv_path else "")
            + COLOR_RESET
        )
    elif venv_path:
        if venv_path:
            print(
                f"{LABEL_HIGHLIGHT}virtualenv path        {DELIMITER} {TEXT_HIGHLIGHT}{venv_path}{LABEL_NORMAL}"
                + (f" (prompt: {venv_prompt})" if venv_prompt and venv_prompt != venv_path.rsplit("/", 1)[-1] else "")
                + COLOR_RESET
            )

    python_path_is_outside_venv = bool(venv_path and "$VIRTUAL_ENV" not in python_path)
    if python_path_is_outside_venv or (
        not venv_path
        and python_path
        not in (
            "/usr/bin/python",
            "/usr/bin/python3",
            "/usr/local/bin/python",
            "/usr/local/bin/python3",
            "/opt/bin/python",
            "/opt/bin/python3",
            "/opt/homebrew/opt/python/bin/python",
            "/opt/homebrew/opt/python/bin/python3",
            "/opt/homebrew/opt/bin/python",
            "/opt/homebrew/opt/bin/python3",
        )
    ):
        print(
            f"{LABEL_HIGHLIGHT}python path            {DELIMITER} {TEXT_HIGHLIGHT}{python_path}{LABEL_NORMAL}"
            + (
                f" {COLOR_RESET}{COLOR.LIGHTRED_EX}{COLOR_STYLE.BRIGHT}{COLOR_STYLE.DIM}[outside venv]"
                if python_path_is_outside_venv
                else ""
            )
            + COLOR_RESET
        )

    print(
        f"{LABEL_HIGHLIGHT}event loop             {DELIMITER} {TEXT_HIGHLIGHT}{event_loop_alias}{LABEL_NORMAL}"
        + (f" (version: {event_loop_version})" if event_loop_version else "")
        + (f" ({event_loop_setting})" if event_loop_setting == "auto" else "")
        + COLOR_RESET
    )

    #    if tz:
    #        print(f"{LABEL_HIGHLIGHT}local time             {DELIMITER} {LABEL_NORMAL}{init_local_time_str}{COLOR_RESET}")
    #    print(f"{LABEL_HIGHLIGHT}start timestamp        {DELIMITER} {LABEL_NORMAL}{init_timestamp_str}{COLOR_RESET}")

    print("")

    if watcher_enabled:
        print(
            f"{NOTICE_TEXT_TOPIC_WATCHER}⌁ [watcher] file watcher enabled (code changes auto restart services){COLOR_RESET}"
        )
    print(f"{NOTICE_TEXT_TOPIC_EXIT}⌁ [notice ] stop running services with <ctrl+c> (graceful teardown){COLOR_RESET}")

    print(COLOR_RESET + "")
