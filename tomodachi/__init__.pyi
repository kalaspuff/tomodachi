from typing import Any, Optional

from tomodachi.__version__ import __version__ as __version__
from tomodachi.__version__ import __version_info__ as __version_info__
from tomodachi.invoker import decorator
from tomodachi.transport.amqp import amqp as amqp
from tomodachi.transport.amqp import amqp_publish as amqp_publish
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs as aws_sns_sqs
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs_publish as aws_sns_sqs_publish
from tomodachi.transport.http import HttpException as HttpException
from tomodachi.transport.http import Response as HttpResponse
from tomodachi.transport.http import get_http_response_status as get_http_response_status
from tomodachi.transport.http import http as http
from tomodachi.transport.http import http_error as http_error
from tomodachi.transport.http import http_static as http_static
from tomodachi.transport.http import websocket as websocket
from tomodachi.transport.schedule import daily as daily
from tomodachi.transport.schedule import heartbeat as heartbeat
from tomodachi.transport.schedule import hourly as hourly
from tomodachi.transport.schedule import minutely as minutely
from tomodachi.transport.schedule import monthly as monthly
from tomodachi.transport.schedule import schedule as schedule

CLASS_ATTRIBUTE: str = ...

def service(cls: Any) -> Any: ...

class Service:
    TOMODACHI_SERVICE_CLASS: bool = ...
    log: Any = ...
    log_setup: Any = ...

def set_service(name: str, instance: Any) -> None: ...

def get_service(name: Optional[str] = None) -> Any: ...

def get_instance(name: Optional[str] = None) -> Any: ...
