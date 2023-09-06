from typing import Any

from tomodachi import context, logging


def log(service: Any, *args: Any, **kwargs: Any) -> None:
    name: str = context("service.logger") or ""
    level = None
    message = None

    if len(args) == 1:
        message = args[0]
    if len(args) == 2:
        if type(args[0]) is int:
            level = args[0]
        elif type(args[0]) is str and str(args[0]).upper() in (
            "NOTSET",
            "DEBUG",
            "INFO",
            "WARN",
            "WARNING",
            "ERROR",
            "FATAL",
            "CRITICAL",
        ):
            level = getattr(logging, str(args[0]).upper())
        else:
            name = args[0]
        message = args[1]
    if len(args) == 3:
        name = args[0]
        level = int(args[1]) if type(args[1]) is int else getattr(logging, str(args[1]).upper())
        message = args[2]

    if "level" in kwargs:
        level = 0
        level_ = kwargs.pop("level", 0)
        if type(level_) is int:
            level = int(level_)
        else:
            level = int(getattr(logging, str(level_).upper()))
    if "lvl" in kwargs:
        level = 0
        level_ = kwargs.pop("lvl", 0)
        if type(level_) is int:
            level = int(level_)
        else:
            level = int(getattr(logging, str(level_).upper()))
    if "name" in kwargs:
        name = kwargs.pop("name", None) or ""
    if not message and "message" in kwargs:
        message = kwargs.pop("message", None)
    if not message and "msg" in kwargs:
        message = kwargs.pop("msg", None)

    if not level:
        level = logging.INFO
    if not name:
        name = context("service.logger")
    if not message:
        message = ""

    logging.getLogger(name or None).log(level, message, **kwargs)
