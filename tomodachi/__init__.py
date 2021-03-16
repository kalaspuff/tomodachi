from __future__ import annotations

import importlib
import uuid as uuid_
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast

from tomodachi.__version__ import __version__, __version_info__

try:
    from tomodachi.helpers.execution_context import clear_execution_context as _clear_execution_context
    from tomodachi.helpers.execution_context import clear_services as _clear_services
    from tomodachi.helpers.execution_context import (
        decrease_execution_context_value,
        get_execution_context,
        get_instance,
        get_service,
        increase_execution_context_value,
        set_execution_context,
    )
    from tomodachi.helpers.execution_context import set_service as _set_service
    from tomodachi.helpers.execution_context import unset_service as _unset_service
    from tomodachi.invoker import decorator
except Exception:  # pragma: no cover
    pass

__available_defs: Dict[str, Union[Tuple[str], Tuple[str, Optional[str]]]] = {
    "amqp": ("tomodachi.transport.amqp",),
    "amqp_publish": ("tomodachi.transport.amqp",),
    "aws_sns_sqs": ("tomodachi.transport.aws_sns_sqs",),
    "aws_sns_sqs_publish": ("tomodachi.transport.aws_sns_sqs",),
    "HttpException": ("tomodachi.transport.http",),
    "HttpResponse": ("tomodachi.transport.http", "Response"),
    "get_http_response_status": ("tomodachi.transport.http",),
    "get_http_response_status_sync": ("tomodachi.transport.http",),
    "http": ("tomodachi.transport.http",),
    "http_error": ("tomodachi.transport.http",),
    "http_static": ("tomodachi.transport.http",),
    "websocket": ("tomodachi.transport.http",),
    "ws": ("tomodachi.transport.http",),
    "daily": ("tomodachi.transport.schedule",),
    "heartbeat": ("tomodachi.transport.schedule",),
    "every_second": ("tomodachi.transport.schedule",),
    "hourly": ("tomodachi.transport.schedule",),
    "minutely": ("tomodachi.transport.schedule",),
    "monthly": ("tomodachi.transport.schedule",),
    "schedule": ("tomodachi.transport.schedule",),
    "scheduler": ("tomodachi.transport.schedule",),
    "aiobotocore_client_connector": ("tomodachi.helpers.aiobotocore_connector", "connector"),
    "AiobotocoreClientConnector": ("tomodachi.helpers.aiobotocore_connector", "ClientConnector"),
    "_log": ("tomodachi.helpers.logging", "log"),
    "_log_setup": ("tomodachi.helpers.logging", "log_setup"),
    "cli": ("tomodachi.cli", None),
}
__imported_modules: Dict[str, Any] = {}
__cached_defs: Dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    if name in __cached_defs:
        return __cached_defs[name]

    if name in __available_defs:
        module_name = __available_defs[name][0]
        real_name = (
            name if len(__available_defs[name]) < 2 else cast(Tuple[str, Optional[str]], __available_defs[name])[1]
        )

        if not __imported_modules.get(module_name):
            try:
                __imported_modules[module_name] = importlib.import_module(module_name)
            except ModuleNotFoundError as e:  # pragma: no cover
                import logging  # noqa  # isort:skip
                import sys  # noqa  # isort:skip

                missing_module_name = str(getattr(e, "name", None) or "")
                if missing_module_name:
                    print(
                        "Fatal dependency failure: '{}' failed to load (error: \"{}\")".format(
                            missing_module_name, str(e)
                        )
                    )
                    print("")
                    logging.exception("")
                    print("")

                logging.getLogger("exception").warning("Unable to initialize dependencies")
                logging.getLogger("exception").warning("Error: See above exceptions and traceback")

                print("")
                if missing_module_name:
                    color = ""
                    color_reset = ""
                    try:
                        import colorama  # noqa  # isort:skip

                        color = colorama.Fore.WHITE + colorama.Back.RED
                        color_reset = colorama.Style.RESET_ALL
                    except Exception:
                        pass

                    if module_name == "tomodachi.transport.http" and missing_module_name in ("aiohttp",):
                        print(
                            "{}[fatal error] The '{}' package is missing.{}".format(
                                color, missing_module_name, color_reset
                            )
                        )
                        print(
                            "{}[fatal error] Install 'tomodachi' with 'http' extras to use '@tomodachi.http' functions.{}".format(
                                color, color_reset
                            )
                        )
                        print("")
                    if module_name == "tomodachi.transport.aws_sns_sqs" and missing_module_name in (
                        "aiobotocore",
                        "botocore",
                        "aiohttp",
                    ):
                        print(
                            "{}[fatal error] The '{}' package is missing.{}".format(
                                color, missing_module_name, color_reset
                            )
                        )
                        print(
                            "{}[fatal error] Install 'tomodachi' with 'aws' extras to use '@tomodachi.aws_sns_sqs' functions.{}".format(
                                color, color_reset
                            )
                        )
                        print("")
                    if module_name == "tomodachi.transport.amqp" and missing_module_name in ("aioamqp",):
                        print(
                            "{}[fatal error] The '{}' package is missing.{}".format(
                                color, missing_module_name, color_reset
                            )
                        )
                        print(
                            "{}[fatal error] Install 'tomodachi' with 'amqp' extras to use '@tomodachi.amqp' functions.{}".format(
                                color, color_reset
                            )
                        )
                        print("")
                    if module_name == "tomodachi.transport.schedule" and missing_module_name in (
                        "tzlocal",
                        "pytz",
                        "zoneinfo",
                    ):
                        print(
                            "{}[fatal error] The '{}' package is missing.{}".format(
                                color, missing_module_name, color_reset
                            )
                        )
                        print(
                            "{}[fatal error] Install 'tomodachi' with 'scheduler' extras to use '@tomodachi.schedule' functions.{}".format(
                                color, color_reset
                            )
                        )
                        print("")
                print("Exiting: Service terminating with exit code: 1")
                sys.exit(1)
            except Exception as e:  # pragma: no cover
                import logging  # noqa  # isort:skip

                print(
                    "Fatal dependency failure: '{}:{}' failed to load (error: \"{}\")".format(module_name, name, str(e))
                )
                print("")
                logging.exception("")
                print("")

                logging.getLogger("exception").warning("Unable to initialize dependencies")
                logging.getLogger("exception").warning("Error: See above exceptions and traceback")

                raise e

        module = __imported_modules.get(module_name)

        if real_name is not None:
            __cached_defs[name] = getattr(module, real_name)
        else:
            __cached_defs[name] = module

        return __cached_defs[name]

    raise AttributeError("module 'tomodachi' has no attribute '{}'".format(name))


__author__: str = "Carl Oscar Aaro"
__email__: str = "hello@carloscar.com"

CLASS_ATTRIBUTE: str = "_tomodachi_class_is_service_class"

__all__ = [
    "service",
    "Service",
    "__version__",
    "__version_info__",
    "__author__",
    "__email__",
    "decorator",
    "cli",
    "run",
    "_run",
    "_set_service",
    "_unset_service",
    "_clear_services",
    "set_execution_context",
    "get_execution_context",
    "_clear_execution_context",
    "decrease_execution_context_value",
    "increase_execution_context_value",
    "get_service",
    "get_instance",
    "AiobotocoreClientConnector",
    "aiobotocore_client_connector",
    "amqp",
    "amqp_publish",
    "aws_sns_sqs",
    "aws_sns_sqs_publish",
    "http",
    "http_error",
    "http_static",
    "websocket",
    "ws",
    "HttpResponse",
    "HttpException",
    "get_http_response_status",
    "get_http_response_status_sync",
    "schedule",
    "heartbeat",
    "every_second",
    "minutely",
    "hourly",
    "daily",
    "monthly",
    "CLASS_ATTRIBUTE",
]


class TomodachiServiceMeta(type):
    def __new__(
        cls: Type[TomodachiServiceMeta], name: str, bases: Tuple[type, ...], attributedict: Dict
    ) -> TomodachiServiceMeta:
        attributedict[CLASS_ATTRIBUTE] = True
        result = cast(Type["Service"], super().__new__(cls, name, bases, dict(attributedict)))

        if bases and not result.uuid:
            result.uuid = str(uuid_.uuid4())
        if bases and not result.name:
            result.name = "service"

        # Removing the CLASS_ATTRIBUTE for classes that were used as bases for inheritance to other classes
        for base in bases:
            if hasattr(base, CLASS_ATTRIBUTE):
                delattr(base, CLASS_ATTRIBUTE)

        return cast(TomodachiServiceMeta, result)


class Service(metaclass=TomodachiServiceMeta):
    _tomodachi_class_is_service_class: bool = False
    name: str = ""
    uuid: str = ""

    def log(self, *args: Any, **kwargs: Any) -> None:
        __getattr__("_log")(self, *args, **kwargs)

    def log_setup(
        self,
        name: Optional[str] = None,
        level: Optional[Union[str, int]] = None,
        formatter: Any = True,
        filename: Optional[str] = None,
    ) -> Any:
        return __getattr__("_log_setup")(self, name=name, level=level, formatter=formatter, filename=filename)


def service(cls: Type[object]) -> Type[TomodachiServiceMeta]:
    if isinstance(cls, TomodachiServiceMeta):
        return cls

    result = type(cls.__name__, (Service, cls), dict(cls.__dict__))
    return cast(Type[TomodachiServiceMeta], result)


def run(app: Optional[Union[str, List[str], Tuple[str]]] = None, *args: str, **kwargs: Optional[str]) -> None:
    if hasattr(run, "__tomodachi_called") and getattr(run, "__tomodachi_called"):
        return
    setattr(run, "__tomodachi_called", True)

    run_args = []
    if not app:
        import inspect  # noqa  # isort:skip

        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        if not module:
            print("Error: Missing argument for 'tomodachi.run', or it was called from interpreter.")
            setattr(run, "__tomodachi_called", False)
            return
        run_args.append(module.__file__)
    elif isinstance(app, (list, tuple)):
        for arg in app:
            if not isinstance(arg, str):
                continue
            run_args.append(arg)
    elif isinstance(app, str):
        run_args.append(app)

    for arg in args:
        if not isinstance(arg, str):
            continue
        run_args.append(arg)

    for key, value in kwargs.items():
        if not isinstance(key, str):
            continue
        if value is not None and not isinstance(key, str):
            continue
        run_args.append("--{}".format(key))
        if value is not None:
            run_args.append(value)

    from tomodachi.cli import CLI  # noqa  # isort:skip

    CLI().run_command(run_args)
