# flake8: noqa
import contextvars
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from tomodachi import cli as cli
from tomodachi import container as container
from tomodachi import discovery as discovery
from tomodachi import envelope as envelope
from tomodachi import helpers as helpers
from tomodachi import importer as importer
from tomodachi import invoker as invoker
from tomodachi import launcher as launcher
from tomodachi import logging as logging
from tomodachi import opentelemetry as opentelemetry
from tomodachi import options as options
from tomodachi import transport as transport
from tomodachi import watcher as watcher
from tomodachi.__version__ import __build_time__ as __build_time__
from tomodachi.__version__ import __version__ as __version__
from tomodachi.__version__ import __version_info__ as __version_info__
from tomodachi.helpers.aiobotocore_connector import ClientConnector as _AiobotocoreClientConnector
from tomodachi.helpers.aiobotocore_connector import connector as _aiobotocore_client_connector
from tomodachi.helpers.execution_context import clear_execution_context as _clear_execution_context
from tomodachi.helpers.execution_context import clear_services as _clear_services
from tomodachi.helpers.execution_context import decrease_execution_context_value as decrease_execution_context_value
from tomodachi.helpers.execution_context import get_execution_context as get_execution_context
from tomodachi.helpers.execution_context import get_instance as get_instance
from tomodachi.helpers.execution_context import get_service as get_service
from tomodachi.helpers.execution_context import get_services as get_services
from tomodachi.helpers.execution_context import increase_execution_context_value as increase_execution_context_value
from tomodachi.helpers.execution_context import set_execution_context as set_execution_context
from tomodachi.helpers.execution_context import set_service as _set_service
from tomodachi.helpers.execution_context import unset_service as _unset_service
from tomodachi.invoker import decorator as decorator
from tomodachi.logging import Logger as Logger
from tomodachi.logging import LoggerProtocol as LoggerProtocol
from tomodachi.logging import get_logger as get_logger
from tomodachi.options import Options as Options
from tomodachi.options import OptionsInterface as OptionsInterface
from tomodachi.transport.amqp import amqp as amqp
from tomodachi.transport.amqp import amqp_publish as amqp_publish
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs as aws_sns_sqs
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs_publish as aws_sns_sqs_publish
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs_send_message as aws_sns_sqs_send_message
from tomodachi.transport.aws_sns_sqs import awssnssqs as awssnssqs
from tomodachi.transport.aws_sns_sqs import awssnssqs_publish as awssnssqs_publish
from tomodachi.transport.aws_sns_sqs import awssnssqs_send_message as awssnssqs_send_message
from tomodachi.transport.aws_sns_sqs import sns_publish as sns_publish
from tomodachi.transport.aws_sns_sqs import sqs_send_message as sqs_send_message
from tomodachi.transport.http import HttpException as HttpException
from tomodachi.transport.http import Response as _HttpResponse
from tomodachi.transport.http import get_forwarded_remote_ip as get_forwarded_remote_ip
from tomodachi.transport.http import get_http_response_status as get_http_response_status
from tomodachi.transport.http import get_http_response_status_sync as get_http_response_status_sync
from tomodachi.transport.http import http as http
from tomodachi.transport.http import http_error as http_error
from tomodachi.transport.http import http_static as http_static
from tomodachi.transport.http import websocket as websocket
from tomodachi.transport.http import ws as ws
from tomodachi.transport.schedule import daily as daily
from tomodachi.transport.schedule import every_second as every_second
from tomodachi.transport.schedule import heartbeat as heartbeat
from tomodachi.transport.schedule import hourly as hourly
from tomodachi.transport.schedule import minutely as minutely
from tomodachi.transport.schedule import monthly as monthly
from tomodachi.transport.schedule import schedule as schedule

AiobotocoreClientConnector = _AiobotocoreClientConnector
aiobotocore_client_connector = _aiobotocore_client_connector
HttpResponse = _HttpResponse

__author__: str = ...
__email__: str = ...

CLASS_ATTRIBUTE: str = ...
TOMODACHI_CLASSES: List[Type] = ...
DEFAULT_SERVICE_EXIT_CODE: int = ...
SERVICE_EXIT_CODE: int = ...

def get_contextvar(key: str) -> contextvars.ContextVar: ...
def context(key: str) -> Any: ...

class TomodachiServiceMeta(type):
    def __new__(
        cls: Type[TomodachiServiceMeta], name: str, bases: Tuple[type, ...], attributedict: Dict
    ) -> TomodachiServiceMeta: ...

class Service(metaclass=TomodachiServiceMeta):
    _tomodachi_class_is_service_class: bool = ...
    name: str = ...
    uuid: str = ...
    options: Options
    logger: LoggerProtocol
    log: Callable = ...

def service(cls: Type[object]) -> Type[TomodachiServiceMeta]: ...
def exit(exit_code: Optional[int] = None) -> None: ...
def run(app: Optional[Union[str, List[str], Tuple[str]]] = None, *args: str, **kwargs: Optional[str]) -> None: ...
