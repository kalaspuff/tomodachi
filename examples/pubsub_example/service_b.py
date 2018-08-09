import tomodachi
from typing import Any
from tomodachi import aws_sns_sqs
from tomodachi.protocol import JsonBase


@tomodachi.service
class ServiceB(tomodachi.Service):
    name = 'example_service_b'
    message_protocol = JsonBase

    options = {
        'aws_sns_sqs': {
            'region_name': None,  # specify AWS region (example: 'eu-west-1')
            'aws_access_key_id': None,  # specify AWS access key (example: 'AKIAXNTIENCJIY2STOCI')
            'aws_secret_access_key': None  # specify AWS secret key
        },
        'aws_endpoint_urls': {
            'sns': None,  # For example 'http://localhost:4575' if localstack is used for testing
            'sqs': None  # For example 'http://localhost:4576' if localstack is used for testing
        }
    }

    @aws_sns_sqs('example-pubsub-callback', competing=True)
    async def callback(self, data: Any) -> None:
        self.log('Received data (function: callback) - "{}"'.format(data))

    async def _started_service(self) -> None:
        self.log('Subscribing to messages on topic "example-pubsub-callback"')
