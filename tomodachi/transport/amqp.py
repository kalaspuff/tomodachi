import logging
import aioamqp
import types
from tomodachi.invoker import Invoker


class AmqpException(Exception):
    def __init__(self, *args, **kwargs):
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
    channel = None

    @classmethod
    async def publish(cls, service, data, routing_key='', exchange_name=''):
        if not cls.channel:
            instance = cls()
            await cls.connect(cls, instance, service.context)
        channel = cls.channel
        exchange_name = exchange_name or cls.exchange_name

        message_protocol = None
        try:
            message_protocol = service.options.get('amqp', {}).get('message_protocol')
        except AttributeError as e:
            pass

        payload = data
        if message_protocol:
            try:
                payload = await message_protocol.build_message(service, data)
            except AttributeError as e:
                pass

        success = False
        while not success:
            try:
                await channel.basic_publish(str.encode(payload), exchange_name, routing_key)
                success = True
            except AssertionError as e:
                instance = cls()
                await cls.connect(cls, instance, service.context)
                channel = cls.channel

    async def subscribe_handler(cls, obj, context, func, routing_key, callback_kwargs=None, exchange_name=''):
        async def handler(payload):
            if callback_kwargs:
                kwargs = {k: None for k in callback_kwargs}
            message_protocol = context.get('options', {}).get('amqp', {}).get('message_protocol')
            message = payload
            if message_protocol:
                try:
                    message = await message_protocol.parse_message(payload)
                    if callback_kwargs:
                        for k, v in message.items():
                            if k in callback_kwargs:
                                kwargs[k] = v
                except Exception as e:
                    return

            if callback_kwargs:
                routine = func(*(obj,), **kwargs)
            else:
                routine = func(*(obj, message), **{})

            if isinstance(routine, types.GeneratorType) or isinstance(routine, types.CoroutineType):
                return_value = await routine
            else:
                return_value = routine
            return return_value

        exchange_name = exchange_name or context.get('options', {}).get('amqp', {}).get('exchange_name', '')

        context['_amqp_subscribers'] = context.get('_amqp_subscribers', [])
        context['_amqp_subscribers'].append((routing_key, exchange_name, func, handler))

        return await cls.subscribe(cls, obj, context)

    async def connect(cls, obj, context):
        logging.getLogger('aioamqp.protocol').setLevel(logging.WARN)
        logging.getLogger('aioamqp.channel').setLevel(logging.WARN)

        host = context.get('options', {}).get('amqp', {}).get('host', '127.0.0.1')
        port = context.get('options', {}).get('amqp', {}).get('port', 5672)
        login = context.get('options', {}).get('amqp', {}).get('login', 'guest')
        password = context.get('options', {}).get('amqp', {}).get('password', 'guest')

        try:
            transport, protocol = await aioamqp.connect(host=host, port=port, login=login, password=password)
        except ConnectionRefusedError as e:
            error_message = 'connection refused'
            logging.getLogger('transport.amqp').warn('Unable to connect [amqp] to {}:{} ({})'.format(host, port, error_message))
            raise AmqpConnectionException(str(e), log_level=context.get('log_level')) from e
        except aioamqp.exceptions.AmqpClosedConnection as e:
            error_message = e.__context__
            logging.getLogger('transport.amqp').warn('Unable to connect [amqp] to {}:{} ({})'.format(host, port, error_message))
            raise AmqpConnectionException(str(e), log_level=context.get('log_level')) from e
        except OSError as e:
            error_message = e.strerror
            logging.getLogger('transport.amqp').warn('Unable to connect [amqp] to {}:{} ({})'.format(host, port, error_message))
            raise AmqpConnectionException(str(e), log_level=context.get('log_level')) from e

        channel = await protocol.channel()
        cls.channel = channel
        cls.exchange_name = context.get('options', {}).get('amqp', {}).get('exchange_name', '')

        try:
            stop_method = getattr(obj, '_stop_service')
        except AttributeError as e:
            stop_method = None
        async def stop_service(*args, **kwargs):
            if stop_method:
                await stop_method(*args, **kwargs)
            logging.getLogger('aioamqp.protocol').setLevel(logging.FATAL)
            await protocol.close()
            transport.close()

        setattr(obj, '_stop_service', stop_service)

        return channel

    async def subscribe(cls, obj, context):
        if context.get('_amqp_connected'):
            return None
        context['_amqp_connected'] = True

        if not cls.channel:
            channel = await cls.connect(cls, obj, context)
        else:
            channel = cls.channel

        async def _subscribe():
            async def declare_queue(routing_key, func, exchange_name='', exchange_type='direct', queue_name=None,
                                    passive=False, durable=True, exclusive=False, auto_delete=False,
                                    competing_consumer=False):
                try:
                    if exchange_name:
                        await channel.exchange_declare(exchange_name=exchange_name, type_name=exchange_type, passive=False, durable=True, auto_delete=False)
                except aioamqp.exceptions.ChannelClosed as e:
                    error_message = e.args[1]
                    if e.args[0] == 403 and exchange_name.startswith('amq.'):
                        logging.getLogger('transport.amqp').warn('Unable to declare exchange [amqp] "{}", starts with reserved "amq." ({})'.format(exchange_name, error_message))
                        raise
                    elif e.args[0] == 507 or e.args[0] == 406:
                        logging.getLogger('transport.amqp').warn('Unable to change type of existing exchange [amqp] "{}" ({})'.format(exchange_name, error_message))
                        raise
                    else:
                        logging.getLogger('transport.amqp').warn('Unable to declare exchange [amqp] "{}" ({})'.format(exchange_name, error_message))
                        raise

                _uuid = obj.uuid
                max_consumers = 1 if not competing_consumer else None
                if queue_name is None:
                    queue_name = '{}.{}.{}'.format(routing_key, func.__name__, _uuid) if not competing_consumer else routing_key

                amqp_arguments = {}
                ttl = context.get('options', {}).get('amqp', {}).get('queue_ttl', 86400)
                if ttl:
                    amqp_arguments['x-expires'] = int(ttl * 1000)

                try:
                    data = await channel.queue_declare(queue_name, passive=passive, durable=durable, exclusive=exclusive, auto_delete=auto_delete, arguments=amqp_arguments)
                    if max_consumers is not None and data.get('consumer_count', 0) >= max_consumers:
                        logging.getLogger('transport.amqp').warn('Max consumers ({}) for queue [amqp] "{}" has been reached'.format(max_consumers, queue_name))
                        raise AmqpTooManyConsumersException("Max consumers for this queue has been reached")
                except aioamqp.exceptions.ChannelClosed as e:
                    if e.args[0] == 405:
                        raise AmqpExclusiveQueueLockedException(str(e)) from e
                    raise AmqpException(str(e)) from e

                if exchange_name:
                    await channel.queue_bind(queue_name, exchange_name, routing_key)
                return queue_name

            def callback(routing_key, handler):
                async def _callback(self, body, envelope, properties):
                    # await channel.basic_reject(delivery_tag, requeue=True)
                    if envelope.routing_key == routing_key:
                        await handler(body.decode())
                    await channel.basic_client_ack(envelope.delivery_tag)
                return _callback

            for routing_key, exchange_name, func, handler in context.get('_amqp_subscribers', []):
                queue_name = await declare_queue(routing_key, func, exchange_name=exchange_name)
                await channel.basic_consume(callback(routing_key, handler), queue_name=queue_name)

        return _subscribe

amqp = AmqpTransport.decorator(AmqpTransport.subscribe_handler)
amqp_publish = AmqpTransport.publish
