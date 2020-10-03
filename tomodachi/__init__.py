import inspect
from typing import Any, Dict, Optional

from tomodachi.__version__ import __version__, __version_info__  # noqa

try:
    import tomodachi.helpers.logging
    import tomodachi.helpers.execution_context
    from tomodachi.helpers.execution_context import (
        set_service,
        unset_service,
        clear_services,
        get_service,
        get_instance,
        set_execution_context,
        get_execution_context,
        increase_execution_context_value,
        decrease_execution_context_value
    )
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

__all__ = [
    "service",
    "Service",
    "__version__",
    "__version_info__",
    "decorator",
    "set_service",
    "unset_service",
    "clear_services",
    "set_execution_context",
    "get_execution_context",
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
    "schedule",
    "heartbeat",
    "minutely",
    "hourly",
    "daily",
    "monthly",
]

CLASS_ATTRIBUTE = "TOMODACHI_SERVICE_CLASS"


def service(cls: Any) -> Any:
    setattr(cls, CLASS_ATTRIBUTE, True)
    if not getattr(cls, "log", None):
        cls.log = tomodachi.helpers.logging.log
    if not getattr(cls, "log_setup", None):
        cls.log_setup = tomodachi.helpers.logging.log_setup
    return cls


class Service(object):
    TOMODACHI_SERVICE_CLASS = True
    log = tomodachi.helpers.logging.log
    log_setup = tomodachi.helpers.logging.log_setup
