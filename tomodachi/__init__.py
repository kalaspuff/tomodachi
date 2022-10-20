from __future__ import annotations

import contextvars
import importlib
import uuid as uuid_
import warnings
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast

from tomodachi.__version__ import __version__, __version_info__
from tomodachi.options import Options, OptionsInterface

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

DEFAULT_SERVICE_EXIT_CODE: int = 0
SERVICE_EXIT_CODE: int = 0

__context: Dict[str, contextvars.ContextVar] = {}

__doc__ = """
A Python library for quickly building microservices using asyncio. Built-in support for HTTP, websockets, internal task scheduling, RabbitMQ / AMQP and AWS SNS+SQS. It is lightweight and builds on top of libraries such as aiohttp, aiobotocore, aioamqp, etc. - extendable to be used with different options of infrastructure choices.
"""


def get_contextvar(key: str) -> contextvars.ContextVar:
    if key not in __context:
        __context[key] = contextvars.ContextVar(f"tomodachi.{key}", default=None)
    return __context[key]


def context(key: str) -> Any:
    if key not in __context:
        return None
    return __context[key].get()


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
    "__doc__",
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
    "exit",
    "context",
    "AiobotocoreClientConnector",
    "aiobotocore_client_connector",
    "Options",
    "OptionsInterface",
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
    "SERVICE_EXIT_CODE",
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

        if bases and (not hasattr(result, "options") or not result.options):
            result.options = Options()
        elif bases and result.options and not isinstance(result.options, Options):
            if not isinstance(result.options, dict):  # type: ignore
                raise ValueError("Invalid value for 'options' attribute")
            warnings.warn(
                "Assigning a dict or dict-like mapping to 'service.options' is deprecated. Use the 'tomodachi.Options' class instead.",
                DeprecationWarning,
            )
            result.options = Options(**result.options)

        # Removing the CLASS_ATTRIBUTE for classes that were used as bases for inheritance to other classes
        for base in bases:
            if hasattr(base, CLASS_ATTRIBUTE):
                delattr(base, CLASS_ATTRIBUTE)

        return cast(TomodachiServiceMeta, result)


class Service(metaclass=TomodachiServiceMeta):
    """
    Base class for all tomodachi services.

    Attributes:
        name: Service name used to distinguish between different services.
        uuid: An identifier set for the current thread of the service. If not set, a random UUID will be generated on start.
        options: Options for the service. See the `tomodachi.Options` class for more information.
    """

    name: str = ""
    uuid: str = ""
    options: Options

    _tomodachi_class_is_service_class: bool = False

    def __getattr__(self, item: str) -> Any:
        """
        Get an attribute from the service instance.

        Args:
            item: Attribute name to look up.
        """

        if item == "log":
            warnings.warn(
                "Calling the 'service.log' function is deprecated. A structured logger should preferably be used for logging.",
                DeprecationWarning,
            )
            fallback_func = __getattr__("_log").__get__(self)
            super().__setattr__(item, fallback_func)
            return fallback_func

        if item == "log_setup":
            warnings.warn(
                "Calling the 'service.log_setup' function is deprecated. A structured logger should preferably be used for logging.",
                DeprecationWarning,
            )
            fallback_func = __getattr__("_log_setup").__get__(self)
            super().__setattr__(item, fallback_func)
            return fallback_func

        return object.__getattribute__(self, item)

    def __setattr__(self, item: str, value: Any) -> None:
        """
        Assigns a value to a service attribute.

        Args:
            item: Attribute name to use for assignment.
            value: Value to assign to the attribute.
        """

        if item == "options" and not isinstance(value, Options):
            if not isinstance(value, dict):
                raise ValueError("Invalid value for 'options' attribute")
            warnings.warn(
                "Assigning a dict or dict-like mapping to 'service.options' is deprecated. Use the 'tomodachi.Options' class instead.",
                DeprecationWarning,
            )
            value = Options(**value)

        super().__setattr__(item, value)


def service(cls: Type[object]) -> Type[TomodachiServiceMeta]:
    warnings.warn(
        "The service class decorator '@tomodachi.service' is deprecated. Instead inherit the 'tomodachi.Service' class.",
        DeprecationWarning,
    )

    if isinstance(cls, TomodachiServiceMeta):
        return cls

    result = type(cls.__name__, (Service, cls), dict(cls.__dict__))
    return cast(Type[TomodachiServiceMeta], result)


def exit(exit_code: Optional[int] = None) -> None:
    """
    Initiate graceful termination of the currently running service.

    Args:
        exit_code: Exit code to use when exiting the service. If not set, the default exit code will be used.
    """
    import logging  # noqa # isort:skip
    import sys  # noqa # isort:skip
    from tomodachi.launcher import ServiceLauncher  # noqa  # isort:skip

    exit_code = exit_code if exit_code is not None else SERVICE_EXIT_CODE
    logging.getLogger("system").warning(f"Termination initiatied via tomodachi.exit call [exit_code: {exit_code}]")
    ServiceLauncher.restart_services = False
    setattr(sys.modules[__name__], "SERVICE_EXIT_CODE", exit_code)
    ServiceLauncher.stop_services()


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
