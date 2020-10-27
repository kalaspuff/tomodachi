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
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Match, Optional, Set, Tuple, Union, cast

import aiobotocore
import aiohttp
import botocore
from botocore.parsers import ResponseParserError

from tomodachi.helpers.dict import merge_dicts
from tomodachi.helpers.execution_context import (
    decrease_execution_context_value,
    increase_execution_context_value,
    set_execution_context,
)
from tomodachi.helpers.middleware import execute_middlewares
from tomodachi.invoker import Invoker

DRAIN_MESSAGE_PAYLOAD = "__TOMODACHI_DRAIN__cdab4416-1727-4603-87c9-0ff8dddf1f22__"
MESSAGE_ENVELOPE_DEFAULT = "e6fb6007-cf15-4cfd-af2e-1d1683374e70"
MESSAGE_PROTOCOL_DEFAULT = MESSAGE_ENVELOPE_DEFAULT  # deprecated
MESSAGE_TOPIC_PREFIX = "09698c75-832b-470f-8e05-96d2dd8c4853"
FILTER_POLICY_DEFAULT = "7e68632f-3b39-4293-b5a9-16644cf857a5"


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
    clients = None
    clients_creation_time = None
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

        topic_arn = await cls.create_topic(cls, topic, service.context, topic_prefix)

        async def _publish_message() -> None:
            await cls.publish_message(cls, topic_arn, payload, cast(Dict, message_attributes), service.context)

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
    def get_queue_name(cls, topic: str, func_name: str, _uuid: str, competing_consumer: bool, context: Dict) -> str:
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

    async def subscribe_handler(
        cls: Any,
        obj: Any,
        context: Dict,
        func: Any,
        topic: str,
        callback_kwargs: Optional[Union[List, Set, Tuple]] = None,
        competing: Optional[bool] = None,
        queue_name: Optional[str] = None,
        *,
        message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
        message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
        filter_policy: Optional[
            Union[str, Dict[str, List[Union[str, Dict[str, Union[bool, List]]]]]]
        ] = FILTER_POLICY_DEFAULT,
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
                    await cls.delete_message(cls, receipt_handle, queue_url, context)
                except Exception:
                    pass
                return

            kwargs = dict(original_kwargs)

            message = payload
            message_attributes_values: Dict[
                str, Union[str, bytes, int, float, List[Optional[Union[str, int, float, bool]]]]
            ] = (cls.transform_message_attributes_from_response(cls, message_attributes) if message_attributes else {})
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
                except Exception as e:
                    logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                    if message is not False and not message_uuid:
                        await cls.delete_message(cls, receipt_handle, queue_url, context)
                    elif message is False and message_uuid:
                        pass  # incompatible envelope, should probably delete if old message
                    elif message is False:
                        await cls.delete_message(cls, receipt_handle, queue_url, context)
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
                except Exception as e:
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
                    await cls.delete_message(cls, receipt_handle, queue_url, context)
                    return

                if isinstance(routine, Awaitable):
                    try:
                        return_value = await routine
                    except Exception as e:
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
                        await cls.delete_message(cls, receipt_handle, queue_url, context)
                        return
                else:
                    return_value = routine

                await cls.delete_message(cls, receipt_handle, queue_url, context)
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

        start_func = cls.subscribe(cls, obj, context)
        return (await start_func) if start_func else None

    async def create_client(cls: Any, name: str, context: Dict) -> None:
        logging.getLogger("botocore.vendored.requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)

        if not cls.clients:
            cls.clients = {}
            cls.clients_creation_time = {}
        asyncio.get_event_loop()
        session = aiobotocore.get_session()

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

        try:
            if cls.clients_creation_time.get(name) and cls.clients_creation_time[name] + 30 > time.time():
                return
            create_client_func = session._create_client if hasattr(session, "_create_client") else session.create_client
            client = create_client_func(
                name,
                region_name=region_name,
                aws_secret_access_key=aws_secret_access_key,
                aws_access_key_id=aws_access_key_id,
                endpoint_url=endpoint_url,
            )
            if isinstance(client, Awaitable):
                cls.clients[name] = await client
            else:
                cls.clients[name] = client
            cls.clients_creation_time[name] = time.time()
        except (botocore.exceptions.PartialCredentialsError, botocore.exceptions.NoRegionError) as e:
            error_message = str(e)
            logging.getLogger("transport.aws_sns_sqs").warning(
                "Invalid credentials [{}] to AWS ({})".format(name, error_message)
            )
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get("log_level")) from e

    async def create_topic(
        cls: Any, topic: str, context: Dict, topic_prefix: Optional[str] = MESSAGE_TOPIC_PREFIX
    ) -> str:
        if not cls.topics:
            cls.topics = {}
        if cls.topics.get(topic):
            topic_arn = cls.topics.get(topic)
            if topic_arn and isinstance(topic_arn, str):
                return topic_arn

        if not cls.clients or not cls.clients.get("sns"):
            await cls.create_client(cls, "sns", context)
        client = cls.clients.get("sns")

        try:
            response = await asyncio.wait_for(
                client.create_topic(Name=cls.encode_topic(cls.get_topic_name(topic, context, topic_prefix))), timeout=30
            )
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
            logging.getLogger("transport.aws_sns_sqs").warning(
                "Unable to create topic [sns] on AWS ({})".format(error_message)
            )
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

        topic_arn = response.get("TopicArn")
        if not topic_arn or not isinstance(topic_arn, str):
            error_message = "Missing ARN in response"
            logging.getLogger("transport.aws_sns_sqs").warning(
                "Unable to create topic [sns] on AWS ({})".format(error_message)
            )
            raise AWSSNSSQSException(error_message, log_level=context.get("log_level"))

        cls.topics[topic] = topic_arn

        return topic_arn

    def transform_message_attributes_from_response(
        cls, message_attributes: Dict
    ) -> Dict[str, Union[str, bytes, int, float, List[Optional[Union[str, int, float, bool]]]]]:
        result: Dict[str, Union[str, bytes, int, float, List[Optional[Union[str, int, float, bool]]]]] = {}

        for name, values in message_attributes.items():
            value = values["Value"]
            if values["Type"] == "String":
                result[name] = value
            elif values["Type"] == "Number":
                result[name] = int(value) if "." not in value else float(value)
            elif values["Type"] == "Binary":
                result[name] = base64.b64decode(value)
            elif values["Type"] == "String.Array":
                result[name] = cast(List[Optional[Union[str, int, float, bool]]], json.loads(value))

        return result

    def transform_message_attributes_to_botocore(
        cls, message_attributes: Dict
    ) -> Dict[str, Dict[str, Union[str, bytes]]]:
        result: Dict[str, Dict[str, Union[str, bytes]]] = {}

        for name, value in message_attributes.items():
            if isinstance(value, str):
                result[name] = {"DataType": "String", "StringValue": value}
            elif isinstance(value, (int, float, decimal.Decimal)):
                result[name] = {"DataType": "Number", "StringValue": str(value)}
            elif isinstance(value, bytes):
                result[name] = {"DataType": "Binary", "BinaryValue": value}
            elif isinstance(value, list):
                result[name] = {"DataType": "String.Array", "StringValue": json.dumps(value)}
            else:
                result[name] = {"DataType": "String", "StringValue": str(value)}

        return result

    async def publish_message(cls: Any, topic_arn: str, message: Any, message_attributes: Dict, context: Dict) -> str:
        if not cls.clients or not cls.clients.get("sns"):
            await cls.create_client(cls, "sns", context)

        message_attribute_values = cls.transform_message_attributes_to_botocore(cls, message_attributes)

        for retry in range(1, 4):
            client = cls.clients.get("sns")
            try:
                response = await asyncio.wait_for(
                    client.publish(TopicArn=topic_arn, Message=message, MessageAttributes=message_attribute_values),
                    timeout=30,
                )
            except (aiohttp.client_exceptions.ServerDisconnectedError, RuntimeError) as e:
                await asyncio.sleep(1)
                try:
                    task = client.close()
                    if getattr(task, "_coro", None):
                        task = task._coro
                    await asyncio.wait([asyncio.ensure_future(task)], timeout=3)
                except Exception:
                    pass
                await cls.create_client(cls, "sns", context)
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

    async def delete_message(cls: Any, receipt_handle: Optional[str], queue_url: Optional[str], context: Dict) -> None:
        if not receipt_handle:
            return
        if not cls.clients or not cls.clients.get("sqs"):
            await cls.create_client(cls, "sqs", context)

        async def _delete_message() -> None:
            for retry in range(1, 4):
                if not cls.clients or not cls.clients.get("sqs"):
                    await cls.create_client(cls, "sqs", context)
                client = cls.clients.get("sqs")
                try:
                    await asyncio.wait_for(
                        client.delete_message(ReceiptHandle=receipt_handle, QueueUrl=queue_url), timeout=30
                    )
                except (aiohttp.client_exceptions.ServerDisconnectedError, RuntimeError) as e:
                    await asyncio.sleep(1)
                    try:
                        task = client.close()
                        if getattr(task, "_coro", None):
                            task = task._coro
                        await asyncio.wait([asyncio.ensure_future(task)], timeout=3)
                    except Exception:
                        pass
                    await cls.create_client(cls, "sqs", context)
                    if retry >= 3:
                        raise e
                    continue
                except botocore.exceptions.ClientError as e:
                    error_message = str(e)
                    logging.getLogger("transport.aws_sns_sqs").warning(
                        "Unable to delete message [sqs] on AWS ({})".format(error_message)
                    )
                except asyncio.TimeoutError as e:
                    if retry >= 3:
                        error_message = "Network timeout"
                        logging.getLogger("transport.aws_sns_sqs").warning(
                            "Unable to delete message [sqs] on AWS ({})".format(error_message)
                        )
                        raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e
                    continue

        await _delete_message()

    async def create_queue(cls: Any, queue_name: str, context: Dict) -> Tuple[str, str]:
        if not cls.clients or not cls.clients.get("sqs"):
            await cls.create_client(cls, "sqs", context)
        client = cls.clients.get("sqs")

        queue_url = ""
        try:
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
    def generate_queue_policy(cls, queue_arn: str, topic_arn_list: List, context: Dict) -> Dict:
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

    async def subscribe_wildcard_topic(
        cls: Any,
        topic: str,
        queue_arn: str,
        queue_url: str,
        context: Dict,
        attributes: Optional[Dict[str, Union[str, bool]]] = None,
    ) -> Optional[List]:
        if not cls.clients or not cls.clients.get("sns"):
            await cls.create_client(cls, "sns", context)
        client = cls.clients.get("sns")

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
                cls, topic_arn_list, queue_arn, queue_url, context, queue_policy=queue_policy, attributes=attributes
            )

        return None

    async def subscribe_topics(
        cls: Any,
        topic_arn_list: List,
        queue_arn: str,
        queue_url: str,
        context: Dict,
        queue_policy: Optional[Dict] = None,
        attributes: Optional[Dict[str, Union[str, bool]]] = None,
    ) -> List:
        if not cls.clients or not cls.clients.get("sns"):
            await cls.create_client(cls, "sns", context)
        client = cls.clients.get("sns")

        if not cls.clients or not cls.clients.get("sqs"):
            await cls.create_client(cls, "sqs", context)
        sqs_client = cls.clients.get("sqs")

        if not queue_policy:
            queue_policy = cls.generate_queue_policy(queue_arn, topic_arn_list, context)

        if not queue_policy or not isinstance(queue_policy, dict):
            raise Exception("SQS policy is invalid")

        current_queue_policy = {}
        current_visibility_timeout = None
        visibility_timeout = None
        message_retention_period = None
        try:
            response = await sqs_client.get_queue_attributes(
                QueueUrl=queue_url, AttributeNames=["Policy", "VisibilityTimeout", "MessageRetentionPeriod"]
            )
            current_queue_attributes = response.get("Attributes", {})
            current_queue_policy = json.loads(current_queue_attributes.get("Policy") or "{}")
            current_visibility_timeout = current_queue_attributes.get("VisibilityTimeout")
            current_message_retention_period = current_queue_attributes.get("MessageRetentionPeriod")
        except botocore.exceptions.ClientError:
            pass

        queue_attributes = {}

        if not current_queue_policy or [{**x, "Sid": ""} for x in current_queue_policy.get("Statement", [])] != [
            {**x, "Sid": ""} for x in queue_policy.get("Statement", [])
        ]:
            queue_attributes["Policy"] = json.dumps(queue_policy)

        if visibility_timeout and visibility_timeout != current_visibility_timeout:
            queue_attributes["VisibilityTimeout"] = visibility_timeout  # specified in seconds

        if message_retention_period and message_retention_period != current_message_retention_period:
            queue_attributes["MessageRetentionPeriod"] = message_retention_period  # specified in seconds

        if queue_attributes:
            try:
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
                    response = await client.subscribe(
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
                    response = await client.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)
                    subscription_arn = response.get("SubscriptionArn")
                except botocore.exceptions.ClientError as e:
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
                        await client.set_subscription_attributes(
                            SubscriptionArn=subscription_arn,
                            AttributeName=attribute_name,
                            AttributeValue=attribute_value,
                        )
                    except botocore.exceptions.ClientError as e:
                        logging.getLogger("transport.aws_sns_sqs").warning(
                            "Unable to subscribe to topic [sns] on AWS ({})".format(error_message)
                        )
                        raise AWSSNSSQSException(error_message, log_level=context.get("log_level")) from e

            subscription_arn_list.append(subscription_arn)

        return subscription_arn_list

    async def consume_queue(cls: Any, obj: Any, context: Dict, handler: Callable, queue_url: str) -> None:
        if not cls.clients or not cls.clients.get("sqs"):
            await cls.create_client(cls, "sqs", context)

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

                client = cls.clients.get("sqs")
                is_disconnected = False

                while not cls.close_waiter.done():
                    futures = []

                    try:
                        try:
                            response = await asyncio.wait_for(
                                client.receive_message(QueueUrl=queue_url, WaitTimeSeconds=20, MaxNumberOfMessages=10),
                                timeout=30,
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
                            await asyncio.sleep(1)
                            try:
                                task = client.close()
                                if getattr(task, "_coro", None):
                                    task = task._coro
                                await asyncio.wait([asyncio.ensure_future(task)], timeout=3)
                            except Exception:
                                pass
                            await cls.create_client(cls, "sqs", context)
                            client = cls.clients.get("sqs")
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
                                    func = await cls.subscribe(cls, obj, context)
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
                                await cls.delete_message(cls, receipt_handle, queue_url, context)
                                logging.getLogger("transport.aws_sns_sqs").warning("Discarded malformed message")
                                continue

                            payload = message_body.get("Message")
                            message_attributes = message_body.get("MessageAttributes", {})

                            futures.append(
                                callback(payload, receipt_handle, queue_url, message_topic, message_attributes)
                            )
                    except asyncio.CancelledError:
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
                if task and not cls.close_waiter.done():
                    logging.getLogger("transport.aws_sns_sqs").warning(
                        "Resuming message receiving after trying to recover from fatal error"
                    )
                if not task or task.done():
                    task = asyncio.ensure_future(_receive_wrapper())
                await asyncio.wait([cls.close_waiter, task], return_when=asyncio.FIRST_COMPLETED)
                if cls.close_waiter.done():
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
            if not cls.close_waiter.done():
                logging.getLogger("transport.aws_sns_sqs").warning("Draining message pool - awaiting running tasks")
                cls.close_waiter.set_result(None)

                if not start_waiter.done():
                    start_waiter.set_result(None)
                await stop_waiter
                if stop_method:
                    await stop_method(*args, **kwargs)

                tasks = []
                for _, client in cls.clients.items():
                    task = client.close()
                    if getattr(task, "_coro", None):
                        task = task._coro
                    tasks.append(asyncio.ensure_future(task))
                await asyncio.wait(tasks, timeout=3)
                cls.clients = None
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

    async def subscribe(cls: Any, obj: Any, context: Dict) -> Optional[Callable]:
        if context.get("_aws_sns_sqs_subscribed"):
            return None
        context["_aws_sns_sqs_subscribed"] = True

        if cls.clients:
            tasks = []
            for _, client in cls.clients.items():
                task = client.close()
                if getattr(task, "_coro", None):
                    task = task._coro
                tasks.append(asyncio.ensure_future(task))
            await asyncio.wait(tasks, timeout=3)
            cls.clients = None

        async def _subscribe() -> None:
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
                topic: str,
                func: Callable,
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
                        cls.encode_topic(topic), func.__name__, _uuid, competing_consumer, context
                    )
                else:
                    queue_name = cls.prefix_queue_name(queue_name, context)

                queue_url, queue_arn = cast(Tuple[str, str], await cls.create_queue(cls, queue_name, context))

                if re.search(r"([*#])", topic):
                    await cls.subscribe_wildcard_topic(cls, topic, queue_arn, queue_url, context, attributes=attributes)
                else:
                    topic_arn = await cls.create_topic(cls, topic, context)
                    await cls.subscribe_topics(cls, (topic_arn,), queue_arn, queue_url, context, attributes=attributes)

                return queue_url

            for topic, competing, queue_name, func, handler, attributes in context.get("_aws_sns_sqs_subscribers", []):
                queue_url = await setup_queue(
                    topic, func, queue_name=queue_name, competing_consumer=competing, attributes=attributes
                )
                await cls.consume_queue(cls, obj, context, handler, queue_url=queue_url)

        return _subscribe


__aws_sns_sqs = AWSSNSSQSTransport.decorator(AWSSNSSQSTransport.subscribe_handler)
aws_sns_sqs_publish = AWSSNSSQSTransport.publish
publish = AWSSNSSQSTransport.publish


def aws_sns_sqs(
    topic: str,
    callback_kwargs: Optional[Union[List, Set, Tuple]] = None,
    competing: Optional[bool] = None,
    queue_name: Optional[str] = None,
    *,
    message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
    message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
    filter_policy: Optional[
        Union[str, Dict[str, List[Union[str, Dict[str, Union[bool, List]]]]]]
    ] = FILTER_POLICY_DEFAULT,
    **kwargs: Any,
) -> Callable:
    return cast(
        Callable,
        __aws_sns_sqs(
            topic,
            callback_kwargs=callback_kwargs,
            competing=competing,
            queue_name=queue_name,
            message_envelope=message_envelope,
            message_protocol=message_protocol,
            filter_policy=filter_policy,
            **kwargs,
        ),
    )
