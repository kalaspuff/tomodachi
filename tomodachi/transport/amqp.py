import logging
import aioamqp
import time
import hashlib
import re
import binascii
import asyncio
from typing import Any, Dict, Union, Optional, Callable, Awaitable, Match
from tomodachi.invoker import Invoker


class AmqpException(Exception):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if kwargs and kwargs.get('log_level'):
            self._log_level = kwargs.get('log_level')
        else:
            self._log_level = 'INFO'


class AmqpExclusiveQueueLockedException(AmqpException):
    pass


class AmqpTooManyConsumersException(AmqpException):
    pass


class AmqpConnectionException(AmqpException):
    pass


class AmqpChannelClosed(AmqpException):
    pass


class AmqpTransport(Invoker):
    channel = None  # type: Any
    protocol = None  # type: Any
    transport = None  # type: Any

    @classmethod
    async def publish(cls, service: Any, data: Any, routing_key: str='', exchange_name: str='', wait: bool=True) -> None:
        if not cls.channel:
            await cls.connect(cls, service, service.context)
        exchange_name = exchange_name or cls.exchange_name
        if not exchange_name:
            exchange_name = 'amq.topic'

        message_protocol = None  # type: Any
        try:
            message_protocol = service.message_protocol
        except AttributeError as e:
            pass

        payload = data
        if message_protocol:
            try:
                payload = await message_protocol.build_message(service, routing_key, data)
            except AttributeError as e:
                pass

        async def _publish_message() -> None:
            success = False
            while not success:
                try:
                    await cls.channel.basic_publish(str.encode(payload), exchange_name, cls.encode_routing_key(cls.get_routing_key(routing_key, service.context)))
                    success = True
                except AssertionError as e:
                    await cls.connect(cls, service, service.context)

        if wait:
            await _publish_message()
        else:
            loop = asyncio.get_event_loop()  # type: Any
            loop.create_task(_publish_message())

    @classmethod
    def get_routing_key(cls, routing_key: str, context: Dict) -> str:
        if context.get('options', {}).get('amqp', {}).get('routing_key_prefix'):
            return '{}{}'.format(context.get('options', {}).get('amqp', {}).get('routing_key_prefix'), routing_key)
        return routing_key

    @classmethod
    def decode_routing_key(cls, encoded_routing_key: str) -> str:
        def decode(match: Match) -> str:
            return binascii.unhexlify(match.group(1).encode('utf-8')).decode('utf-8')

        return re.sub(r'___([a-f0-9]{2}|[a-f0-9]{4}|[a-f0-9]{6}|[a-f0-9]{8})_', decode, encoded_routing_key)

    @classmethod
    def encode_routing_key(cls, routing_key: str) -> str:
        def encode(match: Match) -> str:
            return '___' + binascii.hexlify(match.group(1).encode('utf-8')).decode('utf-8') + '_'

        return re.sub(r'([^a-zA-Z0-9_*#,;.:<>!"%&/\(\)\[\]\{\}\\=?\'^`~+|@$ -])', encode, routing_key)

    @classmethod
    def get_queue_name(cls, routing_key: str, func_name: str, _uuid: str, competing_consumer: bool, context: Dict) -> str:
        if not competing_consumer:
            queue_name = hashlib.sha256('{}{}{}'.format(routing_key, func_name, _uuid).encode('utf-8')).hexdigest()
        else:
            queue_name = hashlib.sha256(routing_key.encode('utf-8')).hexdigest()

        if context.get('options', {}).get('amqp', {}).get('queue_name_prefix'):
            return '{}{}'.format(context.get('options', {}).get('amqp', {}).get('queue_name_prefix'), queue_name)
        return queue_name

    async def subscribe_handler(cls: Any, obj: Any, context: Dict, func: Callable, routing_key: str, callback_kwargs: Optional[Union[list, set, tuple]]=None, exchange_name: str='', competing: bool=False) -> Any:
        async def handler(payload: Any, delivery_tag: Any) -> Any:
            _callback_kwargs = callback_kwargs  # type: Any
            if not _callback_kwargs:
                _callback_kwargs = {k: None for k in func.__code__.co_varnames[1:]}
            kwargs = {k: None for k in _callback_kwargs if k != 'self'}

            message_protocol = context.get('message_protocol')
            message = payload
            message_uuid = None
            if message_protocol:
                try:
                    message, message_uuid, timestamp = await message_protocol.parse_message(payload)
                    if message_uuid:
                        if not context.get('_amqp_received_messages'):
                            context['_amqp_received_messages'] = {}
                        message_key = '{}:{}'.format(message_uuid, func.__name__)
                        if context['_amqp_received_messages'].get(message_key):
                            return
                        context['_amqp_received_messages'][message_key] = time.time()
                        _received_messages = context['_amqp_received_messages']
                        if _received_messages and isinstance(_received_messages, dict) and len(_received_messages) > 100000:
                            context['_amqp_received_messages'] = {k: v for k, v in context['_amqp_received_messages'].items() if v > time.time() - 60}

                    if _callback_kwargs:
                        for k, v in message.items():
                            if k in _callback_kwargs:
                                kwargs[k] = v
                        if 'message' in _callback_kwargs and 'message' not in kwargs:
                            kwargs['message'] = message
                except Exception as e:
                    # log message protocol exception
                    if message is not False and not message_uuid:
                        await cls.channel.basic_client_ack(delivery_tag)
                    elif message is False and message_uuid:
                        pass  # incompatible protocol, should probably ack if old message
                    elif message is False:
                        await cls.channel.basic_client_ack(delivery_tag)
                    return

            try:
                if len(kwargs):
                    routine = func(*(obj,), **kwargs)
                elif len(func.__code__.co_varnames[1:]):
                    kwargs = {}
                    routine = func(*(obj, message), **kwargs)
                else:
                    kwargs = {}
                    routine = func(*(obj), **kwargs)
            except Exception as e:
                await cls.channel.basic_client_ack(delivery_tag)
                raise e

            if isinstance(routine, Awaitable):
                try:
                    return_value = await routine
                except Exception as e:
                    await cls.channel.basic_client_ack(delivery_tag)
                    raise e
            else:
                return_value = routine

            await cls.channel.basic_client_ack(delivery_tag)

            return return_value

        exchange_name = exchange_name or context.get('options', {}).get('amqp', {}).get('exchange_name', 'amq.topic')

        context['_amqp_subscribers'] = context.get('_amqp_subscribers', [])
        context['_amqp_subscribers'].append((routing_key, exchange_name, competing, func, handler))

        start_func = cls.subscribe(cls, obj, context)
        return (await start_func) if start_func else None

    async def connect(cls: Any, obj: Any, context: Dict) -> Any:
        logging.getLogger('aioamqp.protocol').setLevel(logging.WARNING)
        logging.getLogger('aioamqp.channel').setLevel(logging.WARNING)

        host = context.get('options', {}).get('amqp', {}).get('host', '127.0.0.1')
        port = context.get('options', {}).get('amqp', {}).get('port', 5672)
        login = context.get('options', {}).get('amqp', {}).get('login', 'guest')
        password = context.get('options', {}).get('amqp', {}).get('password', 'guest')

        try:
            transport, protocol = await aioamqp.connect(host=host, port=port, login=login, password=password)
            cls.protocol = protocol
            cls.transport = transport
        except ConnectionRefusedError as e:
            error_message = 'connection refused'
            logging.getLogger('transport.amqp').warning('Unable to connect [amqp] to {}:{} ({})'.format(host, port, error_message))
            raise AmqpConnectionException(str(e), log_level=context.get('log_level')) from e
        except aioamqp.exceptions.AmqpClosedConnection as e:
            error_message = e.__context__
            logging.getLogger('transport.amqp').warning('Unable to connect [amqp] to {}:{} ({})'.format(host, port, error_message))
            raise AmqpConnectionException(str(e), log_level=context.get('log_level')) from e
        except OSError as e:
            error_message = e.strerror
            logging.getLogger('transport.amqp').warning('Unable to connect [amqp] to {}:{} ({})'.format(host, port, error_message))
            raise AmqpConnectionException(str(e), log_level=context.get('log_level')) from e

        channel = await protocol.channel()
        if not cls.channel:
            try:
                stop_method = getattr(obj, '_stop_service')
            except AttributeError as e:
                stop_method = None
            async def stop_service(*args: Any, **kwargs: Any) -> None:
                if stop_method:
                    await stop_method(*args, **kwargs)
                logging.getLogger('aioamqp.protocol').setLevel(logging.ERROR)
                await cls.protocol.close()
                cls.transport.close()
                cls.channel = None
                cls.transport = None
                cls.protocol = None

            setattr(obj, '_stop_service', stop_service)

        cls.channel = channel
        cls.exchange_name = context.get('options', {}).get('amqp', {}).get('exchange_name', 'amq.topic')

        return channel

    async def subscribe(cls: Any, obj: Any, context: Dict) -> Optional[Callable]:
        if context.get('_amqp_subscribed'):
            return None
        context['_amqp_subscribed'] = True

        cls.channel = None
        channel = await cls.connect(cls, obj, context)

        async def _subscribe() -> None:
            async def declare_queue(routing_key: str, func: Callable, exchange_name: str='', exchange_type: str='topic', queue_name: Optional[str]=None,
                                    passive: bool=False, durable: bool=True, exclusive: bool=False, auto_delete: bool=False,
                                    competing_consumer: bool=False) -> Optional[str]:
                try:
                    if exchange_name and exchange_name != 'amq.topic':
                        await channel.exchange_declare(exchange_name=exchange_name, type_name=exchange_type, passive=False, durable=True, auto_delete=False)
                except aioamqp.exceptions.ChannelClosed as e:
                    error_message = e.args[1]
                    if e.args[0] == 403 and exchange_name.startswith('amq.'):
                        logging.getLogger('transport.amqp').warning('Unable to declare exchange [amqp] "{}", starts with reserved "amq." ({})'.format(exchange_name, error_message))
                        raise
                    elif e.args[0] == 507 or e.args[0] == 406:
                        logging.getLogger('transport.amqp').warning('Unable to change type of existing exchange [amqp] "{}" ({})'.format(exchange_name, error_message))
                        raise
                    else:
                        logging.getLogger('transport.amqp').warning('Unable to declare exchange [amqp] "{}" ({})'.format(exchange_name, error_message))
                        raise

                _uuid = obj.uuid
                max_consumers = 1 if not competing_consumer else None
                if queue_name is None:
                    queue_name = cls.get_queue_name(cls.encode_routing_key(routing_key), func.__name__, _uuid, competing_consumer, context)

                amqp_arguments = {}
                ttl = context.get('options', {}).get('amqp', {}).get('queue_ttl', 86400)
                if ttl:
                    amqp_arguments['x-expires'] = int(ttl * 1000)

                try:
                    data = await channel.queue_declare(queue_name, passive=passive, durable=durable, exclusive=exclusive, auto_delete=auto_delete, arguments=amqp_arguments)
                    if max_consumers is not None and data.get('consumer_count', 0) >= max_consumers:
                        logging.getLogger('transport.amqp').warning('Max consumers ({}) for queue [amqp] "{}" has been reached'.format(max_consumers, queue_name))
                        raise AmqpTooManyConsumersException("Max consumers for this queue has been reached")
                except aioamqp.exceptions.ChannelClosed as e:
                    if e.args[0] == 405:
                        raise AmqpExclusiveQueueLockedException(str(e)) from e
                    raise AmqpException(str(e)) from e

                await channel.queue_bind(queue_name, exchange_name or 'amq.topic', cls.encode_routing_key(cls.get_routing_key(routing_key, context)))

                return queue_name

            def callback(routing_key: str, handler: Callable) -> Callable:
                async def _callback(self: Any, body: bytes, envelope: Any, properties: Any) -> None:
                    # await channel.basic_reject(delivery_tag, requeue=True)
                    await handler(body.decode(), envelope.delivery_tag)
                return _callback

            for routing_key, exchange_name, competing, func, handler in context.get('_amqp_subscribers', []):
                queue_name = await declare_queue(routing_key, func, exchange_name=exchange_name, competing_consumer=competing)
                await channel.basic_consume(callback(routing_key, handler), queue_name=queue_name)

        return _subscribe

amqp = AmqpTransport.decorator(AmqpTransport.subscribe_handler)
amqp_publish = AmqpTransport.publish
