import asyncio
import binascii
import functools
import hashlib
import inspect
import logging
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Match, Optional, Set, Tuple, Union, cast

import aioamqp

from tomodachi.helpers.dict import merge_dicts
from tomodachi.helpers.execution_context import (
    decrease_execution_context_value,
    increase_execution_context_value,
    set_execution_context,
)
from tomodachi.helpers.middleware import execute_middlewares
from tomodachi.invoker import Invoker

MESSAGE_ENVELOPE_DEFAULT = "2594418c-5771-454a-a7f9-8f83ae82812a"
MESSAGE_PROTOCOL_DEFAULT = MESSAGE_ENVELOPE_DEFAULT  # deprecated
MESSAGE_ROUTING_KEY_PREFIX = "38f58822-25f6-458a-985c-52701d40dbbc"


class AmqpException(Exception):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._log_level = kwargs.get("log_level") if kwargs and kwargs.get("log_level") else "INFO"


class AmqpInternalServiceError(AmqpException):
    pass


class AmqpInternalServiceErrorException(AmqpInternalServiceError):
    pass


class AmqpInternalServiceException(AmqpInternalServiceError):
    pass


class AmqpExclusiveQueueLockedException(AmqpException):
    pass


class AmqpTooManyConsumersException(AmqpException):
    pass


class AmqpConnectionException(AmqpException):
    pass


class AmqpChannelClosed(AmqpException):
    pass


class AmqpTransport(Invoker):
    channel: Any = None
    protocol: Any = None
    transport: Any = None

    @classmethod
    async def publish(
        cls,
        service: Any,
        data: Any,
        routing_key: str = "",
        exchange_name: str = "",
        wait: bool = True,
        *,
        message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
        message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
        routing_key_prefix: Optional[str] = MESSAGE_ROUTING_KEY_PREFIX,
        **kwargs: Any,
    ) -> None:
        if not cls.channel:
            await cls.connect(cls, service, service.context)
        exchange_name = exchange_name or cls.exchange_name or "amq.topic"

        if message_envelope == MESSAGE_ENVELOPE_DEFAULT and message_protocol != MESSAGE_ENVELOPE_DEFAULT:
            # Fallback if deprecated message_protocol keyword is used
            message_envelope = message_protocol

        message_envelope = (
            getattr(service, "message_envelope", getattr(service, "message_protocol", None))
            if message_envelope == MESSAGE_ENVELOPE_DEFAULT
            else message_envelope
        )

        payload = data
        if message_envelope:
            build_message_func = getattr(message_envelope, "build_message", None)
            if build_message_func:
                payload = await build_message_func(service, routing_key, data, **kwargs)

        async def _publish_message() -> None:
            success = False
            while not success:
                try:
                    await cls.channel.basic_publish(
                        str.encode(payload),
                        exchange_name,
                        cls.encode_routing_key(cls.get_routing_key(routing_key, service.context, routing_key_prefix)),
                    )
                    success = True
                except AssertionError:
                    await cls.connect(cls, service, service.context)

        if wait:
            await _publish_message()
        else:
            loop: Any = asyncio.get_event_loop()
            loop.create_task(_publish_message())

    @classmethod
    def get_routing_key(
        cls, routing_key: str, context: Dict, routing_key_prefix: Optional[str] = MESSAGE_ROUTING_KEY_PREFIX
    ) -> str:
        routing_key_prefix = (
            context.get("options", {}).get("amqp", {}).get("routing_key_prefix", "")
            if routing_key_prefix == MESSAGE_ROUTING_KEY_PREFIX
            else (routing_key_prefix or "")
        )
        if routing_key_prefix:
            return "{}{}".format(routing_key_prefix, routing_key)
        return routing_key

    @classmethod
    def get_routing_key_without_prefix(
        cls, routing_key: str, context: Dict, routing_key_prefix: Optional[str] = MESSAGE_ROUTING_KEY_PREFIX
    ) -> str:
        routing_key_prefix = (
            context.get("options", {}).get("amqp", {}).get("routing_key_prefix", "")
            if routing_key_prefix == MESSAGE_ROUTING_KEY_PREFIX
            else (routing_key_prefix or "")
        )
        if routing_key_prefix:
            if routing_key.startswith(routing_key_prefix):
                prefix_length = len(routing_key_prefix)
                return routing_key[prefix_length:]
        return routing_key

    @classmethod
    def decode_routing_key(cls, encoded_routing_key: str) -> str:
        def decode(match: Match) -> str:
            return binascii.unhexlify(match.group(1).encode("utf-8")).decode("utf-8")

        return re.sub(r"___([a-f0-9]{2}|[a-f0-9]{4}|[a-f0-9]{6}|[a-f0-9]{8})_", decode, encoded_routing_key)

    @classmethod
    def encode_routing_key(cls, routing_key: str) -> str:
        def encode(match: Match) -> str:
            return "___" + binascii.hexlify(match.group(1).encode("utf-8")).decode("utf-8") + "_"

        return re.sub(r'([^a-zA-Z0-9_*#,;.:<>!"%&/\(\)\[\]\{\}\\=?\'^`~+|@$ -])', encode, routing_key)

    @classmethod
    def get_queue_name(
        cls, routing_key: str, func_name: str, _uuid: str, competing_consumer: bool, context: Dict
    ) -> str:
        if not competing_consumer:
            queue_name = hashlib.sha256("{}{}{}".format(routing_key, func_name, _uuid).encode("utf-8")).hexdigest()
        else:
            queue_name = hashlib.sha256(routing_key.encode("utf-8")).hexdigest()

        if context.get("options", {}).get("amqp", {}).get("queue_name_prefix"):
            return "{}{}".format(context.get("options", {}).get("amqp", {}).get("queue_name_prefix"), queue_name)
        return queue_name

    @classmethod
    def prefix_queue_name(cls, queue_name: str, context: Dict) -> str:
        if context.get("options", {}).get("amqp", {}).get("queue_name_prefix"):
            return "{}{}".format(context.get("options", {}).get("amqp", {}).get("queue_name_prefix"), queue_name)
        return queue_name

    async def subscribe_handler(
        cls: Any,
        obj: Any,
        context: Dict,
        func: Any,
        routing_key: str,
        callback_kwargs: Optional[Union[List, Set, Tuple]] = None,
        exchange_name: str = "",
        competing: Optional[bool] = None,
        queue_name: Optional[str] = None,
        *,
        message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
        message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
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
        original_kwargs: Dict[str, Any] = {k: v for k, v in _callback_kwargs.items()}

        async def handler(payload: Any, delivery_tag: Any, routing_key: str) -> Any:
            kwargs = dict(original_kwargs)

            message = payload
            message_uuid = None
            message_key = None
            if message_envelope:
                try:
                    parse_message_func = getattr(message_envelope, "parse_message", None)
                    if parse_message_func:
                        if len(parser_kwargs):
                            message, message_uuid, timestamp = await parse_message_func(payload, **parser_kwargs)
                        else:
                            message, message_uuid, timestamp = await parse_message_func(payload)
                    if message_uuid:
                        if not context.get("_amqp_received_messages"):
                            context["_amqp_received_messages"] = {}
                        message_key = "{}:{}".format(message_uuid, func.__name__)
                        if context["_amqp_received_messages"].get(message_key):
                            return
                        context["_amqp_received_messages"][message_key] = time.time()
                        _received_messages = context["_amqp_received_messages"]
                        if (
                            _received_messages
                            and isinstance(_received_messages, dict)
                            and len(_received_messages) > 100000
                        ):
                            context["_amqp_received_messages"] = {
                                k: v for k, v in context["_amqp_received_messages"].items() if v > time.time() - 60
                            }

                    if _callback_kwargs:
                        for k, v in message.items():
                            if k in _callback_kwargs:
                                kwargs[k] = v
                        if "message" in _callback_kwargs and (
                            not isinstance(message, dict) or "message" not in message
                        ):
                            kwargs["message"] = message
                        if "routing_key" in _callback_kwargs and (
                            not isinstance(message, dict) or "routing_key" not in message
                        ):
                            kwargs["routing_key"] = routing_key
                except Exception as e:
                    logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                    if message is not False and not message_uuid:
                        await cls.channel.basic_client_ack(delivery_tag)
                    elif message is False and message_uuid:
                        pass  # incompatible envelope, should probably ack if old message
                    elif message is False:
                        await cls.channel.basic_client_ack(delivery_tag)
                    return
            else:
                if _callback_kwargs:
                    if "message" in _callback_kwargs:
                        kwargs["message"] = message
                    if "routing_key" in _callback_kwargs:
                        kwargs["routing_key"] = routing_key

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
                        (AmqpInternalServiceError, AmqpInternalServiceErrorException, AmqpInternalServiceException),
                    ):
                        if message_key:
                            del context["_amqp_received_messages"][message_key]
                        await cls.channel.basic_client_nack(delivery_tag)
                        return
                    await cls.channel.basic_client_ack(delivery_tag)
                    return

                if isinstance(routine, Awaitable):
                    try:
                        return_value = await routine
                    except Exception as e:
                        logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                        if issubclass(
                            e.__class__,
                            (AmqpInternalServiceError, AmqpInternalServiceErrorException, AmqpInternalServiceException),
                        ):
                            if message_key:
                                del context["_amqp_received_messages"][message_key]
                            await cls.channel.basic_client_nack(delivery_tag)
                            return
                        await cls.channel.basic_client_ack(delivery_tag)
                        return
                else:
                    return_value = routine

                await cls.channel.basic_client_ack(delivery_tag)
                return return_value

            increase_execution_context_value("amqp_current_tasks")
            increase_execution_context_value("amqp_total_tasks")
            return_value = await execute_middlewares(
                func, routine_func, context.get("message_middleware", []), *(obj, message, routing_key)
            )
            decrease_execution_context_value("amqp_current_tasks")

            return return_value

        exchange_name = exchange_name or context.get("options", {}).get("amqp", {}).get("exchange_name", "amq.topic")

        context["_amqp_subscribers"] = context.get("_amqp_subscribers", [])
        context["_amqp_subscribers"].append((routing_key, exchange_name, competing, queue_name, func, handler))

        start_func = cls.subscribe(cls, obj, context)
        return (await start_func) if start_func else None

    async def connect(cls: Any, obj: Any, context: Dict) -> Any:
        logging.getLogger("aioamqp.protocol").setLevel(logging.WARNING)
        logging.getLogger("aioamqp.channel").setLevel(logging.WARNING)

        host = context.get("options", {}).get("amqp", {}).get("host", "127.0.0.1")
        port = context.get("options", {}).get("amqp", {}).get("port", 5672)
        login = context.get("options", {}).get("amqp", {}).get("login", "guest")
        password = context.get("options", {}).get("amqp", {}).get("password", "guest")
        virtualhost = context.get("options", {}).get("amqp", {}).get("virtualhost", "/")
        ssl = context.get("options", {}).get("amqp", {}).get("ssl", False)
        heartbeat = context.get("options", {}).get("amqp", {}).get("heartbeat", 60)

        try:
            transport, protocol = await aioamqp.connect(
                host=host,
                port=port,
                login=login,
                password=password,
                virtualhost=virtualhost,
                ssl=ssl,
                heartbeat=heartbeat,
            )
            cls.protocol = protocol
            cls.transport = transport
        except ConnectionRefusedError as e:
            error_message = "connection refused"
            logging.getLogger("transport.amqp").warning(
                "Unable to connect [amqp] to {}:{} ({})".format(host, port, error_message)
            )
            raise AmqpConnectionException(str(e), log_level=context.get("log_level")) from e
        except aioamqp.exceptions.AmqpClosedConnection as e:
            error_message = e.__context__
            logging.getLogger("transport.amqp").warning(
                "Unable to connect [amqp] to {}:{} ({})".format(host, port, error_message)
            )
            raise AmqpConnectionException(str(e), log_level=context.get("log_level")) from e
        except OSError as e:
            error_message = e.strerror
            logging.getLogger("transport.amqp").warning(
                "Unable to connect [amqp] to {}:{} ({})".format(host, port, error_message)
            )
            raise AmqpConnectionException(str(e), log_level=context.get("log_level")) from e

        channel = await protocol.channel()
        if not cls.channel:
            stop_method = getattr(obj, "_stop_service", None)

            async def stop_service(*args: Any, **kwargs: Any) -> None:
                logging.getLogger("aioamqp.protocol").setLevel(logging.ERROR)
                await cls.protocol.close()
                cls.transport.close()
                cls.channel = None
                cls.transport = None
                cls.protocol = None
                if stop_method:
                    await stop_method(*args, **kwargs)

            setattr(obj, "_stop_service", stop_service)

        cls.channel = channel
        cls.exchange_name = context.get("options", {}).get("amqp", {}).get("exchange_name", "amq.topic")

        return channel

    async def subscribe(cls: Any, obj: Any, context: Dict) -> Optional[Callable]:
        if context.get("_amqp_subscribed"):
            return None
        context["_amqp_subscribed"] = True

        set_execution_context(
            {
                "amqp_enabled": True,
                "amqp_current_tasks": 0,
                "amqp_total_tasks": 0,
                "aioamqp_version": aioamqp.__version__,
            }
        )

        cls.channel = None
        channel = await cls.connect(cls, obj, context)

        async def _subscribe() -> None:
            async def declare_queue(
                routing_key: str,
                func: Callable,
                exchange_name: str = "",
                exchange_type: str = "topic",
                queue_name: Optional[str] = None,
                passive: bool = False,
                durable: bool = True,
                exclusive: bool = False,
                auto_delete: bool = False,
                competing_consumer: Optional[bool] = None,
            ) -> Optional[str]:
                try:
                    if exchange_name and exchange_name != "amq.topic":
                        await channel.exchange_declare(
                            exchange_name=exchange_name,
                            type_name=exchange_type,
                            passive=False,
                            durable=True,
                            auto_delete=False,
                        )
                except aioamqp.exceptions.ChannelClosed as e:
                    error_message = e.args[1]
                    if e.args[0] == 403 and exchange_name.startswith("amq."):
                        logging.getLogger("transport.amqp").warning(
                            'Unable to declare exchange [amqp] "{}", starts with reserved "amq." ({})'.format(
                                exchange_name, error_message
                            )
                        )
                        raise
                    elif e.args[0] == 507 or e.args[0] == 406:
                        logging.getLogger("transport.amqp").warning(
                            'Unable to change type of existing exchange [amqp] "{}" ({})'.format(
                                exchange_name, error_message
                            )
                        )
                        raise
                    else:
                        logging.getLogger("transport.amqp").warning(
                            'Unable to declare exchange [amqp] "{}" ({})'.format(exchange_name, error_message)
                        )
                        raise

                if queue_name and competing_consumer is None:
                    competing_consumer = True

                _uuid = obj.uuid
                max_consumers = 1 if not competing_consumer else None

                if queue_name is None:
                    queue_name = cls.get_queue_name(
                        cls.encode_routing_key(routing_key), func.__name__, _uuid, competing_consumer, context
                    )
                else:
                    queue_name = cls.prefix_queue_name(queue_name, context)

                amqp_arguments = {}
                ttl = context.get("options", {}).get("amqp", {}).get("queue_ttl", 86400)
                if ttl:
                    amqp_arguments["x-expires"] = int(ttl * 1000)

                try:
                    data = await channel.queue_declare(
                        queue_name,
                        passive=passive,
                        durable=durable,
                        exclusive=exclusive,
                        auto_delete=auto_delete,
                        arguments=amqp_arguments,
                    )
                    if max_consumers is not None and data.get("consumer_count", 0) >= max_consumers:
                        logging.getLogger("transport.amqp").warning(
                            'Max consumers ({}) for queue [amqp] "{}" has been reached'.format(
                                max_consumers, queue_name
                            )
                        )
                        raise AmqpTooManyConsumersException("Max consumers for this queue has been reached")
                except aioamqp.exceptions.ChannelClosed as e:
                    if e.args[0] == 405:
                        raise AmqpExclusiveQueueLockedException(str(e)) from e
                    raise AmqpException(str(e)) from e

                await channel.queue_bind(
                    queue_name,
                    exchange_name or "amq.topic",
                    cls.encode_routing_key(cls.get_routing_key(routing_key, context)),
                )

                return queue_name

            def callback(routing_key: str, handler: Callable) -> Callable:
                async def _callback(self: Any, body: bytes, envelope: Any, properties: Any) -> None:
                    # await channel.basic_reject(delivery_tag, requeue=True)
                    await asyncio.shield(handler(body.decode(), envelope.delivery_tag, routing_key))

                return _callback

            for routing_key, exchange_name, competing, queue_name, func, handler in context.get(
                "_amqp_subscribers", []
            ):
                queue_name = await declare_queue(
                    routing_key, func, exchange_name=exchange_name, competing_consumer=competing, queue_name=queue_name
                )
                await channel.basic_consume(callback(routing_key, handler), queue_name=queue_name)

        return _subscribe


__amqp = AmqpTransport.decorator(AmqpTransport.subscribe_handler)
amqp_publish = AmqpTransport.publish
publish = AmqpTransport.publish


def amqp(
    routing_key: str,
    callback_kwargs: Optional[Union[List, Set, Tuple]] = None,
    exchange_name: str = "",
    competing: Optional[bool] = None,
    queue_name: Optional[str] = None,
    *,
    message_envelope: Any = MESSAGE_ENVELOPE_DEFAULT,
    message_protocol: Any = MESSAGE_ENVELOPE_DEFAULT,  # deprecated
    **kwargs: Any,
) -> Callable:
    return cast(
        Callable,
        __amqp(
            routing_key,
            callback_kwargs=callback_kwargs,
            exchange_name=exchange_name,
            competing=competing,
            queue_name=queue_name,
            message_envelope=message_envelope,
            message_protocol=message_protocol,
            **kwargs,
        ),
    )
