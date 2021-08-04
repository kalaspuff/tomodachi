import asyncio
import base64
import binascii
import copy
import decimal
import functools
import hashlib
import inspect
import json
import logging
import re
import sys
import time
import uuid
from typing import Any, Callable, Dict, List, Mapping, Match, Optional, Sequence, Set, Tuple, Union, cast

import aiobotocore
import aiohttp
import aiohttp.client_exceptions
import botocore
import botocore.exceptions
from botocore.parsers import ResponseParserError

from tomodachi.helpers.aiobotocore_connector import ClientConnector
from tomodachi.helpers.dict import merge_dicts
from tomodachi.helpers.execution_context import (
    decrease_execution_context_value,
    increase_execution_context_value,
    set_execution_context,
)
from tomodachi.helpers.middleware import execute_middlewares
from tomodachi.invoker import Invoker

if sys.version_info >= (3, 8):
    from typing import TypedDict, Literal  # isort:skip
else:
    from typing_extensions import TypedDict, Literal  # isort:skip

DRAIN_MESSAGE_PAYLOAD = "__TOMODACHI_DRAIN__cdab4416-1727-4603-87c9-0ff8dddf1f22__"
MESSAGE_ENVELOPE_DEFAULT = "e6fb6007-cf15-4cfd-af2e-1d1683374e70"
MESSAGE_PROTOCOL_DEFAULT = MESSAGE_ENVELOPE_DEFAULT  # deprecated
MESSAGE_TOPIC_PREFIX = "09698c75-832b-470f-8e05-96d2dd8c4853"
MESSAGE_TOPIC_ATTRIBUTES = "dc6c667f-4c22-4a63-85f6-3ea0c7e2db49"
FILTER_POLICY_DEFAULT = "7e68632f-3b39-4293-b5a9-16644cf857a5"

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
    topics: Dict[str, str] = {}
    close_waiter = None

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
        **kwargs: Any,
    ) -> None:
        if message_envelope == MESSAGE_ENVELOPE_DEFAULT and message_protocol != MESSAGE_ENVELOPE_DEFAULT:
            # Fallback if deprecated message_protocol keyword is used
            message_envelope = message_protocol

        message_envelope = (
            getattr(service, "message_envelope", getattr(service, "message_protocol", None))
            if message_envelope == MESSAGE_ENVELOPE_DEFAULT
            else message_envelope
        )

        if not message_attributes:
            message_attributes = {}
        else:
            message_attributes = copy.deepcopy(message_attributes)

        payload = data
        if message_envelope:
            build_message_func = getattr(message_envelope, "build_message", None)
            if build_message_func:
                payload = await build_message_func(
                    service, topic, data, message_attributes=message_attributes, **kwargs
                )

        topic_arn = await cls.create_topic(
            topic,
            service.context,
            topic_prefix,
            attributes=topic_attributes,
            overwrite_attributes=overwrite_topic_attributes,
        )

        async def _publish_message() -> None:
            await cls.publish_message(topic_arn, payload, cast(Dict, message_attributes), service.context)

        if wait:
            await _publish_message()
        else:
            loop: Any = asyncio.get_event_loop()
            loop.create_task(_publish_message())

    @classmethod
    def get_topic_name(cls, topic: str, context: Dict, topic_prefix: Optional[str] = MESSAGE_TOPIC_PREFIX) -> str:
        topic_prefix = (
            context.get("options", {}).get("aws_sns_sqs", {}).get("topic_prefix", "")
            if topic_prefix == MESSAGE_TOPIC_PREFIX
            else (topic_prefix or "")
        )
        if topic_prefix:
            return "{}{}".format(topic_prefix, topic)
        return topic

    @classmethod
    def get_topic_name_without_prefix(
        cls, topic: str, context: Dict, topic_prefix: Optional[str] = MESSAGE_TOPIC_PREFIX
    ) -> str:
        topic_prefix = (
            context.get("options", {}).get("aws_sns_sqs", {}).get("topic_prefix", "")
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

        return re.sub(r"([^a-zA-Z0-9_*#-])", encode, topic)

    @classmethod
    def get_queue_name(
        cls, topic: str, func_name: str, _uuid: str, competing_consumer: Optional[bool], context: Dict
    ) -> str:
        if not competing_consumer:
            queue_name = hashlib.sha256("{}{}{}".format(topic, func_name, _uuid).encode("utf-8")).hexdigest()
        else:
            queue_name = hashlib.sha256(topic.encode("utf-8")).hexdigest()

        if context.get("options", {}).get("aws_sns_sqs", {}).get("queue_name_prefix"):
            return "{}{}".format(context.get("options", {}).get("aws_sns_sqs", {}).get("queue_name_prefix"), queue_name)
        return queue_name

    @classmethod
    def prefix_queue_name(cls, queue_name: str, context: Dict) -> str:
        if context.get("options", {}).get("aws_sns_sqs", {}).get("queue_name_prefix"):
            return "{}{}".format(context.get("options", {}).get("aws_sns_sqs", {}).get("queue_name_prefix"), queue_name)
        return queue_name

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
        **kwargs: Any,
    ) -> Any:
        parser_kwargs = kwargs

        if message_envelope == MESSAGE_ENVELOPE_DEFAULT and message_protocol != MESSAGE_ENVELOPE_DEFAULT:
            # Fallback if deprecated message_protocol keyword is used
            message_envelope = message_protocol

        message_envelope = (
            context.get("message_envelope", context.get("message_protocol"))
            if message_envelope == MESSAGE_ENVELOPE_DEFAULT
            else message_envelope
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

        async def handler(
            payload: Optional[str],
            receipt_handle: Optional[str] = None,
            queue_url: Optional[str] = None,
            message_topic: str = "",
            message_attributes: Optional[Dict] = None,
        ) -> Any:
            if not payload or payload == DRAIN_MESSAGE_PAYLOAD:
                try:
                    await cls.delete_message(receipt_handle, queue_url, context)
                except (Exception, asyncio.CancelledError):
                    pass
                return

            kwargs = dict(original_kwargs)

            message = payload
            message_attributes_values: Dict[
                str, Optional[Union[str, bytes, int, float, bool, List[Optional[Union[str, int, float, bool, object]]]]]
            ] = (cls.transform_message_attributes_from_response(message_attributes) if message_attributes else {})
            message_uuid = None
            message_key = None

            if message_envelope:
                try:
                    parse_message_func = getattr(message_envelope, "parse_message", None)
                    if parse_message_func:
                        if len(parser_kwargs):
                            message, message_uuid, timestamp = await parse_message_func(
                                payload, message_attributes=message_attributes_values, **parser_kwargs
                            )
                        else:
                            message, message_uuid, timestamp = await parse_message_func(payload)
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

                    if _callback_kwargs:
                        if isinstance(message, dict):
                            for k, v in message.items():
                                if k in _callback_kwargs:
                                    kwargs[k] = v
                        if "message" in _callback_kwargs and (
                            not isinstance(message, dict) or "message" not in message
                        ):
                            kwargs["message"] = message
                        if "topic" in _callback_kwargs and (not isinstance(message, dict) or "topic" not in message):
                            kwargs["topic"] = topic
                        if "receipt_handle" in _callback_kwargs and (
                            not isinstance(message, dict) or "receipt_handle" not in message
                        ):
                            kwargs["receipt_handle"] = receipt_handle
                        if "queue_url" in _callback_kwargs and (
                            not isinstance(message, dict) or "queue_url" not in message
                        ):
                            kwargs["queue_url"] = queue_url
                        if "message_attributes" in _callback_kwargs and (
                            not isinstance(message, dict) or "message_attributes" not in message
                        ):
                            kwargs["message_attributes"] = message_attributes_values
                except (Exception, asyncio.CancelledError, BaseException) as e:
                    logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                    if message is not False and not message_uuid:
                        await cls.delete_message(receipt_handle, queue_url, context)
                    elif message is False and message_uuid:
                        pass  # incompatible envelope, should probably delete if old message
                    elif message is False:
                        await cls.delete_message(receipt_handle, queue_url, context)
                    return
            else:
                if _callback_kwargs:
                    if "message" in _callback_kwargs:
                        kwargs["message"] = message
                    if "topic" in _callback_kwargs:
                        kwargs["topic"] = topic
                    if "receipt_handle" in _callback_kwargs:
                        kwargs["receipt_handle"] = receipt_handle
                    if "queue_url" in _callback_kwargs:
                        kwargs["queue_url"] = queue_url
                    if "message_attributes" in _callback_kwargs:
                        kwargs["message_attributes"] = message_attributes_values

                if len(values.args[1:]) and values.args[1] in kwargs:
                    del kwargs[values.args[1]]

            @functools.wraps(func)
            async def routine_func(*a: Any, **kw: Any) -> Any:
                try:
                    if not message_envelope and len(values.args[1:]) and len(values.args[2:]) == len(a):
                        routine = func(*(obj, message, *a))
                    elif not message_envelope and len(values.args[1:]) and len(merge_dicts(kwargs, kw)):
                        routine = func(*(obj, message, *a), **merge_dicts(kwargs, kw))
                    elif len(merge_dicts(kwargs, kw)):
                        routine = func(*(obj, *a), **merge_dicts(kwargs, kw))
                    elif len(values.args[1:]):
                        routine = func(*(obj, message, *a), **kw)
                    else:
                        routine = func(*(obj, *a), **kw)
                except (Exception, asyncio.CancelledError, BaseException) as e:
                    logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                    if issubclass(
                        e.__class__,
                        (
                            AWSSNSSQSInternalServiceError,
                            AWSSNSSQSInternalServiceErrorException,
                            AWSSNSSQSInternalServiceException,
                        ),
                    ):
                        if message_key:
                            del context["_aws_sns_sqs_received_messages"][message_key]
                        return
                    await cls.delete_message(receipt_handle, queue_url, context)
                    return

                if inspect.isawaitable(routine):
                    try:
                        return_value = await routine
                    except (Exception, asyncio.CancelledError, BaseException) as e:
                        logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                        if issubclass(
                            e.__class__,
                            (
                                AWSSNSSQSInternalServiceError,
                                AWSSNSSQSInternalServiceErrorException,
                                AWSSNSSQSInternalServiceException,
                            ),
                        ):
                            if message_key:
                                del context["_aws_sns_sqs_received_messages"][message_key]
                            return
                        await cls.delete_message(receipt_handle, queue_url, context)
                        return
                else:
                    return_value = routine

                await cls.delete_message(receipt_handle, queue_url, context)
                return return_value

            increase_execution_context_value("aws_sns_sqs_current_tasks")
            increase_execution_context_value("aws_sns_sqs_total_tasks")
            return_value = await execute_middlewares(
                func, routine_func, context.get("message_middleware", []), *(obj, message, topic)
            )
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
        context["_aws_sns_sqs_subscribers"].append((topic, competing, queue_name, func, handler, attributes))

        start_func = cls.subscribe(obj, context)
        return (await start_func) if start_func else None

    @staticmethod
    async def create_client(name: str, context: Dict) -> None:
        alias = f"tomodachi.{name}"
        if connector.get_client(alias):
            return

        config_base = context.get("options", {}).get("aws_sns_sqs", context.get("options", {}).get("aws", {}))
        aws_config_base = context.get("options", {}).get("aws", {})

        region_name = (
            config_base.get("aws_region_name", config_base.get("region_name"))
            or aws_config_base.get("aws_region_name", aws_config_base.get("region_name"))
            or None
        )
        aws_secret_access_key = (
            config_base.get("aws_secret_access_key", config_base.get("secret_access_key"))
            or aws_config_base.get("aws_secret_access_key", aws_config_base.get("secret_access_key"))
            or None
        )
        aws_access_key_id = (
            config_base.get("aws_access_key_id", config_base.get("access_key_id"))
            or aws_config_base.get("aws_access_key_id", aws_config_base.get("access_key_id"))
            or None
        )
        endpoint_url = (
            config_base.get("aws_endpoint_urls", config_base.get("endpoint_urls", {})).get(name)
            or config_base.get("aws_{}_endpoint_url".format(name), config_base.get("{}_endpoint_url".format(name)))
            or aws_config_base.get("aws_endpoint_urls", aws_config_base.get("endpoint_urls", {})).get(name)
            or config_base.get("aws_endpoint_url", config_base.get("endpoint_url"))
            or aws_config_base.get("aws_endpoint_url", aws_config_base.get("endpoint_url"))
            or context.get("options", {}).get("aws_endpoint_urls", {}).get(name)
            or None
        )

        credentials = {
            "region_name": region_name,
            "aws_secret_access_key": aws_secret_access_key,
            "aws_access_key_id": aws_access_key_id,
            "endpoint_url": endpoint_url,
        }

        connector.setup_credentials(alias, credentials)

        logging.getLogger("botocore.vendored.requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)

        try:
            await connector.create_client(alias, service_name=name)
        except (botocore.exceptions.PartialCredentialsError, botocore.exceptions.NoRegionError) as e:
            error_message = str(e)
            logging.getLogger("transport.aws_sns_sqs").warning(
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
    ) -> str:
        if not cls.topics:
            cls.topics = {}
        if cls.topics.get(topic):
            topic_arn = cls.topics.get(topic)
            if topic_arn and isinstance(topic_arn, str):
                return topic_arn

        if not connector.get_client("tomodachi.sns"):
            await cls.create_client("sns", context)

        config_base = context.get("options", {}).get("aws_sns_sqs", context.get("options", {}).get("aws", {}))
        aws_config_base = context.get("options", {}).get("aws", {})

        sns_kms_master_key_id: Optional[str] = None
        for config_value in (
            config_base.get("aws_sns_kms_master_key_id"),
            config_base.get("sns_kms_master_key_id"),
            aws_config_base.get("aws_sns_kms_master_key_id"),
            aws_config_base.get("sns_kms_master_key_id"),
            aws_config_base.get("aws_kms_master_key_id"),
            aws_config_base.get("kms_master_key_id"),
            config_base.get("aws_kms_master_key_id"),
            config_base.get("kms_master_key_id"),
        ):
            if config_value is not None:
                if isinstance(config_value, str) and config_value == "":
                    sns_kms_master_key_id = ""
                    break
                elif isinstance(config_value, bool) and config_value is False:
                    sns_kms_master_key_id = ""
                    break
                elif isinstance(config_value, str) and config_value:
                    sns_kms_master_key_id = config_value
                    break
                else:
                    raise ValueError(
                        "Bad value for aws_sns_sqs option sns_kms_master_key_id: {}".format(str(config_value))
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

        if sns_kms_master_key_id is not None and "KmsMasterKeyId" not in topic_attributes:
            topic_attributes["KmsMasterKeyId"] = sns_kms_master_key_id

        update_attributes = True if topic_attributes else False
        topic_arn = None

        try:
            async with connector("tomodachi.sns", service_name="sns") as client:
                response = await asyncio.wait_for(
                    client.create_topic(
                        Name=cls.encode_topic(cls.get_topic_name(topic, context, topic_prefix)),
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
                    logging.getLogger("transport.aws_sns_sqs").info(
                        "SNS topic attribute 'KmsMasterKeyId' on SNS topic '{}' will be updated to disable server-side encryption".format(
                            topic_arn
                        )
                    )
                    update_attributes = True
        except (botocore.exceptions.NoCredentialsError, aiohttp.client_exceptions.ClientOSError) as e:
            error_message = str(e)
            logging.getLogger("transport.aws_sns_sqs").warning(
                "Unable to connect [sns] to AWS ({})".format(error_message)
            )
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
                                Name=cls.encode_topic(cls.get_topic_name(topic, context, topic_prefix))
                            ),
                            timeout=40,
                        )
                        topic_arn = response.get("TopicArn")
                except (
                    Exception,
                    asyncio.TimeoutError,
                ) as e2:
                    error_message2 = str(e) if not isinstance(e, asyncio.TimeoutError) else "Network timeout"
                    logging.getLogger("transport.aws_sns_sqs").warning(
                        "Unable to create topic [sns] on AWS ({})".format(error_message2)
                    )
                    raise AWSSNSSQSException(error_message2, log_level=context.get("log_level")) from e2

                logging.getLogger("transport.aws_sns_sqs").info(
                    "Already existing SNS topic '{}' has different topic attributes".format(topic_arn)
                )
            else:
                logging.getLogger("transport.aws_sns_sqs").warning(
                    "Unable to create topic [sns] on AWS ({})".format(error_message)
                )
                raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

        if update_attributes and topic_attributes and topic_arn and not overwrite_attributes:
            logging.getLogger("transport.aws_sns_sqs").warning(
                "Will not overwrite existing attributes on SNS topic '{}'".format(topic_arn)
            )
            update_attributes = False

        if update_attributes and topic_attributes and topic_arn:
            for attribute_name, attribute_value in topic_attributes.items():
                try:
                    logging.getLogger("transport.aws_sns_sqs").info(
                        "Updating '{}' attribute on SNS topic '{}'".format(attribute_name, topic_arn)
                    )
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
                    logging.getLogger("transport.aws_sns_sqs").warning(
                        "Unable to create topic [sns] on AWS ({})".format(error_message)
                    )
                    raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

        if not topic_arn or not isinstance(topic_arn, str):
            error_message = "Missing ARN in response"
            logging.getLogger("transport.aws_sns_sqs").warning(
                "Unable to create topic [sns] on AWS ({})".format(error_message)
            )
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

        cls.topics[topic] = topic_arn

        return topic_arn

    @staticmethod
    def transform_message_attributes_from_response(
        message_attributes: Dict,
    ) -> Dict[str, Optional[Union[str, bytes, int, float, bool, List[Optional[Union[str, int, float, bool, object]]]]]]:
        result: Dict[
            str, Optional[Union[str, bytes, int, float, bool, List[Optional[Union[str, int, float, bool, object]]]]]
        ] = {}

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
    async def publish_message(cls, topic_arn: str, message: Any, message_attributes: Dict, context: Dict) -> str:
        if not connector.get_client("tomodachi.sns"):
            await cls.create_client("sns", context)

        message_attribute_values = cls.transform_message_attributes_to_botocore(message_attributes)

        response = {}
        for retry in range(1, 4):
            try:
                async with connector("tomodachi.sns", service_name="sns") as client:
                    response = await asyncio.wait_for(
                        client.publish(TopicArn=topic_arn, Message=message, MessageAttributes=message_attribute_values),
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
                    logging.getLogger("transport.aws_sns_sqs").warning(
                        "Unable to publish message [sns] on AWS ({})".format(error_message)
                    )
                    raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e
                continue
            break

        message_id = response.get("MessageId")
        if not message_id or not isinstance(message_id, str):
            error_message = "Missing MessageId in response"
            logging.getLogger("transport.aws_sns_sqs").warning(
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
                    logging.getLogger("transport.aws_sns_sqs").warning(
                        "Unable to delete message [sqs] on AWS ({})".format(error_message)
                    )
                except asyncio.TimeoutError as e:
                    if retry >= 4:
                        error_message = "Network timeout"
                        logging.getLogger("transport.aws_sns_sqs").warning(
                            "Unable to delete message [sqs] on AWS ({})".format(error_message)
                        )
                        raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e
                    continue
                break

        await _delete_message()

    @classmethod
    async def create_queue(cls, queue_name: str, context: Dict) -> Tuple[str, str]:
        if not connector.get_client("tomodachi.sqs"):
            await cls.create_client("sqs", context)

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
            logging.getLogger("transport.aws_sns_sqs").warning(
                "Unable to connect [sqs] to AWS ({})".format(error_message)
            )
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get("log_level")) from e
        except botocore.exceptions.ClientError:
            pass

        if not queue_url:
            try:
                async with connector("tomodachi.sqs", service_name="sqs") as client:
                    response = await client.create_queue(QueueName=queue_name)
                    queue_url = response.get("QueueUrl")
            except (
                botocore.exceptions.NoCredentialsError,
                botocore.exceptions.PartialCredentialsError,
                aiohttp.client_exceptions.ClientOSError,
            ) as e:
                error_message = str(e)
                logging.getLogger("transport.aws_sns_sqs").warning(
                    "Unable to connect [sqs] to AWS ({})".format(error_message)
                )
                raise AWSSNSSQSConnectionException(error_message, log_level=context.get("log_level")) from e
            except botocore.exceptions.ClientError as e:
                error_message = str(e)
                logging.getLogger("transport.aws_sns_sqs").warning(
                    "Unable to create queue [sqs] on AWS ({})".format(error_message)
                )
                raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

        if not queue_url:
            error_message = "Missing Queue URL in response"
            logging.getLogger("transport.aws_sns_sqs").warning(
                "Unable to create queue [sqs] on AWS ({})".format(error_message)
            )
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

        try:
            async with connector("tomodachi.sqs", service_name="sqs") as client:
                response = await client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            logging.getLogger("transport.aws_sns_sqs").warning(
                "Unable to get queue attributes [sqs] on AWS ({})".format(error_message)
            )
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

        queue_arn = response.get("Attributes", {}).get("QueueArn")
        if not queue_arn:
            error_message = "Missing ARN in response"
            logging.getLogger("transport.aws_sns_sqs").warning(
                "Unable to get queue attributes [sqs] on AWS ({})".format(error_message)
            )
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

        return queue_url, queue_arn

    @classmethod
    def generate_queue_policy(cls, queue_arn: str, topic_arn_list: Union[List, Tuple], context: Dict) -> Dict:
        if len(topic_arn_list) == 1:
            if context.get("options", {}).get("aws_sns_sqs", {}).get("queue_policy"):
                source_arn = context.get("options", {}).get("aws_sns_sqs", {}).get("queue_policy")
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
            if context.get("options", {}).get("aws_sns_sqs", {}).get("queue_policy"):
                source_arn = context.get("options", {}).get("aws_sns_sqs", {}).get("queue_policy")
            if context.get("options", {}).get("aws_sns_sqs", {}).get("wildcard_queue_policy"):
                source_arn = context.get("options", {}).get("aws_sns_sqs", {}).get("wildcard_queue_policy")

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
        attributes: Optional[Dict[str, Union[str, bool]]] = None,
    ) -> Optional[List]:
        if not connector.get_client("tomodachi.sns"):
            await cls.create_client("sns", context)

        pattern = r"^arn:aws:sns:[^:]+:[^:]+:{}$".format(
            cls.encode_topic(cls.get_topic_name(topic, context))
            .replace(cls.encode_topic("*"), "((?!{}).)*".format(cls.encode_topic(".")))
            .replace(cls.encode_topic("#"), ".*")
        )
        compiled_pattern = re.compile(pattern)

        next_token = False
        topic_arn_list = None
        while next_token is not None:
            try:
                async with connector("tomodachi.sns", service_name="sns") as client:
                    if next_token:
                        response = await client.list_topics(NextToken=next_token)
                    else:
                        response = await client.list_topics()
            except botocore.exceptions.ClientError as e:
                error_message = str(e)
                logging.getLogger("transport.aws_sns_sqs").warning(
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
                topic_arn_list, queue_arn, queue_url, context, queue_policy=queue_policy, attributes=attributes
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
    ) -> List:
        if not connector.get_client("tomodachi.sns"):
            await cls.create_client("sns", context)

        if not connector.get_client("tomodachi.sqs"):
            await cls.create_client("sqs", context)

        if not queue_policy:
            queue_policy = cls.generate_queue_policy(queue_arn, topic_arn_list, context)

        if not queue_policy or not isinstance(queue_policy, dict):
            raise Exception("SQS policy is invalid")

        config_base = context.get("options", {}).get("aws_sns_sqs", context.get("options", {}).get("aws", {}))
        aws_config_base = context.get("options", {}).get("aws", {})

        sqs_kms_master_key_id: Optional[str] = None
        for config_value in (
            config_base.get("aws_sqs_kms_master_key_id"),
            config_base.get("sqs_kms_master_key_id"),
            aws_config_base.get("aws_sqs_kms_master_key_id"),
            aws_config_base.get("sqs_kms_master_key_id"),
            aws_config_base.get("aws_kms_master_key_id"),
            aws_config_base.get("kms_master_key_id"),
            config_base.get("aws_kms_master_key_id"),
            config_base.get("kms_master_key_id"),
        ):
            if config_value is not None:
                if isinstance(config_value, str) and config_value == "":
                    sqs_kms_master_key_id = ""
                    break
                elif isinstance(config_value, bool) and config_value is False:
                    sqs_kms_master_key_id = ""
                    break
                elif isinstance(config_value, str) and config_value:
                    sqs_kms_master_key_id = config_value
                    break
                else:
                    raise ValueError(
                        "Bad value for aws_sns_sqs option sqs_kms_master_key_id: {}".format(str(config_value))
                    )

        sqs_kms_data_key_reuse_period_option = (
            config_base.get(
                "aws_sqs_kms_data_key_reuse_period",
                config_base.get(
                    "sqs_kms_data_key_reuse_period",
                    config_base.get("aws_kms_data_key_reuse_period", config_base.get("kms_data_key_reuse_period")),
                ),
            )
            or aws_config_base.get(
                "aws_sqs_kms_data_key_reuse_period",
                aws_config_base.get(
                    "sqs_kms_data_key_reuse_period",
                    aws_config_base.get(
                        "aws_kms_data_key_reuse_period", aws_config_base.get("kms_data_key_reuse_period")
                    ),
                ),
            )
            or None
        )
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
        current_kms_master_key_id = None
        current_kms_data_key_reuse_period_seconds = None

        visibility_timeout = None  # not implemented yet
        message_retention_period = None  # not implemented yet

        try:
            async with connector("tomodachi.sqs", service_name="sqs") as sqs_client:
                response = await sqs_client.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=[
                        "Policy",
                        "VisibilityTimeout",
                        "MessageRetentionPeriod",
                        "KmsMasterKeyId",
                        "KmsDataKeyReusePeriodSeconds",
                    ],
                )
                current_queue_attributes = response.get("Attributes", {})
                current_queue_policy = json.loads(current_queue_attributes.get("Policy") or "{}")
                current_visibility_timeout = current_queue_attributes.get("VisibilityTimeout")
                if current_visibility_timeout:
                    current_visibility_timeout = int(current_visibility_timeout)
                current_message_retention_period = current_queue_attributes.get("MessageRetentionPeriod")
                if current_message_retention_period:
                    current_message_retention_period = int(current_message_retention_period)
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
            message_retention_period
            and current_message_retention_period
            and message_retention_period != current_message_retention_period
        ):
            queue_attributes["MessageRetentionPeriod"] = str(
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
                    logging.getLogger("transport.aws_sns_sqs").info(
                        "Updating '{}' attribute on SQS queue '{}'".format(attribute_name, queue_arn)
                    )

            try:
                async with connector("tomodachi.sqs", service_name="sqs") as sqs_client:
                    response = await sqs_client.set_queue_attributes(QueueUrl=queue_url, Attributes=queue_attributes)
            except botocore.exceptions.ClientError as e:
                error_message = str(e)
                logging.getLogger("transport.aws_sns_sqs").warning(
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
                        logging.getLogger("transport.aws_sns_sqs").info(
                            "SNS subscription for topic ARN '{}' and queue ARN '{}' previously had different attributes".format(
                                topic_arn, queue_arn
                            )
                        )
                    else:
                        logging.getLogger("transport.aws_sns_sqs").warning(
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
                    logging.getLogger("transport.aws_sns_sqs").warning(
                        "Unable to subscribe to topic [sns] on AWS ({})".format(error_message)
                    )
                    raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

            if not subscription_arn:
                error_message = "Missing Subscription ARN in response"
                logging.getLogger("transport.aws_sns_sqs").warning(
                    "Unable to subscribe to topic [sns] on AWS ({})".format(error_message)
                )
                raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

            if update_attributes and attributes:
                for attribute_name, attribute_value in attributes.items():
                    try:
                        if "000000000000" not in subscription_arn:
                            logging.getLogger("transport.aws_sns_sqs").info(
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
                        logging.getLogger("transport.aws_sns_sqs").warning(
                            "Unable to subscribe to topic [sns] on AWS ({})".format(error_message)
                        )
                        raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

            subscription_arn_list.append(subscription_arn)

        return subscription_arn_list

    @classmethod
    async def consume_queue(cls, obj: Any, context: Dict, handler: Callable, queue_url: str) -> None:
        max_number_of_messages = 10
        wait_time_seconds = 20

        if not connector.get_client("tomodachi.sqs"):
            await cls.create_client("sqs", context)

        if not cls.close_waiter:
            cls.close_waiter = asyncio.Future()

        stop_waiter: asyncio.Future = asyncio.Future()
        start_waiter: asyncio.Future = asyncio.Future()

        async def receive_messages() -> None:
            await start_waiter

            async def _receive_wrapper() -> None:
                def callback(
                    payload: Optional[str],
                    receipt_handle: Optional[str],
                    queue_url: Optional[str],
                    message_topic: str,
                    message_attributes: Dict,
                ) -> Callable:
                    async def _callback() -> None:
                        await handler(payload, receipt_handle, queue_url, message_topic, message_attributes)

                    return _callback

                is_disconnected = False

                while cls.close_waiter and not cls.close_waiter.done():
                    futures = []

                    try:
                        try:
                            async with connector("tomodachi.sqs", service_name="sqs") as client:
                                response = await asyncio.wait_for(
                                    client.receive_message(
                                        QueueUrl=queue_url,
                                        WaitTimeSeconds=wait_time_seconds,
                                        MaxNumberOfMessages=max_number_of_messages,
                                    ),
                                    timeout=40,
                                )
                            if is_disconnected:
                                is_disconnected = False
                                logging.getLogger("transport.aws_sns_sqs").warning("Reconnected - receiving messages")
                        except (aiohttp.client_exceptions.ServerDisconnectedError, RuntimeError) as e:
                            if not is_disconnected:
                                is_disconnected = True
                                error_message = str(e) if e and str(e) not in ["", "None"] else "Server disconnected"
                                logging.getLogger("transport.aws_sns_sqs").warning(
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
                                logging.getLogger("transport.aws_sns_sqs").warning(
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
                                    logging.getLogger("transport.aws_sns_sqs").warning(
                                        "Reconnected - receiving messages"
                                    )
                                try:
                                    context["_aws_sns_sqs_subscribed"] = False
                                    cls.topics = {}
                                    func = await cls.subscribe(obj, context)
                                    await func()
                                except Exception:
                                    pass
                                await asyncio.sleep(20)
                                continue
                            if not is_disconnected:
                                logging.getLogger("transport.aws_sns_sqs").warning(
                                    "Unable to receive message from queue [sqs] on AWS ({})".format(error_message)
                                )
                            if isinstance(e, (asyncio.TimeoutError, aiohttp.client_exceptions.ClientConnectorError)):
                                is_disconnected = True
                            await asyncio.sleep(1)
                            continue
                        except Exception as e:
                            error_message = str(e)
                            logging.getLogger("transport.aws_sns_sqs").warning(
                                "Unexpected error while receiving message from queue [sqs] on AWS ({})".format(
                                    error_message
                                )
                            )
                            await asyncio.sleep(1)
                            continue
                        except BaseException as e:
                            error_message = str(e)
                            logging.getLogger("transport.aws_sns_sqs").warning(
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
                                message_topic = (
                                    cls.get_topic_name_without_prefix(
                                        cls.decode_topic(cls.get_topic_from_arn(message_body.get("TopicArn"))), context
                                    )
                                    if message_body.get("TopicArn")
                                    else ""
                                )
                            except ValueError:
                                # Malformed SQS message, not in SNS format and should be discarded
                                await cls.delete_message(receipt_handle, queue_url, context)
                                logging.getLogger("transport.aws_sns_sqs").warning("Discarded malformed message")
                                continue

                            payload = message_body.get("Message")
                            message_attributes = message_body.get("MessageAttributes", {})

                            futures.append(
                                callback(payload, receipt_handle, queue_url, message_topic, message_attributes)
                            )
                    except asyncio.CancelledError:
                        continue
                    except BaseException:
                        continue

                    tasks = [asyncio.ensure_future(func()) for func in futures if func]
                    if not tasks:
                        continue
                    try:
                        await asyncio.shield(asyncio.wait(tasks))
                    except asyncio.CancelledError:
                        await asyncio.wait(tasks)
                        await asyncio.sleep(1)

                if not stop_waiter.done():
                    stop_waiter.set_result(None)

            task = None
            while True:
                if task and cls.close_waiter and not cls.close_waiter.done():
                    logging.getLogger("transport.aws_sns_sqs").warning(
                        "Resuming message receiving after trying to recover from fatal error"
                    )
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
                        logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                    sleep_task: asyncio.Future = asyncio.ensure_future(asyncio.sleep(10))
                    await asyncio.wait([sleep_task, cls.close_waiter], return_when=asyncio.FIRST_COMPLETED)
                    if not sleep_task.done():
                        sleep_task.cancel()

            if task and not task.done():
                task.cancel()
                await task

        loop: Any = asyncio.get_event_loop()

        stop_method = getattr(obj, "_stop_service", None)

        async def stop_service(*args: Any, **kwargs: Any) -> None:
            if cls.close_waiter and not cls.close_waiter.done():
                logging.getLogger("transport.aws_sns_sqs").warning("Draining message pool - awaiting running tasks")
                cls.close_waiter.set_result(None)

                if not start_waiter.done():
                    start_waiter.set_result(None)
                await stop_waiter
                if stop_method:
                    await stop_method(*args, **kwargs)
                await connector.close()
            else:
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

        loop.create_task(receive_messages())

    @classmethod
    async def subscribe(cls, obj: Any, context: Dict) -> Optional[Callable]:
        if context.get("_aws_sns_sqs_subscribed"):
            return None
        context["_aws_sns_sqs_subscribed"] = True

        async def _subscribe() -> None:
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
            ) -> str:
                _uuid = obj.uuid

                if queue_name and competing_consumer is False:
                    raise AWSSNSSQSException(
                        "Queue with predefined queue name must be competing", log_level=context.get("log_level")
                    )

                if queue_name is None:
                    queue_name = cls.get_queue_name(
                        cls.encode_topic(topic or ""), func.__name__, _uuid, competing_consumer, context
                    )
                else:
                    queue_name = cls.prefix_queue_name(queue_name, context)

                queue_url, queue_arn = await cls.create_queue(queue_name, context)

                if topic:
                    if re.search(r"([*#])", topic):
                        await cls.subscribe_wildcard_topic(topic, queue_arn, queue_url, context, attributes=attributes)
                    else:
                        topic_arn = await cls.create_topic(topic, context)
                        await cls.subscribe_topics((topic_arn,), queue_arn, queue_url, context, attributes=attributes)

                return queue_url

            try:
                for topic, competing, queue_name, func, handler, attributes in context.get(
                    "_aws_sns_sqs_subscribers", []
                ):
                    queue_url = await setup_queue(
                        func, topic=topic, queue_name=queue_name, competing_consumer=competing, attributes=attributes
                    )
                    await cls.consume_queue(obj, context, handler, queue_url=queue_url)
            except Exception:
                await connector.close(fast=True)
                await asyncio.sleep(0.5)
                raise

        return _subscribe


__aws_sns_sqs = AWSSNSSQSTransport.decorator(AWSSNSSQSTransport.subscribe_handler)
aws_sns_sqs_publish = AWSSNSSQSTransport.publish
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
            **kwargs,
        ),
    )
