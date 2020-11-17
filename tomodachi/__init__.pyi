from typing import Any, Callable, Dict, Tuple, Type

from tomodachi.__version__ import __version_info__ as __version_info__
from tomodachi.helpers.execution_context import clear_execution_context as _clear_execution_context
from tomodachi.helpers.execution_context import clear_services as _clear_services
from tomodachi.helpers.execution_context import decrease_execution_context_value as decrease_execution_context_value
from tomodachi.helpers.execution_context import get_execution_context as get_execution_context
from tomodachi.helpers.execution_context import get_instance as get_instance
from tomodachi.helpers.execution_context import get_service as get_service
from tomodachi.helpers.execution_context import increase_execution_context_value as increase_execution_context_value
from tomodachi.helpers.execution_context import set_execution_context as set_execution_context
from tomodachi.helpers.execution_context import set_service as _set_service
from tomodachi.helpers.execution_context import unset_service as _unset_service
from tomodachi.invoker import decorator as decorator
from tomodachi.transport.amqp import amqp as amqp
from tomodachi.transport.amqp import amqp_publish as amqp_publish
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs as aws_sns_sqs
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs_publish as aws_sns_sqs_publish
from tomodachi.transport.http import HttpException as HttpException
from tomodachi.transport.http import Response as HttpResponse
from tomodachi.transport.http import get_http_response_status as get_http_response_status
from tomodachi.transport.http import get_http_response_status_sync as get_http_response_status_sync
from tomodachi.transport.http import http as http
from tomodachi.transport.http import http_error as http_error
from tomodachi.transport.http import http_static as http_static
from tomodachi.transport.http import websocket as websocket
from tomodachi.transport.http import ws as ws
from tomodachi.transport.schedule import daily as daily
from tomodachi.transport.schedule import heartbeat as heartbeat
from tomodachi.transport.schedule import hourly as hourly
from tomodachi.transport.schedule import minutely as minutely
from tomodachi.transport.schedule import monthly as monthly
from tomodachi.transport.schedule import schedule as schedule

def __getattr__(name: str) -> Any: ...

__author__: str = ...
__email__: str = ...

CLASS_ATTRIBUTE: str = ...

class TomodachiServiceMeta(type):
    def __new__(
        cls: Type[TomodachiServiceMeta], name: str, bases: Tuple[type, ...], attributedict: Dict
    ) -> TomodachiServiceMeta: ...

class Service(metaclass=TomodachiServiceMeta):
    _tomodachi_class_is_service_class: bool = ...
    name: str = ...
    uuid: str = ...
    log: Callable = ...
    log_setup: Callable = ...

def service(cls: Type[object]) -> Type[TomodachiServiceMeta]: ...
