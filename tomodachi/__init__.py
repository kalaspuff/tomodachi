from typing import Any, Optional
import inspect
from tomodachi.__version__ import __version__, __version_info__  # noqa
try:
    import tomodachi.helpers.logging
    from tomodachi.invoker import decorator
except Exception:  # pragma: no cover
    pass

try:
    from tomodachi.transport.amqp import (amqp,
                                          amqp_publish)
except Exception:  # pragma: no cover
    pass
try:
    from tomodachi.transport.aws_sns_sqs import (aws_sns_sqs,
                                                 aws_sns_sqs_publish)
except Exception:  # pragma: no cover
    pass
try:
    from tomodachi.transport.http import (http,
                                          http_error,
                                          http_static,
                                          websocket,
                                          ws,
                                          get_http_response_status,
                                          HttpException,
                                          Response as HttpResponse)
except Exception:  # pragma: no cover
    pass
try:
    from tomodachi.transport.schedule import (schedule,
                                              heartbeat,
                                              minutely,
                                              hourly,
                                              daily,
                                              monthly)
except Exception:  # pragma: no cover
    pass

__all__ = ['service', 'Service', '__version__', '__version_info__',
           'decorator', 'set_service', 'get_service', 'get_instance',
           'amqp', 'amqp_publish',
           'aws_sns_sqs', 'aws_sns_sqs_publish',
           'http', 'http_error', 'http_static', 'websocket', 'ws', 'HttpResponse', 'HttpException',
           'schedule', 'heartbeat', 'minutely', 'hourly', 'daily', 'monthly']

CLASS_ATTRIBUTE = 'TOMODACHI_SERVICE_CLASS'
_services = {}
_current_service = {}


def service(cls: Any) -> Any:
    setattr(cls, CLASS_ATTRIBUTE, True)
    if not getattr(cls, 'log', None):
        cls.log = tomodachi.helpers.logging.log
    if not getattr(cls, 'log_setup', None):
        cls.log_setup = tomodachi.helpers.logging.log_setup
    return cls


class Service(object):
    TOMODACHI_SERVICE_CLASS = True
    log = tomodachi.helpers.logging.log
    log_setup = tomodachi.helpers.logging.log_setup


def set_service(name: str, instance: Any) -> None:
    _services[name] = instance
    _current_service[0] = instance


def get_service(name: Optional[str] = None) -> Any:
    if name is None:
        if _current_service and len(_current_service):
            return _current_service[0]

        for k, v in _services.items():
            name = k
            break

    return _services.get(name)


def get_instance(name: Optional[str] = None) -> Any:
    # alias for tomodachi.get_service()
    return get_service(name)
