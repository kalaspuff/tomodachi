from typing import Any

import tomodachi
from tomodachi import Options, aws_sns_sqs, aws_sns_sqs_publish
from tomodachi.envelope import JsonBase


class ServiceA(tomodachi.Service):
    name = "example-service-a"
    message_envelope = JsonBase

    options = Options(
        aws_sns_sqs=Options.AWSSNSSQS(
            region_name=None,  # Specify AWS region (example: "eu-west-1")
            aws_access_key_id=None,  # Specify AWS access key (example: "AKIA****************"")
            aws_secret_access_key=None,  # Specify AWS secret key (example: "****************************************")
        ),
        aws_endpoint_urls=Options.AWSEndpointURLs(
            sns=None,  # For example 'http://localhost:4566' (or 4567, port may vary) if localstack is used for testing
            sqs=None,  # For example 'http://localhost:4566' (or 4567, port may vary) if localstack is used for testing
        ),
    )

    @aws_sns_sqs("example-pubsub-new-message")
    async def new_message(self, data: Any) -> None:
        self.log(f"Received data (function: new_message) - '{data}'")

        callback_data = f"message received: '{data}'"
        await aws_sns_sqs_publish(self, callback_data, topic="example-pubsub-callback", wait=True)

    async def _started_service(self) -> None:
        self.log("Subscribing to messages on topic 'example-pubsub-new-message'")
