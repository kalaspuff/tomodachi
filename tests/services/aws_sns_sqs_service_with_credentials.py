import asyncio
import os
import signal
import tomodachi
import uuid
from typing import Any
from tomodachi.discovery.aws_sns_registration import AWSSNSRegistration
from tomodachi.protocol.json_base import JsonBase
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs, aws_sns_sqs_publish


@tomodachi.service
class AWSSNSSQSService(object):
    name = 'test_aws_sns_sqs'
    log_level = 'INFO'
    discovery = [AWSSNSRegistration]
    message_protocol = JsonBase
    options = {
        'aws': {
            'region_name': os.environ.get('TOMODACHI_TEST_AWS_REGION'),
            'aws_access_key_id': os.environ.get('TOMODACHI_TEST_AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.environ.get('TOMODACHI_TEST_AWS_ACCESS_SECRET'),
        },
        'aws_sns_sqs': {
            'queue_name_prefix': os.environ.get('TOMODACHI_TEST_SQS_QUEUE_PREFIX'),
            'topic_prefix': os.environ.get('TOMODACHI_TEST_SNS_TOPIC_PREFIX')
        }
    }
    uuid = os.environ.get('TOMODACHI_TEST_SERVICE_UUID')
    closer = asyncio.Future()  # type: Any
    test_topic_data_received = False
    test_topic_specified_queue_name_data_received = False
    test_topic_metadata_topic = None
    test_topic_service_uuid = None
    wildcard_topic_data_received = False
    data_uuid = None

    @aws_sns_sqs('test-topic')
    async def test(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            self.test_topic_data_received = True
            self.test_topic_metadata_topic = metadata.get('topic')
            self.test_topic_service_uuid = service.get('uuid')

    @aws_sns_sqs('test-topic', queue_name='test-queue')
    async def test_specified_queue_name(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            if self.test_topic_specified_queue_name_data_received:
                raise Exception('test_topic_specified_queue_name_data_received already set')
            self.test_topic_specified_queue_name_data_received = True

    @aws_sns_sqs('test-topic', queue_name='test-queue')
    async def test_specified_queue_name_again(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            if self.test_topic_specified_queue_name_data_received:
                raise Exception('test_topic_specified_queue_name_data_received already set')
            self.test_topic_specified_queue_name_data_received = True

    @aws_sns_sqs('test-topic#')
    async def faked_wildcard_topic(self, metadata: Any, data: Any) -> None:
        if data == self.data_uuid:
            self.wildcard_topic_data_received = True

    async def _started_service(self) -> None:
        async def publish(data: Any, topic: str) -> None:
            await aws_sns_sqs_publish(self, data, topic=topic, wait=False)

        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(10.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            asyncio.ensure_future(sleep_and_kill())
            await self.closer
            os.kill(os.getpid(), signal.SIGINT)
        asyncio.ensure_future(_async())

        self.data_uuid = str(uuid.uuid4())
        for _ in range(30):
            if self.test_topic_data_received:
                break
            await publish(self.data_uuid, 'test-topic')
            await asyncio.sleep(0.1)

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
