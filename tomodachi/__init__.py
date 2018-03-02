from typing import Any
from tomodachi.__version__ import __version__, __version_info__  # noqa
try:
    import tomodachi.helpers.logging
    from tomodachi.transport.amqp import (amqp,
                                          amqp_publish)
    from tomodachi.transport.aws_sns_sqs import (aws_sns_sqs,
                                                 aws_sns_sqs_publish)
    from tomodachi.transport.http import (http,
                                          http_error,
                                          http_static,
                                          websocket,
                                          HttpException,
                                          Response as HttpResponse)
    from tomodachi.transport.schedule import (schedule,
                                              heartbeat,
                                              minutely,
                                              hourly,
                                              daily,
                                              monthly)
except Exception:
    pass

__all__ = ['service', '__version__', '__version_info__',
           'amqp', 'amqp_publish',
           'aws_sns_sqs', 'aws_sns_sqs_publish',
           'http', 'http_error', 'http_static', 'websocket', 'HttpResponse', 'HttpException',
           'schedule', 'heartbeat', 'minutely', 'hourly', 'daily', 'monthly']

CLASS_ATTRIBUTE = 'TOMODACHI_SERVICE_CLASS'


def service(cls: Any) -> Any:
    setattr(cls, CLASS_ATTRIBUTE, True)
    if not getattr(cls, 'log', None):
        cls.log = tomodachi.helpers.logging.log
    if not getattr(cls, 'log_setup', None):
        cls.log_setup = tomodachi.helpers.logging.log_setup
    return cls
