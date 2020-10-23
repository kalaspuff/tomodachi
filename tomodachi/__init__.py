from __future__ import annotations

import inspect  # noqa
import uuid
from typing import Callable, Dict, Tuple, Type, cast

from tomodachi.__version__ import __version__, __version_info__  # noqa

try:
    import tomodachi.helpers.execution_context
    import tomodachi.helpers.logging
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

try:
    from tomodachi.transport.amqp import amqp, amqp_publish
except Exception:  # pragma: no cover
    pass
try:
    from tomodachi.transport.aws_sns_sqs import aws_sns_sqs, aws_sns_sqs_publish
except Exception:  # pragma: no cover
    pass
try:
    from tomodachi.transport.http import HttpException
    from tomodachi.transport.http import Response as HttpResponse
    from tomodachi.transport.http import get_http_response_status, http, http_error, http_static, websocket, ws
except Exception:  # pragma: no cover
    pass
try:
    from tomodachi.transport.schedule import daily, heartbeat, hourly, minutely, monthly, schedule
except Exception:  # pragma: no cover
    pass

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
    "schedule",
    "heartbeat",
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
            result.uuid = str(uuid.uuid4())
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
    log: Callable = tomodachi.helpers.logging.log
    log_setup: Callable = tomodachi.helpers.logging.log_setup


def service(cls: Type[object]) -> Type[TomodachiServiceMeta]:
    if isinstance(cls, TomodachiServiceMeta):
        return cls

    result = type(cls.__name__, (cls, Service), dict(cls.__dict__))
    return result
