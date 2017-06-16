import logging
import asyncio
import aiobotocore
import botocore
import aiohttp
import time
import hashlib
import re
import binascii
import ujson
import uuid
from typing import Any, Dict, Union, Optional, Callable, Awaitable, List, Tuple, Match
from tomodachi.invoker import Invoker

DRAIN_MESSAGE_PAYLOAD = '__TOMODACHI_DRAIN__cdab4416-1727-4603-87c9-0ff8dddf1f22__'


class AWSSNSSQSException(Exception):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if kwargs and kwargs.get('log_level'):
            self._log_level = kwargs.get('log_level')
        else:
            self._log_level = 'INFO'


class AWSSNSSQSConnectionException(AWSSNSSQSException):
    pass


class AWSSNSSQSTransport(Invoker):
    clients = None
    topics = {}  # type: Dict[str, str]
    close_waiter = None

    @classmethod
    async def publish(cls, service: Any, data: Any, topic: str, wait: bool=True) -> None:
        message_protocol = None
        try:
            message_protocol = service.message_protocol
        except AttributeError as e:
            pass

        payload = data
        if message_protocol:
            try:
                payload = await message_protocol.build_message(service, topic, data)
            except AttributeError as e:
                pass

        topic_arn = await cls.create_topic(cls, topic, service.context)

        async def _publish_message() -> None:
            await cls.publish_message(cls, topic_arn, payload, service.context)

        if wait:
            await _publish_message()
        else:
            loop = asyncio.get_event_loop()  # type: Any
            loop.create_task(_publish_message())

    @classmethod
    def get_topic_name(cls, topic: str, context: Dict) -> str:
        if context.get('options', {}).get('aws_sns_sqs', {}).get('topic_prefix'):
            return '{}{}'.format(context.get('options', {}).get('aws_sns_sqs', {}).get('topic_prefix'), topic)
        return topic

    @classmethod
    def decode_topic(cls, encoded_topic: str) -> str:
        def decode(match: Match) -> str:
            return binascii.unhexlify(match.group(1).encode('utf-8')).decode('utf-8')

        return re.sub(r'___([a-f0-9]{2}|[a-f0-9]{4}|[a-f0-9]{6}|[a-f0-9]{8})_', decode, encoded_topic)

    @classmethod
    def encode_topic(cls, topic: str) -> str:
        def encode(match: Match) -> str:
            return '___' + binascii.hexlify(match.group(1).encode('utf-8')).decode('utf-8') + '_'

        return re.sub(r'([^a-zA-Z0-9_*#-])', encode, topic)

    @classmethod
    def get_queue_name(cls, topic: str, func_name: str, _uuid: str, competing_consumer: bool, context: Dict) -> str:
        if not competing_consumer:
            queue_name = hashlib.sha256('{}{}{}'.format(topic, func_name, _uuid).encode('utf-8')).hexdigest()
        else:
            queue_name = hashlib.sha256(topic.encode('utf-8')).hexdigest()

        if context.get('options', {}).get('aws_sns_sqs', {}).get('queue_name_prefix'):
            return '{}{}'.format(context.get('options', {}).get('aws_sns_sqs', {}).get('queue_name_prefix'), queue_name)
        return queue_name

    async def subscribe_handler(cls: Any, obj: Any, context: Dict, func: Callable, topic: str, callback_kwargs: Optional[Union[list, set, tuple]]=None, competing: bool=False) -> Any:
        async def handler(payload: Optional[str], receipt_handle: Optional[str]=None, queue_url: Optional[str]=None) -> Any:
            if not payload or payload == DRAIN_MESSAGE_PAYLOAD:
                await cls.delete_message(cls, receipt_handle, queue_url, context)
                return

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
                    if message is not False and message_uuid:
                        if not context.get('_aws_sns_sqs_received_messages'):
                            context['_aws_sns_sqs_received_messages'] = {}
                        message_key = '{}:{}'.format(message_uuid, func.__name__)
                        if context['_aws_sns_sqs_received_messages'].get(message_key):
                            return
                        context['_aws_sns_sqs_received_messages'][message_key] = time.time()
                        _received_messages = context['_aws_sns_sqs_received_messages']
                        if _received_messages and isinstance(_received_messages, dict) and len(_received_messages) > 100000:
                            context['_aws_sns_sqs_received_messages'] = {k: v for k, v in context['_aws_sns_sqs_received_messages'].items() if v > time.time() - 60}

                    if _callback_kwargs:
                        for k, v in message.items():
                            if k in _callback_kwargs:
                                kwargs[k] = v
                        if 'message' in _callback_kwargs and 'message' not in kwargs:
                            kwargs['message'] = message
                except Exception as e:
                    # log message protocol exception
                    if message is not False and not message_uuid:
                        await cls.delete_message(cls, receipt_handle, queue_url, context)
                    elif message is False and message_uuid:
                        pass  # incompatible protocol, should probably delete if old message
                    elif message is False:
                        await cls.delete_message(cls, receipt_handle, queue_url, context)
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
                await cls.delete_message(cls, receipt_handle, queue_url, context)
                raise e

            if isinstance(routine, Awaitable):
                try:
                    return_value = await routine
                except Exception as e:
                    await cls.delete_message(cls, receipt_handle, queue_url, context)
                    raise e
            else:
                return_value = routine

            await cls.delete_message(cls, receipt_handle, queue_url, context)

            return return_value

        context['_aws_sns_sqs_subscribers'] = context.get('_aws_sns_sqs_subscribers', [])
        context['_aws_sns_sqs_subscribers'].append((topic, competing, func, handler))

        start_func = cls.subscribe(cls, obj, context)
        return (await start_func) if start_func else None

    def create_client(cls: Any, name: str, context: Dict) -> None:
        logging.getLogger('botocore.vendored.requests.packages.urllib3.connectionpool').setLevel(logging.WARNING)

        if not cls.clients:
            cls.clients = {}
        loop = asyncio.get_event_loop()
        session = aiobotocore.get_session(loop=loop)

        config_base = context.get('options', {}).get('aws_sns_sqs', context.get('options', {}).get('aws', {}))
        aws_config_base = context.get('options', {}).get('aws', {})

        region_name = config_base.get('aws_region_name', config_base.get('region_name')) or aws_config_base.get('aws_region_name', config_base.get('region_name'))
        aws_secret_access_key = config_base.get('aws_secret_access_key', config_base.get('secret_access_key')) or aws_config_base.get('aws_secret_access_key', config_base.get('secret_access_key'))
        aws_access_key_id = config_base.get('aws_access_key_id', config_base.get('access_key_id')) or aws_config_base.get('aws_access_key_id', config_base.get('access_key_id'))

        try:
            cls.clients[name] = session.create_client(name, region_name=region_name, aws_secret_access_key=aws_secret_access_key, aws_access_key_id=aws_access_key_id)
        except botocore.exceptions.PartialCredentialsError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Invalid credentials [{}] to AWS ({})'.format(name, error_message))
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get('log_level')) from e
        except botocore.exceptions.NoRegionError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Invalid credentials [{}] to AWS ({})'.format(name, error_message))
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get('log_level')) from e

    async def create_topic(cls: Any, topic: str, context: Dict) -> str:
        if not cls.topics:
            cls.topics = {}
        if cls.topics.get(topic):
            topic_arn = cls.topics.get(topic)
            if topic_arn and isinstance(topic_arn, str):
                return topic_arn

        if not cls.clients or not cls.clients.get('sns'):
            cls.create_client(cls, 'sns', context)
        client = cls.clients.get('sns')

        try:
            response = await asyncio.wait_for(client.create_topic(Name=cls.encode_topic(cls.get_topic_name(topic, context))), timeout=30)
        except botocore.exceptions.NoCredentialsError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to connect [sns] to AWS ({})'.format(error_message))
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get('log_level')) from e
        except botocore.exceptions.PartialCredentialsError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to create topic [sns] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e
        except aiohttp.client_exceptions.ClientOSError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to connect [sns] to AWS ({})'.format(error_message))
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get('log_level')) from e
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to create topic [sns] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e
        except asyncio.TimeoutError as e:
            error_message = 'Network timeout'
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to create topic [sns] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e

        topic_arn = response.get('TopicArn')
        if not topic_arn or not isinstance(topic_arn, str):
            error_message = 'Missing ARN in response'
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to create topic [sns] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level'))

        cls.topics[topic] = topic_arn

        return topic_arn

    async def publish_message(cls: Any, topic_arn: str, message: Any, context: Dict) -> str:
        if not cls.clients or not cls.clients.get('sns'):
            cls.create_client(cls, 'sns', context)
        client = cls.clients.get('sns')

        try:
            response = await asyncio.wait_for(client.publish(TopicArn=topic_arn, Message=message), timeout=30)
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to publish message [sns] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e
        except aiohttp.client_exceptions.ClientConnectorError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to publish message [sns] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e
        except asyncio.TimeoutError as e:
            error_message = 'Network timeout'
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to publish message [sns] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e

        message_id = response.get('MessageId')
        if not message_id or not isinstance(message_id, str):
            error_message = 'Missing MessageId in response'
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to publish message [sns] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level'))

        return message_id

    async def delete_message(cls: Any, receipt_handle: Optional[str], queue_url: Optional[str], context: Dict) -> None:
        if not receipt_handle:
            return
        if not cls.clients or not cls.clients.get('sqs'):
            cls.create_client(cls, 'sqs', context)
        client = cls.clients.get('sqs')

        async def _delete_message() -> None:
            try:
                await asyncio.wait_for(client.delete_message(ReceiptHandle=receipt_handle, QueueUrl=queue_url), timeout=30)
            except botocore.exceptions.ClientError as e:
                error_message = str(e)
                logging.getLogger('transport.aws_sns_sqs').warning('Unable to delete message [sqs] on AWS ({})'.format(error_message))
            except asyncio.TimeoutError as e:
                error_message = 'Network timeout'
                logging.getLogger('transport.aws_sns_sqs').warning('Unable to delete message [sqs] on AWS ({})'.format(error_message))
                raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e

        await _delete_message()

    async def create_queue(cls: Any, queue_name: str, context: Dict) -> Tuple[str, str]:
        if not cls.clients or not cls.clients.get('sqs'):
            cls.create_client(cls, 'sqs', context)
        client = cls.clients.get('sqs')

        try:
            response = await client.create_queue(QueueName=queue_name)
        except botocore.exceptions.NoCredentialsError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to connect [sqs] to AWS ({})'.format(error_message))
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get('log_level')) from e
        except botocore.exceptions.PartialCredentialsError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to connect [sqs] to AWS ({})'.format(error_message))
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get('log_level')) from e
        except aiohttp.client_exceptions.ClientOSError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to connect [sqs] to AWS ({})'.format(error_message))
            raise AWSSNSSQSConnectionException(error_message, log_level=context.get('log_level')) from e
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to create queue [sqs] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e

        queue_url = response.get('QueueUrl')
        if not queue_url:
            error_message = 'Missing Queue URL in response'
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to create queue [sqs] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level'))

        try:
            response = await client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=['QueueArn'])
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to get queue attributes [sqs] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e

        queue_arn = response.get('Attributes', {}).get('QueueArn')
        if not queue_arn:
            error_message = 'Missing ARN in response'
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to get queue attributes [sqs] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level'))

        return queue_url, queue_arn

    @classmethod
    def generate_queue_policy(cls, queue_arn: str, topic_arn_list: List, context: Dict) -> Dict:
        if len(topic_arn_list) == 1:
            if context.get('options', {}).get('aws_sns_sqs', {}).get('queue_policy'):
                source_arn = context.get('options', {}).get('aws_sns_sqs', {}).get('queue_policy')
            else:
                source_arn = topic_arn_list[0]
        else:
            wildcard_topic_arn = []
            try:
                for i in range(0, min([len(topic_arn) for topic_arn in topic_arn_list])):
                    if len(set([topic_arn[i] for topic_arn in topic_arn_list])) == 1:
                        wildcard_topic_arn.append(topic_arn_list[0][i])
                    else:
                        wildcard_topic_arn.append('*')
                        break
            except IndexError:
                wildcard_topic_arn.append('*')

            source_arn = ''.join(wildcard_topic_arn)
            if context.get('options', {}).get('aws_sns_sqs', {}).get('queue_policy'):
                source_arn = context.get('options', {}).get('aws_sns_sqs', {}).get('queue_policy')
            if context.get('options', {}).get('aws_sns_sqs', {}).get('wildcard_queue_policy'):
                source_arn = context.get('options', {}).get('aws_sns_sqs', {}).get('wildcard_queue_policy')

        queue_policy = {
            "Version": "2012-10-17",
            "Id": "{}/SQSDefaultPolicy".format(queue_arn),
            "Statement": [
                {
                    "Sid": "{}{}".format(str(uuid.uuid4()), ('%.3f' % time.time()).replace('.', '')),
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "SQS:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {
                        "ArnEquals": {
                            "aws:SourceArn": source_arn
                        }
                    }
                }
            ]
        }
        return queue_policy

    async def subscribe_wildcard_topic(cls: Any, topic: str, queue_arn: str, queue_url: str, context: Dict) -> Optional[List]:
        if not cls.clients or not cls.clients.get('sns'):
            cls.create_client(cls, 'sns', context)
        client = cls.clients.get('sns')

        pattern = r'^arn:aws:sns:[^:]+:[^:]+:{}$'.format(cls.encode_topic(cls.get_topic_name(topic, context)).replace(cls.encode_topic('*'), '((?!{}).)*'.format(cls.encode_topic('.'))).replace(cls.encode_topic('#'), '.*'))
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
                logging.getLogger('transport.aws_sns_sqs').warning('Unable to list topics [sns] on AWS ({})'.format(error_message))
                raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e

            next_token = response.get('NextToken')
            topics = response.get('Topics', [])
            topic_arn_list = [t.get('TopicArn') for t in topics if t.get('TopicArn') and compiled_pattern.match(t.get('TopicArn'))]

        if topic_arn_list:
            queue_policy = cls.generate_queue_policy(queue_arn, topic_arn_list, context)
            cls.topics[topic] = topic_arn_list[0]
            return await cls.subscribe_topics(cls, topic_arn_list, queue_arn, queue_url, context, queue_policy=queue_policy)

        return None

    async def subscribe_topics(cls: Any, topic_arn_list: List, queue_arn: str, queue_url: str, context: Dict, queue_policy: Optional[Dict]=None) -> List:
        if not cls.clients or not cls.clients.get('sns'):
            cls.create_client(cls, 'sns', context)
        client = cls.clients.get('sns')

        if not cls.clients or not cls.clients.get('sqs'):
            cls.create_client(cls, 'sqs', context)
        sqs_client = cls.clients.get('sqs')

        if not queue_policy:
            queue_policy = cls.generate_queue_policy(queue_arn, topic_arn_list, context)

        try:
            # MessageRetentionPeriod (default 4 days, set to context value)
            # VisibilityTimeout (default 30 seconds)
            response = await sqs_client.set_queue_attributes(QueueUrl=queue_url, Attributes={'Policy': ujson.dumps(queue_policy)})
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            logging.getLogger('transport.aws_sns_sqs').warning('Unable to set queue attributes [sqs] on AWS ({})'.format(error_message))
            raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e

        subscription_arn_list = []
        for topic_arn in topic_arn_list:
            try:
                response = await client.subscribe(TopicArn=topic_arn, Protocol='sqs', Endpoint=queue_arn)
            except botocore.exceptions.ClientError as e:
                error_message = str(e)
                logging.getLogger('transport.aws_sns_sqs').warning('Unable to subscribe to topic [sns] on AWS ({})'.format(error_message))
                raise AWSSNSSQSException(error_message, log_level=context.get('log_level')) from e

            subscription_arn = response.get('SubscriptionArn')
            if not subscription_arn:
                error_message = 'Missing Subscription ARN in response'
                logging.getLogger('transport.aws_sns_sqs').warning('Unable to subscribe to topic [sns] on AWS ({})'.format(error_message))
                raise AWSSNSSQSException(error_message, log_level=context.get('log_level'))

            subscription_arn_list.append(subscription_arn)

        return subscription_arn_list

    async def consume_queue(cls: Any, obj: Any, context: Dict, handler: Callable, queue_url: str) -> None:
        if not cls.clients or not cls.clients.get('sqs'):
            cls.create_client(cls, 'sqs', context)
        client = cls.clients.get('sqs')

        if not cls.close_waiter:
            cls.close_waiter = asyncio.Future()
        stop_waiter = asyncio.Future()  # type: asyncio.Future
        start_waiter = asyncio.Future()  # type: asyncio.Future

        async def receive_messages() -> None:
            def callback(payload: Optional[str], receipt_handle: Optional[str], queue_url: Optional[str]) -> Callable:
                async def _callback() -> None:
                    await handler(payload, receipt_handle, queue_url)
                return _callback

            await start_waiter
            while not cls.close_waiter.done():
                try:
                    response = await asyncio.wait_for(client.receive_message(QueueUrl=queue_url, WaitTimeSeconds=20, MaxNumberOfMessages=10), timeout=30)
                except botocore.exceptions.ClientError as e:
                    error_message = str(e)
                    logging.getLogger('transport.aws_sns_sqs').warning('Unable to receive message from queue [sqs] on AWS ({})'.format(error_message))
                    await asyncio.sleep(1)
                    continue
                except asyncio.TimeoutError as e:
                    error_message = 'Network timeout'
                    logging.getLogger('transport.aws_sns_sqs').warning('Unable to receive message from queue [sqs] on AWS ({})'.format(error_message))
                    await asyncio.sleep(1)
                    continue
                except aiohttp.client_exceptions.ClientConnectorError as e:
                    error_message = str(e)
                    logging.getLogger('transport.aws_sns_sqs').warning('Unable to receive message from queue [sqs] on AWS ({})'.format(error_message))
                    await asyncio.sleep(1)
                    continue

                messages = response.get('Messages', [])
                if messages:
                    futures = []

                    for message in messages:
                        receipt_handle = message.get('ReceiptHandle')
                        try:
                            message_body = ujson.loads(message.get('Body'))
                        except ValueError:
                            # Malformed SQS message, not in SNS format and should be discarded
                            await cls.delete_message(cls, receipt_handle, queue_url, context)
                            logging.getLogger('transport.aws_sns_sqs').warning('Discarded malformed message')
                            continue

                        payload = message_body.get('Message')
                        futures.append(callback(payload, receipt_handle, queue_url))
                    if futures:
                        await asyncio.wait([asyncio.ensure_future(func()) for func in futures if func])

            if not stop_waiter.done():
                stop_waiter.set_result(None)

        loop = asyncio.get_event_loop()  # type: Any

        try:
            stop_method = getattr(obj, '_stop_service')
        except AttributeError as e:
            stop_method = None
        async def stop_service(*args: Any, **kwargs: Any) -> None:
            if not cls.close_waiter.done():
                cls.close_waiter.set_result(None)
                logging.getLogger('transport.aws_sns_sqs').warning('Draining message pool - may take up to 30 seconds')

                for _ in range(0, 100):
                    tasks = []
                    t = time.time()
                    if stop_waiter.done():
                        break
                    for topic, topic_arn in cls.topics.items():
                        tasks.append(asyncio.ensure_future(cls.publish_message(cls, topic_arn, DRAIN_MESSAGE_PAYLOAD, context)))
                    if tasks:
                        task_results = await asyncio.wait(tasks, timeout=40)
                        exception = None
                        for v in [value for value in task_results][0]:
                            try:
                                if (v.exception() or v.cancelled()) and not exception:
                                    exception = True
                                    sleep_timer = (t + 30.0) - time.time()
                                    if sleep_timer > 0.0:
                                        logging.getLogger('transport.aws_sns_sqs').warning('Draining failed - please wait')
                                        await asyncio.sleep(sleep_timer)
                            except Exception:
                                pass
                        if exception and not stop_waiter.done():
                            stop_waiter.set_result(None)

                    if not stop_waiter.done():
                        await asyncio.sleep(0.2)

                if not start_waiter.done():
                    start_waiter.set_result(None)
                await stop_waiter
                if stop_method:
                    await stop_method(*args, **kwargs)
                await asyncio.wait([asyncio.ensure_future(client.close()) for _, client in cls.clients.items()], timeout=3)
                cls.clients = None
            else:
                await stop_waiter
                if stop_method:
                    await stop_method(*args, **kwargs)

        setattr(obj, '_stop_service', stop_service)

        try:
            started_method = getattr(obj, '_started_service')
        except AttributeError as e:
            started_method = None
        async def started_service(*args: Any, **kwargs: Any) -> None:
            if started_method:
                await started_method(*args, **kwargs)
            if not start_waiter.done():
                start_waiter.set_result(None)

        setattr(obj, '_started_service', started_service)

        loop.create_task(receive_messages())

    async def subscribe(cls: Any, obj: Any, context: Dict) -> Optional[Callable]:
        if context.get('_aws_sns_sqs_subscribed'):
            return None
        context['_aws_sns_sqs_subscribed'] = True

        async def _subscribe() -> None:
            async def setup_queue(topic: str, func: Callable, queue_name: Optional[str]=None, competing_consumer: bool=False):
                _uuid = obj.uuid

                if queue_name is None:
                    queue_name = cls.get_queue_name(cls.encode_topic(topic), func.__name__, _uuid, competing_consumer, context)

                queue_url, queue_arn = await cls.create_queue(cls, queue_name, context)

                if re.search(r'([*#])', topic):
                    await cls.subscribe_wildcard_topic(cls, topic, queue_arn, queue_url, context)
                else:
                    topic_arn = await cls.create_topic(cls, topic, context)
                    await cls.subscribe_topics(cls, (topic_arn,), queue_arn, queue_url, context)

                return queue_url

            for topic, competing, func, handler in context.get('_aws_sns_sqs_subscribers', []):
                queue_url = await setup_queue(topic, func, competing_consumer=competing)
                await cls.consume_queue(cls, obj, context, handler, queue_url=queue_url)

        return _subscribe

aws_sns_sqs = AWSSNSSQSTransport.decorator(AWSSNSSQSTransport.subscribe_handler)
aws_sns_sqs_publish = AWSSNSSQSTransport.publish
