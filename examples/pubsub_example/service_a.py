import os
import tomodachi
from typing import Any, Dict
from tomodachi import aws_sns_sqs, aws_sns_sqs_publish
from tomodachi.protocol import JsonBase


@tomodachi.service
class ServiceA(tomodachi.Service):
    name = 'example_service_a'
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

    @aws_sns_sqs('example-pubsub-new-message', competing=True)
    async def new_message(self, data: Any) -> None:
        self.log('Received data (function: new_message) - "{}"'.format(data))
        callback_data = 'message received: "{}"'.format(data)
        await aws_sns_sqs_publish(self, callback_data, topic='example-pubsub-callback', wait=True)

    async def _started_service(self) -> None:
        self.log('Subscribing to messages on topic "example-pubsub-new-message"')
