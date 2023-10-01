from __future__ import annotations

import asyncio
import base64
import binascii
import copy
import decimal
import functools
import hashlib
import inspect
import json
import re
import string
import time
import uuid
import warnings
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Literal,
    Mapping,
    Match,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypedDict,
    Union,
    cast,
    overload,
)

import aiobotocore
import aiohttp
import aiohttp.client_exceptions
import botocore
import botocore.exceptions
from botocore.parsers import ResponseParserError

from tomodachi import get_contextvar, logging
from tomodachi._exception import limit_exception_traceback
from tomodachi.helpers.aiobotocore_connector import ClientConnector
from tomodachi.helpers.execution_context import (
    decrease_execution_context_value,
    get_execution_context,
    increase_execution_context_value,
    set_execution_context,
)
from tomodachi.helpers.middleware import execute_middlewares
from tomodachi.invoker import Invoker
from tomodachi.options import Options

DRAIN_MESSAGE_PAYLOAD = "__TOMODACHI_DRAIN__cdab4416-1727-4603-87c9-0ff8dddf1f22__"
MESSAGE_ENVELOPE_DEFAULT = "e6fb6007-cf15-4cfd-af2e-1d1683374e70"
MESSAGE_PROTOCOL_DEFAULT = MESSAGE_ENVELOPE_DEFAULT  # deprecated
MESSAGE_TOPIC_PREFIX = "09698c75-832b-470f-8e05-96d2dd8c4853"
MESSAGE_TOPIC_ATTRIBUTES = "dc6c667f-4c22-4a63-85f6-3ea0c7e2db49"
FILTER_POLICY_DEFAULT = "7e68632f-3b39-4293-b5a9-16644cf857a5"
DEAD_LETTER_QUEUE_DEFAULT = "22ebae61-1aab-4b2e-840f-008da1f45472"
DLQ_MESSAGE_RETENTION_PERIOD_DEFAULT = 1209600  # 14 days
MESSAGE_RETENTION_PERIOD_DEFAULT = "b3eb5107-ca13-2cfb-ca1e-1a14b5313e91"
VISIBILITY_TIMEOUT_DEFAULT = -1
MAX_RECEIVE_COUNT_DEFAULT = -1
MAX_NUMBER_OF_CONSUMED_MESSAGES = 10

SET_CONTEXTVAR_VALUES = False

AnythingButFilterPolicyValueType = Union[str, int, float, List[str], List[int], List[float], List[Union[int, float]]]
AnythingButFilterPolicyDict = TypedDict(
    "AnythingButFilterPolicyDict",
    {
        "anything-but": AnythingButFilterPolicyValueType,
    },
    total=False,
)

NumericFilterPolicyValueType = Sequence[Union[int, float, Literal["<", "<=", "=", ">=", ">"]]]
NumericFilterPolicyDict = TypedDict(
    "NumericFilterPolicyDict",
    {
        "numeric": NumericFilterPolicyValueType,
    },
    total=False,
)

PrefixFilterPolicyDict = TypedDict(
    "PrefixFilterPolicyDict",
    {
        "prefix": str,
    },
    total=False,
)

ExistsFilterPolicyDict = TypedDict(
    "ExistsFilterPolicyDict",
    {
        "exists": bool,
    },
    total=False,
)

FilterPolicyDictValueType = Sequence[
    Optional[
        Union[
            str,
            int,
            float,
            AnythingButFilterPolicyDict,
            NumericFilterPolicyDict,
            PrefixFilterPolicyDict,
            ExistsFilterPolicyDict,
        ]
    ]
]

FilterPolicyDictType = Mapping[str, FilterPolicyDictValueType]

MessageAttributesType = Dict[
    str, Optional[Union[str, bytes, int, float, bool, List[Optional[Union[str, int, float, bool, object]]]]]
]

connector = ClientConnector()


class AWSSNSSQSException(Exception):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._log_level = kwargs.get("log_level") if kwargs and kwargs.get("log_level") else "INFO"


class AWSSNSSQSConnectionException(AWSSNSSQSException):
    pass


class AWSSNSSQSInternalServiceError(AWSSNSSQSException):
    pass


class AWSSNSSQSInternalServiceErrorException(AWSSNSSQSInternalServiceError):
    pass


class AWSSNSSQSInternalServiceException(AWSSNSSQSInternalServiceError):
    pass


class AWSSNSSQSTransport(Invoker):
    topics: Optional[Dict[str, str]] = None
    close_waiter: Optional[asyncio.Future] = None

    @overload
    @classmethod
    async def publish(
        cls,
        service: Any,
        data: Any,
        topic: str,
        wait: Literal[True] = True,
        *,
        message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
        message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
        topic_prefix: Optional[str] = MESSAGE_TOPIC_PREFIX,
        message_attributes: Optional[Dict[str, Any]] = None,
        topic_attributes: Optional[Union[str, Dict[str, Union[bool, str]]]] = MESSAGE_TOPIC_ATTRIBUTES,
        overwrite_topic_attributes: bool = False,
        group_id: Optional[str] = None,
        deduplication_id: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        ...

    @overload
    @classmethod
    async def publish(
        cls,
        service: Any,
        data: Any,
        topic: str,
        wait: Literal[False],
        *,
        message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
        message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
        topic_prefix: Optional[str] = MESSAGE_TOPIC_PREFIX,
        message_attributes: Optional[Dict[str, Any]] = None,
        topic_attributes: Optional[Union[str, Dict[str, Union[bool, str]]]] = MESSAGE_TOPIC_ATTRIBUTES,
        overwrite_topic_attributes: bool = False,
        group_id: Optional[str] = None,
        deduplication_id: Optional[str] = None,
        **kwargs: Any,
    ) -> asyncio.Task[str]:
        ...

    @classmethod
    async def publish(
        cls,
        service: Any,
        data: Any,
        topic: str,
        wait: bool = True,
        *,
        message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
        message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
        topic_prefix: Optional[str] = MESSAGE_TOPIC_PREFIX,
        message_attributes: Optional[Dict[str, Any]] = None,
        topic_attributes: Optional[Union[str, Dict[str, Union[bool, str]]]] = MESSAGE_TOPIC_ATTRIBUTES,
        overwrite_topic_attributes: bool = False,
        group_id: Optional[str] = None,
        deduplication_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Union[str, asyncio.Task[str]]:
        logging.getLogger("tomodachi.awssnssqs").new(logger="tomodachi.awssnssqs")

        if message_envelope == MESSAGE_ENVELOPE_DEFAULT and message_protocol != MESSAGE_ENVELOPE_DEFAULT:
            # Fallback if deprecated message_protocol keyword is used
            message_envelope = message_protocol

            warnings.warn(
                "Using the 'message_protocol' keyword argument is deprecated. Use 'message_envelope' instead.",
                DeprecationWarning,
            )

        message_envelope = (
            getattr(service, "message_envelope", getattr(service, "message_protocol", None))
            if message_envelope == MESSAGE_ENVELOPE_DEFAULT
            else message_envelope
        )

        if getattr(service, "message_protocol", None):
            warnings.warn(
                "Using the 'message_protocol' attribute on a service is deprecated. Use 'message_envelope' instead.",
                DeprecationWarning,
            )

        if not message_attributes:
            message_attributes = {}
        else:
            message_attributes = copy.deepcopy(message_attributes)

        payload = data
        if message_envelope:
            build_message_func = getattr(message_envelope, "build_message", None)
            if build_message_func:
                payload = await asyncio.create_task(
                    build_message_func(service, topic, data, message_attributes=message_attributes, **kwargs)
                )

        topic_arn: str
        if cls.topics and cls.topics.get(topic):
            topic_arn = cls.topics.get(topic, "")
        else:
            topic_arn = ""

        if not topic_arn or not isinstance(topic_arn, str):
            topic_arn = await asyncio.create_task(
                cls.create_topic(
                    topic,
                    service.context,
                    topic_prefix,
                    fifo=group_id is not None,
                    attributes=topic_attributes,
                    overwrite_attributes=overwrite_topic_attributes,
                )
            )

        async def _publish_message() -> str:
            logging.getLogger("tomodachi.awssnssqs").bind(topic=topic)
            return await cls._publish_message(
                topic_arn,
                payload,
                cast(Dict, message_attributes),
                service.context,
                group_id=group_id,
                deduplication_id=deduplication_id,
                service=service,
            )

        if wait:
            return await asyncio.create_task(_publish_message())
        else:
            return asyncio.create_task(_publish_message())

    @classmethod
    def get_topic_name(
        cls,
        topic: str,
        context: Dict,
        fifo: bool,
        topic_prefix: Optional[str] = MESSAGE_TOPIC_PREFIX,
    ) -> str:
        topic_prefix = (
            cls.options(context).aws_sns_sqs.topic_prefix
            if topic_prefix == MESSAGE_TOPIC_PREFIX
            else (topic_prefix or "")
        )
        if topic_prefix:
            topic = "{}{}".format(topic_prefix, topic)
        if fifo and not topic.endswith(".fifo"):
            topic += ".fifo"
        return topic

    @classmethod
    def get_topic_name_without_prefix(
        cls, topic: str, context: Dict, topic_prefix: Optional[str] = MESSAGE_TOPIC_PREFIX
    ) -> str:
        topic_prefix = (
            cls.options(context).aws_sns_sqs.topic_prefix
            if topic_prefix == MESSAGE_TOPIC_PREFIX
            else (topic_prefix or "")
        )
        if topic_prefix:
            if topic.startswith(topic_prefix):
                prefix_length = len(topic_prefix)
                return topic[prefix_length:]
        return topic

    @classmethod
    def get_topic_from_arn(cls, topic: str) -> str:
        return topic.rsplit(":")[-1]

    @classmethod
    def decode_topic(cls, encoded_topic: str) -> str:
        def decode(match: Match) -> str:
            return binascii.unhexlify(match.group(1).encode("utf-8")).decode("utf-8")

        return re.sub(r"___([a-f0-9]{2}|[a-f0-9]{4}|[a-f0-9]{6}|[a-f0-9]{8})_", decode, encoded_topic)

    @classmethod
    def encode_topic(cls, topic: str) -> str:
        def encode(match: Match) -> str:
            return "___" + binascii.hexlify(match.group(1).encode("utf-8")).decode("utf-8") + "_"

        topic = re.sub(r"(?!\.fifo$)([^a-zA-Z0-9_*#-])", encode, topic)
        return topic

    @classmethod
    def get_queue_name(
        cls,
        topic: str,
        func_name: str,
        _uuid: str,
        competing_consumer: Optional[bool],
        context: Dict,
        fifo: bool,
    ) -> str:
        if not competing_consumer:
            queue_name = hashlib.sha256("{}{}{}".format(topic, func_name, _uuid).encode("utf-8")).hexdigest()
        else:
            queue_name = hashlib.sha256(topic.encode("utf-8")).hexdigest()

        queue_name_prefix: Optional[str] = cls.options(context).aws_sns_sqs.queue_name_prefix
        if queue_name_prefix:
            queue_name = "{}{}".format(queue_name_prefix, queue_name)

        if fifo and not queue_name.endswith(".fifo"):
            queue_name += ".fifo"
        return queue_name

    @classmethod
    def prefix_queue_name(cls, queue_name: str, context: Dict) -> str:
        queue_name_prefix: Optional[str] = cls.options(context).aws_sns_sqs.queue_name_prefix
        if queue_name_prefix:
            return "{}{}".format(queue_name_prefix, queue_name)
        return queue_name

    @classmethod
    def get_queue_name_without_prefix(cls, queue_name: str, context: Dict) -> str:
        queue_name_prefix: Optional[str] = cls.options(context).aws_sns_sqs.queue_name_prefix
        if queue_name_prefix:
            if queue_name.startswith(queue_name_prefix):
                prefix_length = len(queue_name_prefix)
                return queue_name[prefix_length:]
        return queue_name

    @classmethod
    def get_queue_name_from_queue_url(cls, queue_url: str) -> str:
        return queue_url.rsplit("/")[-1]

    @classmethod
    def validate_queue_name(cls, queue_name: str) -> None:
        if len(queue_name) > 80:
            raise Exception("Queue name ({}) is too long.".format(queue_name))
        if not set(queue_name.rstrip(".fifo")) <= set(string.digits + string.ascii_letters + "-" + "_"):
            raise Exception(
                "Queue name ({}) may only contain alphanumeric characters, hyphens (-), and underscores (_).".format(
                    queue_name
                )
            )

    @classmethod
    def validate_topic_name(cls, topic: str) -> None:
        if len(topic) > 256:
            raise Exception("Topic name ({}) is too long.".format(topic))
        if not set(topic.rstrip(".fifo")) <= set(string.digits + string.ascii_letters + "-" + "_"):
            raise Exception(
                "Topic name ({}) may only contain alphanumeric characters, hyphens (-), and underscores (_).".format(
                    topic
                )
            )

    @classmethod
    async def subscribe_handler(
        cls,
        obj: Any,
        context: Dict,
        func: Any,
        topic: Optional[str] = None,
        callback_kwargs: Optional[Union[List, Set, Tuple]] = None,
        competing: Optional[bool] = None,
        queue_name: Optional[str] = None,
        *,
        message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
        message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
        filter_policy: Optional[Union[str, FilterPolicyDictType]] = FILTER_POLICY_DEFAULT,
        visibility_timeout: Optional[int] = VISIBILITY_TIMEOUT_DEFAULT,
        dead_letter_queue_name: Optional[str] = DEAD_LETTER_QUEUE_DEFAULT,
        max_receive_count: Optional[int] = MAX_RECEIVE_COUNT_DEFAULT,
        fifo: bool = False,
        max_number_of_consumed_messages: Optional[int] = MAX_NUMBER_OF_CONSUMED_MESSAGES,
        **kwargs: Any,
    ) -> Any:
        parser_kwargs = kwargs

        if message_envelope == MESSAGE_ENVELOPE_DEFAULT and message_protocol != MESSAGE_ENVELOPE_DEFAULT:
            # Fallback if deprecated message_protocol keyword is used
            message_envelope = message_protocol

            warnings.warn(
                "Using the 'message_protocol' keyword argument is deprecated. Use 'message_envelope' instead.",
                DeprecationWarning,
            )

        message_envelope = (
            context.get("message_envelope", context.get("message_protocol"))
            if message_envelope == MESSAGE_ENVELOPE_DEFAULT
            else message_envelope
        )

        if context.get("message_protocol"):
            warnings.warn(
                "Using the 'message_protocol' attribute on a service is deprecated. Use 'message_envelope' instead.",
                DeprecationWarning,
            )

        # Validate the parser kwargs if there is a validation function in the envelope
        if message_envelope:
            envelope_kwargs_validation_func = getattr(message_envelope, "validate", None)
            if envelope_kwargs_validation_func:
                envelope_kwargs_validation_func(**parser_kwargs)

        _callback_kwargs: Any = callback_kwargs
        values = inspect.getfullargspec(func)
        if not _callback_kwargs:
            _callback_kwargs = (
                {
                    k: values.defaults[i - len(values.args) + 1]
                    if values.defaults and i >= len(values.args) - len(values.defaults) - 1
                    else None
                    for i, k in enumerate(values.args[1:])
                }
                if values.args and len(values.args) > 1
                else {}
            )
        else:
            _callback_kwargs = {k: None for k in _callback_kwargs if k != "self"}
        original_kwargs = {k: v for k, v in _callback_kwargs.items()}
        args_set = (set(values.args[1:]) | set(values.kwonlyargs) | set(callback_kwargs or [])) - set(["self"])

        async def handler(
            payload: Optional[str],
            receipt_handle: Optional[str] = None,
            queue_url: Optional[str] = None,
            message_topic: str = "",
            message_attributes: Optional[Dict] = None,
            approximate_receive_count: Optional[int] = None,
            sns_message_id: Optional[str] = None,
            sqs_message_id: Optional[str] = None,
            message_timestamp: Optional[str] = None,
            message_deduplication_id: Optional[str] = None,
            message_group_id: Optional[str] = None,
        ) -> Any:
            logging.bind_logger(logging.getLogger("tomodachi.awssnssqs").new(logger="tomodachi.awssnssqs"))

            if not payload or payload == DRAIN_MESSAGE_PAYLOAD:
                try:
                    await cls.delete_message(receipt_handle, queue_url, context)
                except (Exception, asyncio.CancelledError):
                    pass
                return

            kwargs = dict(original_kwargs)

            if SET_CONTEXTVAR_VALUES:
                # experimental featureset - set values to contextvars
                get_contextvar("aws_sns_sqs.receipt_handle").set(receipt_handle)
                get_contextvar("aws_sns_sqs.queue_url").set(queue_url)
                get_contextvar("aws_sns_sqs.approximate_receive_count").set(approximate_receive_count)

            message: Optional[Union[bool, str, Dict]] = payload
            message_attributes_values: MessageAttributesType = (
                cls.transform_message_attributes_from_response(message_attributes) if message_attributes else {}
            )
            message_uuid = None
            message_key = None

            if message_envelope:
                try:
                    parse_message_func = getattr(message_envelope, "parse_message", None)
                    if parse_message_func:
                        if len(parser_kwargs):
                            message, message_uuid, timestamp = await asyncio.create_task(
                                parse_message_func(
                                    payload, message_attributes=message_attributes_values, **parser_kwargs
                                )
                            )
                        else:
                            message, message_uuid, timestamp = await asyncio.create_task(parse_message_func(payload))
                    if message is not False and message_uuid:
                        if not context.get("_aws_sns_sqs_received_messages"):
                            context["_aws_sns_sqs_received_messages"] = {}
                        message_key = "{}:{}".format(message_uuid, func.__name__)
                        if context["_aws_sns_sqs_received_messages"].get(message_key):
                            return
                        context["_aws_sns_sqs_received_messages"][message_key] = time.time()
                        _received_messages = context["_aws_sns_sqs_received_messages"]
                        if (
                            _received_messages
                            and isinstance(_received_messages, dict)
                            and len(_received_messages) > 100000
                        ):
                            context["_aws_sns_sqs_received_messages"] = {
                                k: v
                                for k, v in context["_aws_sns_sqs_received_messages"].items()
                                if v > time.time() - 60
                            }

                    if args_set:
                        if isinstance(message, dict):
                            for k, v in message.items():
                                if k in args_set:
                                    kwargs[k] = v
                        if "message" in args_set and (not isinstance(message, dict) or "message" not in message):
                            kwargs["message"] = message
                        if "topic" in args_set and (not isinstance(message, dict) or "topic" not in message):
                            kwargs["topic"] = topic
                        if "message_uuid" in args_set and (
                            not isinstance(message, dict) or "message_uuid" not in message
                        ):
                            kwargs["message_uuid"] = message_uuid
                        if "receipt_handle" in args_set and (
                            not isinstance(message, dict) or "receipt_handle" not in message
                        ):
                            kwargs["receipt_handle"] = receipt_handle
                        if "queue_url" in args_set and (not isinstance(message, dict) or "queue_url" not in message):
                            kwargs["queue_url"] = queue_url
                        if "message_attributes" in args_set and (
                            not isinstance(message, dict) or "message_attributes" not in message
                        ):
                            kwargs["message_attributes"] = message_attributes_values
                        if "approximate_receive_count" in args_set and (
                            not isinstance(message, dict) or "approximate_receive_count" not in message
                        ):
                            kwargs["approximate_receive_count"] = approximate_receive_count
                        if "sns_message_id" in args_set and (
                            not isinstance(message, dict) or "sns_message_id" not in message
                        ):
                            kwargs["sns_message_id"] = sns_message_id
                        if "sqs_message_id" in args_set and (
                            not isinstance(message, dict) or "sqs_message_id" not in message
                        ):
                            kwargs["sqs_message_id"] = sqs_message_id
                        if "message_timestamp" in args_set and (
                            not isinstance(message, dict) or "message_timestamp" not in message
                        ):
                            kwargs["message_timestamp"] = message_timestamp
                        if "message_deduplication_id" in args_set and (
                            not isinstance(message, dict) or "message_deduplication_id" not in message
                        ):
                            kwargs["message_deduplication_id"] = message_deduplication_id
                        if "message_group_id" in args_set and (
                            not isinstance(message, dict) or "message_group_id" not in message
                        ):
                            kwargs["message_group_id"] = message_group_id

                except (Exception, asyncio.CancelledError, BaseException) as e:
                    limit_exception_traceback(e, ("tomodachi.transport.aws_sns_sqs",))
                    logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))
                    if message is not False and not message_uuid:
                        await cls.delete_message(receipt_handle, queue_url, context)
                    elif message is False and message_uuid:
                        pass  # incompatible envelope, should probably delete if old message
                    elif message is False:
                        await cls.delete_message(receipt_handle, queue_url, context)
                    return
            else:
                if args_set:
                    if "message" in args_set:
                        kwargs["message"] = message
                    if "topic" in args_set:
                        kwargs["topic"] = topic
                    if "message_uuid" in args_set:
                        kwargs["message_uuid"] = message_uuid
                    if "receipt_handle" in args_set:
                        kwargs["receipt_handle"] = receipt_handle
                    if "queue_url" in args_set:
                        kwargs["queue_url"] = queue_url
                    if "message_attributes" in args_set:
                        kwargs["message_attributes"] = message_attributes_values
                    if "approximate_receive_count" in args_set:
                        kwargs["approximate_receive_count"] = approximate_receive_count
                    if "sns_message_id" in args_set:
                        kwargs["sns_message_id"] = sns_message_id
                    if "sqs_message_id" in args_set:
                        kwargs["sqs_message_id"] = sqs_message_id
                    if "message_timestamp" in args_set:
                        kwargs["message_timestamp"] = message_timestamp
                    if "message_deduplication_id" in args_set:
                        kwargs["message_deduplication_id"] = message_deduplication_id
                    if "message_group_id" in args_set:
                        kwargs["message_group_id"] = message_group_id

                if len(values.args[1:]) and values.args[1] in kwargs:
                    del kwargs[values.args[1]]

            @functools.wraps(func)
            async def routine_func(*a: Any, **kw: Any) -> Any:
                logging.bind_logger(
                    logging.getLogger("tomodachi.awssnssqs.handler").bind(
                        handler=func.__name__, type="tomodachi.awssnssqs"
                    )
                )
                get_contextvar("service.logger").set("tomodachi.awssnssqs.handler")

                kw_values = {k: v for k, v in {**kwargs, **kw}.items() if values.varkw or k in args_set}
                args_values = [
                    kw_values.pop(key) if key in kw_values else a[i + 1]
                    for i, key in enumerate(values.args[1 : len(a) + 1])
                ]
                if values.varargs and not values.defaults and len(a) > len(args_values) + 1:
                    args_values += a[len(args_values) + 1 :]

                routine = func(*(obj, *args_values), **kw_values)
                if inspect.isawaitable(routine):
                    return_value = await routine
                else:
                    return_value = routine

                return return_value

            increase_execution_context_value("aws_sns_sqs_current_tasks")
            increase_execution_context_value("aws_sns_sqs_total_tasks")
            keep_message_in_queue = False
            try:
                logging.bind_logger(
                    logging.getLogger("tomodachi.awssnssqs.middleware").bind(
                        middleware=Ellipsis, handler=func.__name__, type="tomodachi.awssnssqs"
                    )
                )
                return_value = await asyncio.create_task(
                    execute_middlewares(
                        func,
                        routine_func,
                        context.get("_awssnssqs_message_pre_middleware", []) + context.get("message_middleware", []),
                        *(obj, message, topic),
                        message=message,
                        message_uuid=message_uuid,
                        topic=topic,
                        receipt_handle=receipt_handle,
                        queue_url=queue_url,
                        message_attributes=message_attributes_values,
                        approximate_receive_count=approximate_receive_count,
                        sns_message_id=sns_message_id,
                        sqs_message_id=sqs_message_id,
                        message_timestamp=message_timestamp,
                        message_deduplication_id=message_deduplication_id,
                        message_group_id=message_group_id,
                    )
                )
            except (Exception, asyncio.CancelledError, BaseException) as e:
                # todo: don't log exception in case the error is of a AWSSNSSQSInternalServiceError (et. al) type
                limit_exception_traceback(e, ("tomodachi.transport.aws_sns_sqs", "tomodachi.helpers.middleware"))
                logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))
                return_value = None
                if issubclass(
                    e.__class__,
                    (
                        AWSSNSSQSInternalServiceError,
                        AWSSNSSQSInternalServiceErrorException,
                        AWSSNSSQSInternalServiceException,
                    ),
                ):
                    keep_message_in_queue = True
                    if message_key:
                        del context["_aws_sns_sqs_received_messages"][message_key]

            if not keep_message_in_queue:
                await cls.delete_message(receipt_handle, queue_url, context)
            decrease_execution_context_value("aws_sns_sqs_current_tasks")

            return return_value

        attributes: Dict[str, Union[str, bool]] = {}

        if filter_policy != FILTER_POLICY_DEFAULT:
            if filter_policy is None:
                filter_policy = {}
            if isinstance(filter_policy, str):
                filter_policy = json.loads(filter_policy)
            attributes["FilterPolicy"] = json.dumps(filter_policy)

        context["_aws_sns_sqs_subscribers"] = context.get("_aws_sns_sqs_subscribers", [])
        context["_aws_sns_sqs_subscribers"].append(
            (
                topic,
                competing,
                queue_name,
                func,
                handler,
                attributes,
                visibility_timeout,
                dead_letter_queue_name,
                max_receive_count,
                fifo,
                max_number_of_consumed_messages,
            )
        )

        start_func = cls.subscribe(obj, context)
        return (await start_func) if start_func else None

    @staticmethod
    async def create_client(name: str, context: Dict) -> None:
        alias = f"tomodachi.{name}"
        if connector.get_client(alias):
            return

        options: Options = AWSSNSSQSTransport.options(context)

        credentials = {
            "region_name": options.aws_sns_sqs.region_name,
            "aws_secret_access_key": options.aws_sns_sqs.aws_secret_access_key,
            "aws_access_key_id": options.aws_sns_sqs.aws_access_key_id,
            "endpoint_url": options.aws_endpoint_urls.get(name, None),
        }

        connector.setup_credentials(alias, credentials)

        logging.getLogger("botocore.vendored.requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)

        try:
            await connector.create_client(alias, service_name=name)
        except (botocore.exceptions.PartialCredentialsError, botocore.exceptions.NoRegionError) as e:
            error_message = str(e)
            logging.getLogger("tomodachi.awssnssqs").warning(
                "Invalid credentials [{}] to AWS ({})".format(name, error_message)
            )
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get("log_level")) from e

    @classmethod
    async def create_topic(
        cls,
        topic: str,
        context: Dict,
        topic_prefix: Optional[str] = MESSAGE_TOPIC_PREFIX,
        attributes: Optional[Union[str, Dict[str, Union[bool, str]]]] = MESSAGE_TOPIC_ATTRIBUTES,
        overwrite_attributes: bool = True,
        fifo: bool = False,
    ) -> str:
        if cls.topics is None:
            cls.topics = {}

        if cls.topics and cls.topics.get(topic):
            topic_arn = cls.topics.get(topic)
            if topic_arn and isinstance(topic_arn, str):
                return topic_arn

        cls.validate_topic_name(topic)

        condition = await connector.get_condition("tomodachi.sns.create_topic")
        lock = connector.get_lock("tomodachi.sns.create_topic_lock")

        async with condition:
            if lock.locked() and not (cls.topics and cls.topics.get(topic)):
                await condition.wait()

            if cls.topics and cls.topics.get(topic):
                topic_arn = cls.topics.get(topic)
                if topic_arn and isinstance(topic_arn, str):
                    return topic_arn

            await lock.acquire()

        logger = logging.getLogger("tomodachi.awssnssqs").new(logger="tomodachi.awssnssqs", topic=topic)

        try:
            if not connector.get_client("tomodachi.sns"):
                await cls.create_client("sns", context)

            sns_kms_master_key_id: Any = cls.options(context).aws_sns_sqs.sns_kms_master_key_id
            if sns_kms_master_key_id is not None:
                if isinstance(sns_kms_master_key_id, str) and sns_kms_master_key_id == "":
                    sns_kms_master_key_id = ""
                elif isinstance(sns_kms_master_key_id, bool) and sns_kms_master_key_id is False:
                    sns_kms_master_key_id = ""
                elif isinstance(sns_kms_master_key_id, str) and sns_kms_master_key_id:
                    pass
                else:
                    raise ValueError(
                        "Bad value for aws_sns_sqs option sns_kms_master_key_id: {}".format(str(sns_kms_master_key_id))
                    )

            topic_attributes: Dict

            if attributes is None or attributes == MESSAGE_TOPIC_ATTRIBUTES:
                topic_attributes = {}
            elif not isinstance(attributes, dict):
                raise Exception(
                    "Argument 'attributes' to 'AWSSNSSQSTransport.create_topic' should be specified as a dict mapping"
                )
            else:
                topic_attributes = copy.deepcopy(attributes)

            if fifo:
                topic_attributes["FifoTopic"] = "true"
                topic_attributes["ContentBasedDeduplication"] = "false"

            if sns_kms_master_key_id is not None and "KmsMasterKeyId" not in topic_attributes:
                topic_attributes["KmsMasterKeyId"] = sns_kms_master_key_id

            update_attributes = True if topic_attributes else False
            topic_arn = None

            try:
                async with connector("tomodachi.sns", service_name="sns") as client:
                    response = await asyncio.wait_for(
                        client.create_topic(
                            Name=cls.encode_topic(cls.get_topic_name(topic, context, fifo, topic_prefix)),
                            Attributes=topic_attributes,
                        ),
                        timeout=40,
                    )
                    topic_arn = response.get("TopicArn")
                    update_attributes = False

                if topic_attributes and topic_attributes.get("KmsMasterKeyId") == "":
                    try:
                        async with connector("tomodachi.sns", service_name="sqs") as client:
                            topic_attributes_response = await client.get_topic_attributes(TopicArn=topic_arn)
                            if not topic_attributes_response.get("Attributes", {}).get("KmsMasterKeyId"):
                                update_attributes = False
                                overwrite_attributes = False
                    except Exception:
                        pass

                    if overwrite_attributes:
                        logger.info(
                            "SNS topic attribute 'KmsMasterKeyId' on SNS topic '{}' will be updated to disable server-side encryption".format(
                                topic_arn
                            )
                        )
                        update_attributes = True
            except (botocore.exceptions.NoCredentialsError, aiohttp.client_exceptions.ClientOSError) as e:
                error_message = str(e)
                logger.warning("Unable to connect [sns] to AWS ({})".format(error_message))
                raise AWSSNSSQSConnectionException(error_message, log_level=context.get("log_level")) from e
            except (
                botocore.exceptions.PartialCredentialsError,
                botocore.exceptions.ClientError,
                asyncio.TimeoutError,
            ) as e:
                error_message = str(e) if not isinstance(e, asyncio.TimeoutError) else "Network timeout"
                if "Topic already exists with different attributes" in error_message:
                    try:
                        async with connector("tomodachi.sns", service_name="sns") as client:
                            response = await asyncio.wait_for(
                                client.create_topic(
                                    Name=cls.encode_topic(cls.get_topic_name(topic, context, fifo, topic_prefix))
                                ),
                                timeout=40,
                            )
                            topic_arn = response.get("TopicArn")
                    except (
                        Exception,
                        asyncio.TimeoutError,
                    ) as e2:
                        error_message2 = str(e) if not isinstance(e, asyncio.TimeoutError) else "Network timeout"
                        logger.warning("Unable to create topic [sns] on AWS ({})".format(error_message2))
                        raise AWSSNSSQSException(error_message2, log_level=context.get("log_level")) from e2

                    logger.info("Already existing SNS topic '{}' has different topic attributes".format(topic_arn))
                else:
                    logger.warning("Unable to create topic [sns] on AWS ({})".format(error_message))
                    raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

            if update_attributes and topic_attributes and topic_arn and not overwrite_attributes:
                logger.warning("Will not overwrite existing attributes on SNS topic '{}'".format(topic_arn))
                update_attributes = False

            if update_attributes and topic_attributes and topic_arn:
                for attribute_name, attribute_value in topic_attributes.items():
                    try:
                        logger.info("Updating '{}' attribute on SNS topic '{}'".format(attribute_name, topic_arn))
                        async with connector("tomodachi.sns", service_name="sns") as client:
                            await client.set_topic_attributes(
                                TopicArn=topic_arn,
                                AttributeName=attribute_name,
                                AttributeValue=attribute_value,
                            )
                    except (
                        botocore.exceptions.NoCredentialsError,
                        aiohttp.client_exceptions.ClientOSError,
                        botocore.exceptions.PartialCredentialsError,
                        botocore.exceptions.ClientError,
                        asyncio.TimeoutError,
                    ) as e:
                        error_message = str(e)
                        logger.warning("Unable to create topic [sns] on AWS ({})".format(error_message))
                        raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

            if not topic_arn or not isinstance(topic_arn, str):
                error_message = "Missing ARN in response"
                logger.warning("Unable to create topic [sns] on AWS ({})".format(error_message))
                raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

            cls.topics[topic] = topic_arn
        finally:
            lock.release()
            async with condition:
                condition.notify()

        async with condition:
            condition.notify_all()

        return topic_arn

    @staticmethod
    def transform_message_attributes_from_response(
        message_attributes: Dict,
    ) -> MessageAttributesType:
        result: MessageAttributesType = {}

        for name, values in message_attributes.items():
            value = values["Value"]
            if values["Type"] == "String":
                result[name] = value
            elif values["Type"] == "Number":
                result[name] = int(value) if "." not in value else float(value)
            elif values["Type"] == "Binary":
                result[name] = base64.b64decode(value)
            elif values["Type"] == "String.Array":
                result[name] = cast(
                    Optional[Union[bool, List[Optional[Union[str, int, float, bool, object]]]]], json.loads(value)
                )

        return result

    @staticmethod
    def transform_message_attributes_to_botocore(message_attributes: Dict) -> Dict[str, Dict[str, Union[str, bytes]]]:
        result: Dict[str, Dict[str, Union[str, bytes]]] = {}

        for name, value in message_attributes.items():
            if isinstance(value, str):
                result[name] = {"DataType": "String", "StringValue": value}
            elif value is None or isinstance(value, bool):
                result[name] = {"DataType": "String.Array", "StringValue": json.dumps(value)}
            elif isinstance(value, (int, float, decimal.Decimal)):
                result[name] = {"DataType": "Number", "StringValue": str(value)}
            elif isinstance(value, bytes):
                result[name] = {"DataType": "Binary", "BinaryValue": value}
            elif isinstance(value, list):
                result[name] = {"DataType": "String.Array", "StringValue": json.dumps(value)}
            else:
                result[name] = {"DataType": "String", "StringValue": str(value)}

        return result

    @classmethod
    async def publish_message(
        cls,
        topic_arn: str,
        message: Any,
        message_attributes: Dict,
        context: Dict,
        group_id: Optional[str] = None,
        deduplication_id: Optional[str] = None,
        service: Any = None,
    ) -> str:
        return await cls._publish_message(
            topic_arn,
            message,
            message_attributes,
            context,
            group_id=group_id,
            deduplication_id=deduplication_id,
            service=service,
        )

    @classmethod
    async def _publish_message(
        cls,
        /,
        topic_arn: str,
        message: Any,
        message_attributes: Dict,
        context: Dict,
        *,
        group_id: Optional[str] = None,
        deduplication_id: Optional[str] = None,
        service: Any = None,
    ) -> str:
        if not connector.get_client("tomodachi.sns"):
            await cls.create_client("sns", context)

        message_attribute_values = cls.transform_message_attributes_to_botocore(message_attributes)

        fifo_attrs = {}
        if group_id is not None:
            fifo_attrs = {
                "MessageGroupId": group_id,
                "MessageDeduplicationId": deduplication_id or str(uuid.uuid4()),
            }

        response = {}
        for retry in range(1, 4):
            try:
                async with connector("tomodachi.sns", service_name="sns") as client:
                    response = await asyncio.wait_for(
                        client.publish(
                            TopicArn=topic_arn,
                            Message=message,
                            MessageAttributes=message_attribute_values,
                            **fifo_attrs,
                        ),
                        timeout=40,
                    )
            except (aiohttp.client_exceptions.ServerDisconnectedError, RuntimeError, asyncio.CancelledError) as e:
                if retry >= 3:
                    raise e
                continue
            except (
                botocore.exceptions.ClientError,
                aiohttp.client_exceptions.ClientConnectorError,
                asyncio.TimeoutError,
            ) as e:
                if retry >= 3:
                    error_message = str(e) if not isinstance(e, asyncio.TimeoutError) else "Network timeout"
                    logging.getLogger("tomodachi.awssnssqs").warning(
                        "Unable to publish message [sns] on AWS ({})".format(error_message)
                    )
                    raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e
                continue
            # AWS API can respond with empty body as 408 error - botocore adds "Further retries may succeed"
            except ResponseParserError as e:
                if retry >= 3 or "Further retries may succeed" not in str(e):
                    raise e
                continue
            break

        message_id = response.get("MessageId")
        if not message_id or not isinstance(message_id, str):
            error_message = "Missing MessageId in response"
            logging.getLogger("tomodachi.awssnssqs").warning(
                "Unable to publish message [sns] on AWS ({})".format(error_message)
            )
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

        return message_id

    @classmethod
    async def delete_message(cls, receipt_handle: Optional[str], queue_url: Optional[str], context: Dict) -> None:
        if not receipt_handle:
            return

        if not connector.get_client("tomodachi.sqs"):
            await cls.create_client("sqs", context)

        async def _delete_message() -> None:
            for retry in range(1, 5):
                try:
                    async with connector("tomodachi.sqs", service_name="sqs") as client:
                        await asyncio.wait_for(
                            client.delete_message(ReceiptHandle=receipt_handle, QueueUrl=queue_url), timeout=12
                        )
                except (
                    aiohttp.client_exceptions.ServerDisconnectedError,
                    aiohttp.client_exceptions.ClientConnectorError,
                    RuntimeError,
                    asyncio.CancelledError,
                ) as e:
                    if retry >= 4:
                        raise e
                    continue
                except botocore.exceptions.ClientError as e:
                    error_message = str(e)
                    logging.getLogger("tomodachi.awssnssqs").warning(
                        "Unable to delete message [sqs] on AWS ({})".format(error_message)
                    )
                except asyncio.TimeoutError as e:
                    if retry >= 4:
                        error_message = "Network timeout"
                        logging.getLogger("tomodachi.awssnssqs").warning(
                            "Unable to delete message [sqs] on AWS ({})".format(error_message)
                        )
                        raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e
                    continue
                # AWS API can respond with empty body as 408 error - botocore adds "Further retries may succeed"
                except ResponseParserError as e:
                    if retry >= 4 or "Further retries may succeed" not in str(e):
                        raise e
                    continue
                break

        await _delete_message()

    @classmethod
    async def get_queue_url_from_arn(cls, queue_arn: str, context: Dict) -> Optional[str]:
        if not connector.get_client("tomodachi.sqs"):
            await cls.create_client("sqs", context)

        queue_name = queue_arn.split(":")[-1]
        account_id = queue_arn.split(":")[-2]

        queue_url = None
        try:
            async with connector("tomodachi.sqs", service_name="sqs") as client:
                response = await client.get_queue_url(QueueName=queue_name, QueueOwnerAWSAccountId=account_id)
                queue_url = response.get("QueueUrl")
        except (
            botocore.exceptions.NoCredentialsError,
            botocore.exceptions.PartialCredentialsError,
            aiohttp.client_exceptions.ClientOSError,
        ) as e:
            error_message = str(e)
            logging.getLogger("tomodachi.awssnssqs").warning(
                "Unable to connect [sqs] to AWS ({})".format(error_message)
            )
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get("log_level")) from e
        except botocore.exceptions.ClientError:
            pass

        return queue_url

    @classmethod
    async def create_queue(
        cls,
        queue_name: str,
        context: Dict,
        fifo: bool,
        message_retention_period: Union[int, str] = MESSAGE_RETENTION_PERIOD_DEFAULT,
    ) -> Tuple[str, str]:
        cls.validate_queue_name(queue_name)
        if not connector.get_client("tomodachi.sqs"):
            await cls.create_client("sqs", context)

        logger = logging.getLogger("tomodachi.awssnssqs").new(
            logger="tomodachi.awssnssqs",
            queue_name=logging.getLogger("tomodachi.awssnssqs")._context.get("queue_name", queue_name),
        )

        queue_url = ""
        try:
            async with connector("tomodachi.sqs", service_name="sqs") as client:
                response = await client.get_queue_url(QueueName=queue_name)
                queue_url = response.get("QueueUrl")
        except (
            botocore.exceptions.NoCredentialsError,
            botocore.exceptions.PartialCredentialsError,
            aiohttp.client_exceptions.ClientOSError,
        ) as e:
            error_message = str(e)
            logger.warning("Unable to connect [sqs] to AWS ({})".format(error_message))
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get("log_level")) from e
        except botocore.exceptions.ClientError:
            pass

        if not queue_url:
            queue_attrs = (
                {
                    "FifoQueue": "true",
                    "ContentBasedDeduplication": "false",
                    "DeduplicationScope": "messageGroup",
                    "FifoThroughputLimit": "perMessageGroupId",
                }
                if fifo
                else {}
            )
            if isinstance(message_retention_period, int) and str(message_retention_period) != str(
                MESSAGE_RETENTION_PERIOD_DEFAULT
            ):
                queue_attrs["MessageRetentionPeriod"] = str(message_retention_period)
            try:
                async with connector("tomodachi.sqs", service_name="sqs") as client:
                    response = await client.create_queue(QueueName=queue_name, Attributes=queue_attrs)
                    queue_url = response.get("QueueUrl")
            except (
                botocore.exceptions.NoCredentialsError,
                botocore.exceptions.PartialCredentialsError,
                aiohttp.client_exceptions.ClientOSError,
            ) as e:
                error_message = str(e)
                logger.warning("Unable to connect [sqs] to AWS ({})".format(error_message))
                raise AWSSNSSQSConnectionException(error_message, log_level=context.get("log_level")) from e
            except botocore.exceptions.ClientError as e:
                error_message = str(e)
                logger.warning("Unable to create queue [sqs] on AWS ({})".format(error_message))
                raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

        if not queue_url:
            error_message = "Missing Queue URL in response"
            logger.warning("Unable to create queue [sqs] on AWS ({})".format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

        try:
            async with connector("tomodachi.sqs", service_name="sqs") as client:
                response = await client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            logger.warning("Unable to get queue attributes [sqs] on AWS ({})".format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

        queue_arn = response.get("Attributes", {}).get("QueueArn")
        if not queue_arn:
            error_message = "Missing ARN in response"
            logger.warning("Unable to get queue attributes [sqs] on AWS ({})".format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

        queue_fifo = queue_name.endswith(".fifo")
        if fifo is not queue_fifo:
            queue_types = {False: "Standard", True: "FIFO"}
            error_message = (
                f"AWS SQS queue configured as {queue_types[queue_fifo]}, "
                f"but the handler expected {queue_types[fifo]}."
            )
            logger.warning("Queue [sqs] type mismatch ({})".format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

        return queue_url, queue_arn

    @classmethod
    def generate_queue_policy(cls, queue_arn: str, topic_arn_list: Union[List, Tuple], context: Dict) -> Dict:
        aws_sns_sqs_options: Options.AWSSNSSQS = cls.options(context).aws_sns_sqs
        if len(topic_arn_list) == 1:
            if aws_sns_sqs_options.queue_policy:
                source_arn = aws_sns_sqs_options.queue_policy
            else:
                source_arn = topic_arn_list[0]
        else:
            wildcard_topic_arn = []
            try:
                for i in range(0, min([len(topic_arn) for topic_arn in topic_arn_list])):
                    if len(set([topic_arn[i] for topic_arn in topic_arn_list])) == 1:
                        wildcard_topic_arn.append(topic_arn_list[0][i])
                    else:
                        wildcard_topic_arn.append("*")
                        break
            except IndexError:
                wildcard_topic_arn.append("*")

            source_arn = "".join(wildcard_topic_arn)
            if aws_sns_sqs_options.queue_policy:
                source_arn = aws_sns_sqs_options.queue_policy
            if aws_sns_sqs_options.wildcard_queue_policy:
                source_arn = aws_sns_sqs_options.wildcard_queue_policy

        queue_policy = {
            "Version": "2012-10-17",
            "Id": "{}/SQSDefaultPolicy".format(queue_arn),
            "Statement": [
                {
                    "Sid": "{}{}".format(str(uuid.uuid4()), ("%.3f" % time.time()).replace(".", "")),
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "SQS:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {"ArnEquals": {"aws:SourceArn": source_arn}},
                }
            ],
        }
        return queue_policy

    @classmethod
    async def subscribe_wildcard_topic(
        cls,
        topic: str,
        queue_arn: str,
        queue_url: str,
        context: Dict,
        fifo: bool,
        attributes: Optional[Dict[str, Union[str, bool]]] = None,
        visibility_timeout: Optional[int] = None,
        redrive_policy: Optional[Dict[str, Union[str, int]]] = None,
    ) -> Optional[List]:
        if cls.topics is None:
            cls.topics = {}

        if not connector.get_client("tomodachi.sns"):
            await cls.create_client("sns", context)

        pattern = r"^arn:aws:sns:[^:]+:[^:]+:{}$".format(
            cls.encode_topic(cls.get_topic_name(topic, context, fifo))
            .replace(cls.encode_topic("*"), "((?!{}).)*".format(cls.encode_topic(".")))
            .replace(cls.encode_topic("#"), ".*")
        )
        compiled_pattern = re.compile(pattern)

        next_token: Any = False
        topic_arn_list: Optional[List[str]] = None
        while next_token is not None:
            try:
                async with connector("tomodachi.sns", service_name="sns") as client:
                    if next_token:
                        response = await client.list_topics(NextToken=next_token)
                    else:
                        response = await client.list_topics()
            except botocore.exceptions.ClientError as e:
                error_message = str(e)
                logging.getLogger("tomodachi.awssnssqs").warning(
                    "Unable to list topics [sns] on AWS ({})".format(error_message)
                )
                raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

            next_token = response.get("NextToken")
            topics = response.get("Topics", [])
            topic_arn_list = [
                t.get("TopicArn") for t in topics if t.get("TopicArn") and compiled_pattern.match(t.get("TopicArn"))
            ]

        if topic_arn_list:
            queue_policy = cls.generate_queue_policy(queue_arn, topic_arn_list, context)
            cls.topics[topic] = topic_arn_list[0]
            return await cls.subscribe_topics(
                topic_arn_list,
                queue_arn,
                queue_url,
                context,
                queue_policy=queue_policy,
                attributes=attributes,
                visibility_timeout=visibility_timeout,
                redrive_policy=redrive_policy,
            )

        return None

    @classmethod
    async def subscribe_topics(
        cls,
        topic_arn_list: Union[List, Tuple],
        queue_arn: str,
        queue_url: str,
        context: Dict,
        queue_policy: Optional[Dict] = None,
        attributes: Optional[Dict[str, Union[str, bool]]] = None,
        visibility_timeout: Optional[int] = None,
        redrive_policy: Optional[Dict[str, Union[str, int]]] = None,
    ) -> List:
        if not connector.get_client("tomodachi.sns"):
            await cls.create_client("sns", context)

        if not connector.get_client("tomodachi.sqs"):
            await cls.create_client("sqs", context)

        if not queue_policy:
            queue_policy = cls.generate_queue_policy(queue_arn, topic_arn_list, context)

        if not queue_policy or not isinstance(queue_policy, dict):
            raise Exception("SQS policy is invalid")

        if redrive_policy is not None and not isinstance(redrive_policy, dict):
            raise Exception("SQS redrive_policy is invalid")

        if visibility_timeout == VISIBILITY_TIMEOUT_DEFAULT:
            visibility_timeout = None

        if visibility_timeout is not None and (
            not isinstance(visibility_timeout, int)
            or visibility_timeout < 0
            or visibility_timeout > 43200
            or visibility_timeout is True
            or visibility_timeout is False
        ):
            raise Exception("SQS visibility_timeout is invalid")

        aws_sns_sqs_options: Options.AWSSNSSQS = cls.options(context).aws_sns_sqs

        sqs_kms_master_key_id: Optional[Union[str, bool]] = aws_sns_sqs_options.sqs_kms_master_key_id
        if sqs_kms_master_key_id is not None:
            if isinstance(sqs_kms_master_key_id, str) and sqs_kms_master_key_id == "":
                sqs_kms_master_key_id = ""
            elif isinstance(sqs_kms_master_key_id, bool) and sqs_kms_master_key_id is False:
                sqs_kms_master_key_id = ""
            elif isinstance(sqs_kms_master_key_id, str) and sqs_kms_master_key_id:
                pass
            else:
                raise ValueError(
                    "Bad value for aws_sns_sqs option sqs_kms_master_key_id: {}".format(str(sqs_kms_master_key_id))
                )

        sqs_kms_data_key_reuse_period_option: Optional[int] = aws_sns_sqs_options.sqs_kms_data_key_reuse_period
        sqs_kms_data_key_reuse_period: Optional[int] = None
        if sqs_kms_data_key_reuse_period_option is None or sqs_kms_data_key_reuse_period_option is False:
            sqs_kms_data_key_reuse_period = None
        if sqs_kms_data_key_reuse_period_option is True:
            raise ValueError(
                "Bad value for aws_sns_sqs option sqs_kms_data_key_reuse_period: {}".format(
                    str(sqs_kms_data_key_reuse_period_option)
                )
            )
        try:
            if sqs_kms_data_key_reuse_period_option is not None:
                sqs_kms_data_key_reuse_period = int(sqs_kms_data_key_reuse_period_option)
            if sqs_kms_data_key_reuse_period == 0:
                sqs_kms_data_key_reuse_period = None
        except Exception:
            raise ValueError(
                "Bad value for aws_sns_sqs option sqs_kms_data_key_reuse_period: {}".format(
                    str(sqs_kms_data_key_reuse_period_option)
                )
            ) from None

        current_queue_attributes = {}
        current_queue_policy = {}
        current_visibility_timeout = None
        current_message_retention_period = None
        current_redrive_policy = None
        current_kms_master_key_id = None
        current_kms_data_key_reuse_period_seconds = None

        message_retention_period = None

        try:
            async with connector("tomodachi.sqs", service_name="sqs") as sqs_client:
                response = await sqs_client.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=[
                        "Policy",
                        "RedrivePolicy",
                        "VisibilityTimeout",
                        "MessageRetentionPeriod",
                        "KmsMasterKeyId",
                        "KmsDataKeyReusePeriodSeconds",
                    ],
                )
                current_queue_attributes = response.get("Attributes", {})
                current_queue_policy = json.loads(current_queue_attributes.get("Policy") or "{}")
                current_visibility_timeout = current_queue_attributes.get("VisibilityTimeout")
                if current_queue_attributes:
                    current_redrive_policy = json.loads(current_queue_attributes.get("RedrivePolicy") or "{}")
                if current_visibility_timeout:
                    current_visibility_timeout = int(current_visibility_timeout)
                current_message_retention_period = current_queue_attributes.get("MessageRetentionPeriod")
                if current_message_retention_period:
                    try:
                        current_message_retention_period = int(current_message_retention_period)
                    except ValueError:
                        current_message_retention_period = None
                current_kms_master_key_id = current_queue_attributes.get("KmsMasterKeyId")
                current_kms_data_key_reuse_period_seconds = current_queue_attributes.get("KmsDataKeyReusePeriodSeconds")
                if current_kms_data_key_reuse_period_seconds:
                    current_kms_data_key_reuse_period_seconds = int(current_kms_data_key_reuse_period_seconds)
        except botocore.exceptions.ClientError:
            pass

        queue_attributes = {}

        if not current_queue_policy or [{**x, "Sid": ""} for x in current_queue_policy.get("Statement", [])] != [
            {**x, "Sid": ""} for x in queue_policy.get("Statement", [])
        ]:
            queue_attributes["Policy"] = json.dumps(queue_policy)

        if visibility_timeout and current_visibility_timeout and visibility_timeout != current_visibility_timeout:
            queue_attributes["VisibilityTimeout"] = str(
                visibility_timeout
            )  # SQS.SetQueueAttributes "Attributes" are mapped string -> string

        if (
            redrive_policy is not None
            and current_redrive_policy is not None
            and redrive_policy != current_redrive_policy
        ):
            queue_attributes["RedrivePolicy"] = json.dumps(redrive_policy)

        if (
            message_retention_period  # type: ignore
            and current_message_retention_period
            and message_retention_period != current_message_retention_period
        ):
            queue_attributes["MessageRetentionPeriod"] = str(  # type: ignore
                message_retention_period
            )  # SQS.SetQueueAttributes "Attributes" are mapped string -> string

        if (
            sqs_kms_master_key_id is not None
            and current_kms_master_key_id != sqs_kms_master_key_id
            and (current_kms_master_key_id or sqs_kms_master_key_id)
        ):
            queue_attributes["KmsMasterKeyId"] = sqs_kms_master_key_id

        if (
            sqs_kms_data_key_reuse_period is not None
            and current_kms_data_key_reuse_period_seconds != sqs_kms_data_key_reuse_period
            and (current_kms_master_key_id or sqs_kms_master_key_id)
        ):
            queue_attributes["KmsDataKeyReusePeriodSeconds"] = str(
                sqs_kms_data_key_reuse_period
            )  # SQS.SetQueueAttributes "Attributes" are mapped string -> string

        if queue_attributes:
            if current_queue_policy:
                for attribute_name, _ in queue_attributes.items():
                    logging.getLogger("tomodachi.awssnssqs").info(
                        "Updating '{}' attribute on SQS queue '{}'".format(attribute_name, queue_arn)
                    )

            try:
                async with connector("tomodachi.sqs", service_name="sqs") as sqs_client:
                    response = await sqs_client.set_queue_attributes(QueueUrl=queue_url, Attributes=queue_attributes)
            except botocore.exceptions.ClientError as e:
                error_message = str(e)
                logging.getLogger("tomodachi.awssnssqs").warning(
                    "Unable to set queue attributes [sqs] on AWS ({})".format(error_message)
                )
                raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

        subscription_arn_list = []

        # Subscription attributes: DeliveryPolicy, FilterPolicy, RawMessageDelivery, RedrivePolicy
        update_attributes = True if attributes else False

        for topic_arn in topic_arn_list:
            subscription_arn = None

            if update_attributes and attributes:
                try:
                    async with connector("tomodachi.sns", service_name="sns") as sns_client:
                        response = await sns_client.subscribe(
                            TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn, Attributes=attributes
                        )
                        subscription_arn = response.get("SubscriptionArn")
                        if subscription_arn and "000000000000" not in subscription_arn:
                            update_attributes = False
                except botocore.exceptions.ClientError as e:
                    error_message = str(e)
                    if "Subscription already exists with different attributes" in error_message:
                        logging.getLogger("tomodachi.awssnssqs").info(
                            "SNS subscription for topic ARN '{}' and queue ARN '{}' previously had different attributes".format(
                                topic_arn, queue_arn
                            )
                        )
                    else:
                        logging.getLogger("tomodachi.awssnssqs").warning(
                            "Unable to subscribe to topic [sns] on AWS ({})".format(error_message)
                        )
                        raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

            if not subscription_arn:
                try:
                    async with connector("tomodachi.sns", service_name="sns") as sns_client:
                        response = await sns_client.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)
                    subscription_arn = response.get("SubscriptionArn")
                except botocore.exceptions.ClientError as e:
                    error_message = str(e)
                    logging.getLogger("tomodachi.awssnssqs").warning(
                        "Unable to subscribe to topic [sns] on AWS ({})".format(error_message)
                    )
                    raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

            if not subscription_arn:
                error_message = "Missing Subscription ARN in response"
                logging.getLogger("tomodachi.awssnssqs").warning(
                    "Unable to subscribe to topic [sns] on AWS ({})".format(error_message)
                )
                raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

            if update_attributes and attributes:
                for attribute_name, attribute_value in attributes.items():
                    try:
                        if "000000000000" not in subscription_arn:
                            logging.getLogger("tomodachi.awssnssqs").info(
                                "Updating '{}' attribute on subscription for topic ARN '{}' and queue ARN '{}' - changes can take several minutes to propagate".format(
                                    attribute_name, topic_arn, queue_arn
                                )
                            )
                        async with connector("tomodachi.sns", service_name="sns") as sns_client:
                            await sns_client.set_subscription_attributes(
                                SubscriptionArn=subscription_arn,
                                AttributeName=attribute_name,
                                AttributeValue=attribute_value,
                            )
                    except botocore.exceptions.ClientError as e:
                        error_message = str(e)
                        logging.getLogger("tomodachi.awssnssqs").warning(
                            "Unable to subscribe to topic [sns] on AWS ({})".format(error_message)
                        )
                        raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

            subscription_arn_list.append(subscription_arn)

        return subscription_arn_list

    @classmethod
    async def consume_queue(
        cls,
        obj: Any,
        context: Dict,
        handler: Callable,
        queue_url: str,
        func: Callable,
        topic: Optional[str],
        queue_name: Optional[str],
        max_number_of_consumed_messages: int,
    ) -> None:
        logger = logging.getLogger()

        if not (1 <= max_number_of_consumed_messages <= 10):
            max_number_of_consumed_messages = MAX_NUMBER_OF_CONSUMED_MESSAGES

        wait_time_seconds = 20

        if not connector.get_client("tomodachi.sqs"):
            await cls.create_client("sqs", context)

        if not cls.close_waiter:
            cls.close_waiter = asyncio.Future()

        stop_waiter: asyncio.Future = asyncio.Future()
        start_waiter: asyncio.Future = asyncio.Future()

        async def receive_messages() -> None:
            logger = logging.getLogger("tomodachi.awssnssqs").bind(
                wrapped_handler=func.__name__, topic=topic or Ellipsis, queue_name=queue_name or Ellipsis
            )
            logging.bind_logger(logger)

            await start_waiter

            async def _receive_wrapper() -> None:
                def callback(
                    payload: Optional[str],
                    receipt_handle: Optional[str],
                    queue_url: Optional[str],
                    message_topic: str,
                    message_attributes: Dict,
                    approximate_receive_count: Optional[int],
                    sns_message_id: Optional[str],
                    sqs_message_id: Optional[str],
                    message_timestamp: Optional[str],
                    message_deduplication_id: Optional[str],
                    message_group_id: Optional[str],
                ) -> Callable[..., Coroutine]:
                    async def _callback() -> None:
                        await handler(
                            payload,
                            receipt_handle,
                            queue_url,
                            message_topic,
                            message_attributes,
                            approximate_receive_count,
                            sns_message_id,
                            sqs_message_id,
                            message_timestamp,
                            message_deduplication_id,
                            message_group_id,
                        )

                    return _callback

                is_disconnected = False

                while cls.close_waiter and not cls.close_waiter.done():
                    coro_wrappers: List[Callable[..., Coroutine]] = []

                    # In case of FIFO queues, we cannot receive more
                    # than one message at a time, because otherwise we will not
                    # be able to ensure their execution order.
                    message_limit = 1 if queue_url.endswith(".fifo") else max_number_of_consumed_messages

                    try:
                        try:
                            async with connector("tomodachi.sqs", service_name="sqs") as client:
                                response = await asyncio.wait_for(
                                    client.receive_message(
                                        QueueUrl=queue_url,
                                        WaitTimeSeconds=wait_time_seconds,
                                        MaxNumberOfMessages=message_limit,
                                        AttributeNames=[
                                            "ApproximateReceiveCount",
                                            "MessageDeduplicationId",
                                            "MessageGroupId",
                                        ],
                                    ),
                                    timeout=40,
                                )
                            if is_disconnected:
                                is_disconnected = False
                                logger.warning("Reconnected - receiving messages")
                        except (aiohttp.client_exceptions.ServerDisconnectedError, RuntimeError) as e:
                            if not is_disconnected:
                                is_disconnected = True
                                error_message = str(e) if e and str(e) not in ["", "None"] else "Server disconnected"
                                logger.warning(
                                    "Unable to receive message from queue [sqs] on AWS ({}) - reconnecting".format(
                                        error_message
                                    )
                                )
                            continue
                        except asyncio.CancelledError:
                            continue
                        except ResponseParserError:
                            if not is_disconnected:
                                is_disconnected = True
                                error_message = "Unable to parse response: the server was not able to produce a timely response to your request"
                                logger.warning(
                                    "Unable to receive message from queue [sqs] on AWS ({}) - reconnecting".format(
                                        error_message
                                    )
                                )
                            await asyncio.sleep(1)
                            continue
                        except (
                            botocore.exceptions.ClientError,
                            aiohttp.client_exceptions.ClientConnectorError,
                            asyncio.TimeoutError,
                        ) as e:
                            error_message = str(e) if not isinstance(e, asyncio.TimeoutError) else "Network timeout"
                            if "AWS.SimpleQueueService.NonExistentQueue" in error_message:
                                if is_disconnected:
                                    is_disconnected = False
                                    logger.warning("Reconnected - receiving messages")
                                try:
                                    context["_aws_sns_sqs_subscribed"] = False
                                    cls.topics = {}
                                    sub_func = await asyncio.create_task(cls.subscribe(obj, context))
                                    if sub_func:
                                        await asyncio.create_task(sub_func())
                                except Exception:
                                    pass
                                await asyncio.sleep(20)
                                continue
                            if not is_disconnected:
                                logger.warning(
                                    "Unable to receive message from queue [sqs] on AWS ({})".format(error_message)
                                )
                            if isinstance(e, (asyncio.TimeoutError, aiohttp.client_exceptions.ClientConnectorError)):
                                is_disconnected = True
                            await asyncio.sleep(1)
                            continue
                        except Exception as e:
                            error_message = str(e)
                            logger.warning(
                                "Unexpected error while receiving message from queue [sqs] on AWS ({})".format(
                                    error_message
                                )
                            )
                            await asyncio.sleep(1)
                            continue
                        except BaseException as e:
                            error_message = str(e)
                            logger.warning(
                                "Unexpected error while receiving message from queue [sqs] on AWS ({})".format(
                                    error_message
                                )
                            )
                            await asyncio.sleep(1)
                            continue

                        messages = response.get("Messages", [])
                        if not messages:
                            continue

                        for message in messages:
                            receipt_handle = message.get("ReceiptHandle")
                            try:
                                message_body = json.loads(message.get("Body"))
                                topic_arn = message_body.get("TopicArn")
                                message_topic = (
                                    cls.get_topic_name_without_prefix(
                                        cls.decode_topic(cls.get_topic_from_arn(topic_arn)), context
                                    )
                                    if topic_arn
                                    else ""
                                )
                            except ValueError:
                                # Malformed SQS message, not in SNS format and should be discarded
                                await cls.delete_message(receipt_handle, queue_url, context)
                                logger.warning("Discarded malformed message")
                                continue

                            payload = message_body.get("Message")
                            message_attributes = message_body.get("MessageAttributes", {})
                            approximate_receive_count: Optional[int] = (
                                int(message.get("Attributes", {}).get("ApproximateReceiveCount", 0)) or None
                            )
                            message_deduplication_id: Optional[str] = (
                                str(message.get("Attributes", {}).get("MessageDeduplicationId", "")) or None
                            )
                            message_group_id: Optional[str] = (
                                str(message.get("Attributes", {}).get("MessageGroupId", "")) or None
                            )

                            sns_message_id = message_body.get("MessageId") or ""
                            sqs_message_id = message.get("MessageId") or ""
                            message_timestamp = message_body.get("Timestamp") or ""

                            coro_wrappers.append(
                                callback(
                                    payload,
                                    receipt_handle,
                                    queue_url,
                                    message_topic,
                                    message_attributes,
                                    approximate_receive_count,
                                    sns_message_id,
                                    sqs_message_id,
                                    message_timestamp,
                                    message_deduplication_id,
                                    message_group_id,
                                )
                            )
                    except asyncio.CancelledError:
                        continue
                    except BaseException as e:
                        logging.getLogger("exception").exception(
                            "Uncaught exception while receiving messages: {}".format(str(e))
                        )
                        continue

                    tasks = [asyncio.ensure_future(coro()) for coro in coro_wrappers]
                    if not tasks:
                        continue
                    try:
                        await asyncio.shield(asyncio.wait(tasks))
                    except asyncio.CancelledError:
                        await asyncio.wait(tasks)
                        await asyncio.sleep(1)

                if not stop_waiter.done():
                    stop_waiter.set_result(None)

            task: Optional[asyncio.Future] = None
            while True:
                if task and cls.close_waiter and not cls.close_waiter.done():
                    logger.warning("Resuming message receiving after trying to recover from fatal error")
                if not task or task.done():
                    task = asyncio.ensure_future(_receive_wrapper())
                await asyncio.wait([cast(asyncio.Future, cls.close_waiter), task], return_when=asyncio.FIRST_COMPLETED)
                if not cls.close_waiter or cls.close_waiter.done():
                    break
                if not cls.close_waiter.done() and task.done() and task.exception():
                    try:
                        exception = task.exception()
                        if exception:
                            raise exception
                    except Exception as e:
                        logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))
                    sleep_task: asyncio.Future = asyncio.ensure_future(asyncio.sleep(10))
                    await asyncio.wait([sleep_task, cls.close_waiter], return_when=asyncio.FIRST_COMPLETED)
                    if not sleep_task.done():
                        sleep_task.cancel()

            if task and not task.done():
                task.cancel()
                await task

        stop_method = getattr(obj, "_stop_service", None)

        async def stop_service(*args: Any, **kwargs: Any) -> None:
            if cls.close_waiter and not cls.close_waiter.done():
                cls.close_waiter.set_result(None)
                logger.info("draining sqs receiver loop")

                if not start_waiter.done():
                    start_waiter.set_result(None)

                sleep_task: asyncio.Future = asyncio.ensure_future(asyncio.sleep(2))
                await asyncio.wait([sleep_task, stop_waiter], return_when=asyncio.FIRST_COMPLETED)
                if not sleep_task.done():
                    sleep_task.cancel()
                else:
                    task_count = get_execution_context().get("aws_sns_sqs_current_tasks", 0)
                    if task_count > 0:
                        logger.warning(
                            "awaiting running tasks",
                            task_count=task_count,
                        )

                await stop_waiter
                if stop_method:
                    await stop_method(*args, **kwargs)
                await connector.close()
            else:
                if not start_waiter.done():
                    start_waiter.set_result(None)

                await stop_waiter
                if stop_method:
                    await stop_method(*args, **kwargs)

        setattr(obj, "_stop_service", stop_service)

        started_method = getattr(obj, "_started_service", None)

        async def started_service(*args: Any, **kwargs: Any) -> None:
            if started_method:
                await started_method(*args, **kwargs)
            if not start_waiter.done():
                start_waiter.set_result(None)

        setattr(obj, "_started_service", started_service)

        asyncio.create_task(receive_messages())

    @classmethod
    async def subscribe(cls, obj: Any, context: Dict) -> Optional[Callable]:
        if context.get("_aws_sns_sqs_subscribed"):
            return None
        context["_aws_sns_sqs_subscribed"] = True

        logger = logging.getLogger("tomodachi.awssnssqs").new(logger="tomodachi.awssnssqs")
        logging.bind_logger(logger)

        async def _subscribe() -> None:
            logger = logging.getLogger("tomodachi.awssnssqs").new(logger="tomodachi.awssnssqs")
            logging.bind_logger(logger)

            if not connector.get_client("tomodachi.sns"):
                await cls.create_client("sns", context)

            if not connector.get_client("tomodachi.sqs"):
                await cls.create_client("sqs", context)

            cls.close_waiter = asyncio.Future()

            set_execution_context(
                {
                    "aws_sns_sqs_enabled": True,
                    "aws_sns_sqs_current_tasks": 0,
                    "aws_sns_sqs_total_tasks": 0,
                    "aiobotocore_version": aiobotocore.__version__,
                    "aiohttp_version": aiohttp.__version__,
                    "botocore_version": botocore.__version__,
                }
            )

            async def setup_queue(
                func: Callable,
                topic: Optional[str] = None,
                queue_name: Optional[str] = None,
                competing_consumer: Optional[bool] = None,
                attributes: Optional[Dict[str, Union[str, bool]]] = None,
                visibility_timeout: Optional[int] = None,
                dead_letter_queue_name: Optional[str] = DEAD_LETTER_QUEUE_DEFAULT,
                max_receive_count: Optional[int] = MAX_RECEIVE_COUNT_DEFAULT,
                fifo: bool = False,
            ) -> str:
                logger = logging.getLogger("tomodachi.awssnssqs").bind(
                    wrapped_handler=func.__name__, topic=topic or Ellipsis, queue_name=queue_name or Ellipsis
                )
                logging.bind_logger(logger)

                _uuid = obj.uuid

                if queue_name and competing_consumer is False:
                    raise AWSSNSSQSException(
                        "AWS SQS queue with predefined queue name must be competing", log_level=context.get("log_level")
                    )

                queue_url = None
                queue_arn = None
                if queue_name is None:
                    queue_name = cls.get_queue_name(
                        cls.encode_topic(topic or ""),
                        func.__name__,
                        _uuid,
                        competing_consumer,
                        context,
                        fifo,
                    )
                elif queue_name.startswith("arn:aws:sqs:"):
                    queue_arn = queue_name
                    queue_name = queue_arn.split(":")[-1]
                    queue_url = await cls.get_queue_url_from_arn(queue_arn, context)
                    if not queue_url:
                        raise AWSSNSSQSException(
                            "AWS SQS queue with specific ARN ({}) does not exist".format(queue_arn),
                            log_level=context.get("log_level"),
                        )
                else:
                    queue_name = cls.prefix_queue_name(queue_name, context)

                if not queue_url:
                    queue_url, queue_arn = cast(
                        Tuple[str, str], await asyncio.create_task(cls.create_queue(queue_name, context, fifo))
                    )

                redrive_policy: Optional[Dict[str, Union[str, int]]] = None
                if dead_letter_queue_name is None and max_receive_count in (MAX_RECEIVE_COUNT_DEFAULT, None):
                    max_receive_count = None
                    redrive_policy = {}
                elif (
                    dead_letter_queue_name != DEAD_LETTER_QUEUE_DEFAULT
                    or max_receive_count != MAX_RECEIVE_COUNT_DEFAULT
                ):
                    if (
                        not isinstance(dead_letter_queue_name, str)
                        or not dead_letter_queue_name.strip()
                        or dead_letter_queue_name == DEAD_LETTER_QUEUE_DEFAULT
                        or not isinstance(max_receive_count, int)
                        or max_receive_count is True
                        or max_receive_count < 1
                    ):
                        raise AWSSNSSQSException(
                            "Invalid values specified for dead-letter queue parameters (dead_letter_queue_name and max_receive_count)",
                            log_level=context.get("log_level"),
                        )
                    dlq_arn: str
                    if dead_letter_queue_name.startswith("arn:aws:sqs:"):
                        dlq_arn = dead_letter_queue_name
                        dlq_url = await cls.get_queue_url_from_arn(dlq_arn, context)
                        if not dlq_url:
                            raise AWSSNSSQSException(
                                "AWS SQS dead-letter queue with specific ARN ({}) does not exist".format(queue_arn),
                                log_level=context.get("log_level"),
                            )
                    else:

                        async def _create_dlq(dead_letter_queue_name: str) -> Tuple[str, str]:
                            logging.bind_logger(logging.getLogger().bind(queue_name=dead_letter_queue_name))
                            return await cls.create_queue(
                                cls.prefix_queue_name(dead_letter_queue_name, context),
                                context,
                                fifo,
                                DLQ_MESSAGE_RETENTION_PERIOD_DEFAULT,
                            )

                        dlq_url, dlq_arn = await asyncio.create_task(_create_dlq(dead_letter_queue_name))

                    redrive_policy = {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": max_receive_count}

                if topic:
                    if re.search(r"([*#])", topic):
                        await asyncio.create_task(
                            cls.subscribe_wildcard_topic(
                                topic,
                                cast(str, queue_arn),
                                queue_url,
                                context,
                                attributes=attributes,
                                visibility_timeout=visibility_timeout,
                                redrive_policy=redrive_policy,
                                fifo=fifo,
                            )
                        )
                    else:
                        topic_arn = await asyncio.create_task(cls.create_topic(topic, context, fifo=fifo))
                        await asyncio.create_task(
                            cls.subscribe_topics(
                                (topic_arn,),
                                cast(str, queue_arn),
                                queue_url,
                                context,
                                attributes=attributes,
                                visibility_timeout=visibility_timeout,
                                redrive_policy=redrive_policy,
                            )
                        )

                return queue_url

            try:
                for (
                    topic,
                    competing,
                    queue_name,
                    func,
                    handler,
                    attributes,
                    visibility_timeout,
                    dead_letter_queue_name,
                    max_receive_count,
                    fifo,
                    max_number_of_consumed_messages,
                ) in context.get("_aws_sns_sqs_subscribers", []):
                    queue_url = await asyncio.create_task(
                        setup_queue(
                            func,
                            topic=topic,
                            queue_name=queue_name,
                            competing_consumer=competing,
                            attributes=attributes,
                            visibility_timeout=visibility_timeout,
                            dead_letter_queue_name=dead_letter_queue_name,
                            max_receive_count=max_receive_count,
                            fifo=fifo,
                        )
                    )
                    await asyncio.create_task(
                        cls.consume_queue(
                            obj,
                            context,
                            handler,
                            queue_url=queue_url,
                            func=func,
                            topic=topic,
                            queue_name=queue_name,
                            max_number_of_consumed_messages=max_number_of_consumed_messages,
                        )
                    )
            except Exception:
                await connector.close(fast=True)
                await asyncio.sleep(0.5)
                raise

        return _subscribe


__aws_sns_sqs = AWSSNSSQSTransport.decorator(AWSSNSSQSTransport.subscribe_handler)
__awssnssqs = AWSSNSSQSTransport.decorator(AWSSNSSQSTransport.subscribe_handler)

aws_sns_sqs_publish = AWSSNSSQSTransport.publish
awssnssqs_publish = AWSSNSSQSTransport.publish
publish = AWSSNSSQSTransport.publish


def aws_sns_sqs(
    topic: Optional[str] = None,
    callback_kwargs: Optional[Union[List, Set, Tuple]] = None,
    competing: Optional[bool] = None,
    queue_name: Optional[str] = None,
    *,
    message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
    message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
    filter_policy: Optional[Union[str, FilterPolicyDictType]] = FILTER_POLICY_DEFAULT,
    visibility_timeout: Optional[int] = VISIBILITY_TIMEOUT_DEFAULT,
    dead_letter_queue_name: Optional[str] = DEAD_LETTER_QUEUE_DEFAULT,
    max_receive_count: Optional[int] = MAX_RECEIVE_COUNT_DEFAULT,
    fifo: bool = False,
    max_number_of_consumed_messages: Optional[int] = MAX_NUMBER_OF_CONSUMED_MESSAGES,
    **kwargs: Any,
) -> Callable:
    return cast(
        Callable,
        __aws_sns_sqs(
            topic=topic,
            callback_kwargs=callback_kwargs,
            competing=competing,
            queue_name=queue_name,
            message_envelope=message_envelope,
            message_protocol=message_protocol,
            filter_policy=filter_policy,
            visibility_timeout=visibility_timeout,
            dead_letter_queue_name=dead_letter_queue_name,
            max_receive_count=max_receive_count,
            fifo=fifo,
            max_number_of_consumed_messages=max_number_of_consumed_messages,
            **kwargs,
        ),
    )


def awssnssqs(
    topic: Optional[str] = None,
    callback_kwargs: Optional[Union[List, Set, Tuple]] = None,
    competing: Optional[bool] = None,
    queue_name: Optional[str] = None,
    *,
    message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
    message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
    filter_policy: Optional[Union[str, FilterPolicyDictType]] = FILTER_POLICY_DEFAULT,
    visibility_timeout: Optional[int] = VISIBILITY_TIMEOUT_DEFAULT,
    dead_letter_queue_name: Optional[str] = DEAD_LETTER_QUEUE_DEFAULT,
    max_receive_count: Optional[int] = MAX_RECEIVE_COUNT_DEFAULT,
    fifo: bool = False,
    max_number_of_consumed_messages: Optional[int] = MAX_NUMBER_OF_CONSUMED_MESSAGES,
    **kwargs: Any,
) -> Callable:
    return cast(
        Callable,
        __awssnssqs(
            topic=topic,
            callback_kwargs=callback_kwargs,
            competing=competing,
            queue_name=queue_name,
            message_envelope=message_envelope,
            message_protocol=message_protocol,
            filter_policy=filter_policy,
            visibility_timeout=visibility_timeout,
            dead_letter_queue_name=dead_letter_queue_name,
            max_receive_count=max_receive_count,
            fifo=fifo,
            max_number_of_consumed_messages=max_number_of_consumed_messages,
            **kwargs,
        ),
    )
