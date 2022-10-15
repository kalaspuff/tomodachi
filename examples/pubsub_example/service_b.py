from typing import Any

import tomodachi
from tomodachi import Options, aws_sns_sqs
from tomodachi.envelope import JsonBase


class ServiceB(tomodachi.Service):
    name = "example-service-b"
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

    @aws_sns_sqs("example-pubsub-callback")
    async def callback(self, data: Any) -> None:
        self.log(f"Received data (function: callback) - '{data}'")

    async def _started_service(self) -> None:
        self.log("Subscribing to messages on topic 'example-pubsub-callback'")
