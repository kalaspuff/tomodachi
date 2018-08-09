import os
import tomodachi
import uuid
from typing import Any, Dict
from tomodachi import schedule, minutely, hourly
from tomodachi import aws_sns_sqs_publish
from tomodachi.protocol import JsonBase


@tomodachi.service
class ServiceSendMessage(tomodachi.Service):
    name = 'example_service_send_message'
    log_level = 'INFO'
    uuid = os.environ.get('SERVICE_UUID')
    message_protocol = JsonBase

    options = {
        'aws_sns_sqs': {
            'region_name': None,  # specify AWS region (example: 'eu-west-1')
            'aws_access_key_id': None,  # specify AWS access key (example: 'AKIAXNTIENCJIY2STOCI')
            'aws_secret_access_key': None  # specify AWS secret key (example: 'f7sha92hNotarealsecretkeyn29ShnSYQi3nzgA')
        },
        'aws_endpoint_urls': {
            'sns': None,  # For example 'http://localhost:4575' if localstack is used for testing
            'sqs': None  # For example 'http://localhost:4576' if localstack is used for testing
        }
    }

    @schedule(interval=10, immediately=True)
    async def send_message(self) -> None:
        data = str(uuid.uuid4())
        self.log('Publishing message "{}" on topic "example-pubsub-new-message"'.format(data))
        await aws_sns_sqs_publish(self, data, topic='example-pubsub-new-message', wait=True)
