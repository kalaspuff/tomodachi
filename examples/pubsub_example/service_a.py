from typing import Any

import tomodachi
from tomodachi import aws_sns_sqs, aws_sns_sqs_publish
from tomodachi.envelope import JsonBase


class ServiceA(tomodachi.Service):
    name = "example-service-a"
    message_envelope = JsonBase

    options = {
        "aws_sns_sqs.region_name": None,  # specify AWS region (example: 'eu-west-1')
        "aws_sns_sqs.aws_access_key_id": None,  # specify AWS access key (example: 'AKIAXNTIENCJIY2STOCI')
        "aws_sns_sqs.aws_secret_access_key": None,  # specify AWS secret key
        "aws_endpoint_urls.sns": None,  # For example 'http://localhost:4575' if localstack is used for testing
        "aws_endpoint_urls.sqs": None,  # For example 'http://localhost:4576' if localstack is used for testing
    }

    @aws_sns_sqs("example-pubsub-new-message")
    async def new_message(self, data: Any) -> None:
        self.log(f"Received data (function: new_message) - '{data}'")

        callback_data = f"message received: '{data}'"
        await aws_sns_sqs_publish(self, callback_data, topic="example-pubsub-callback", wait=True)

    async def _started_service(self) -> None:
        self.log("Subscribing to messages on topic 'example-pubsub-new-message'")
