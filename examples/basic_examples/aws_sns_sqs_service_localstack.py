import os
from typing import Any

import tomodachi
from tomodachi import aws_sns_sqs, aws_sns_sqs_publish
from tomodachi.discovery import AWSSNSRegistration
from tomodachi.envelope import JsonBase
from tomodachi.transport.aws_sns_sqs import AWSSNSSQSInternalServiceError


class ExampleAWSSNSSQSService(tomodachi.Service):
    name = "example-aws-sns-sqs-service"
    log_level = "INFO"
    uuid = str(os.environ.get("SERVICE_UUID") or "")

    # Build own "discovery" functions, to be run on start and stop
    # See tomodachi/discovery/aws_sns_registration.py for example
    discovery = [AWSSNSRegistration]

    # The message envelope class defines how a message should be processed when sent and received
    # See tomodachi/envelope/json_base.py for a basic example using JSON and transferring some metadata
    message_envelope = JsonBase

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = {
        "aws_sns_sqs.region_name": "eu-west-1",  # specify AWS region (example: 'eu-west-1')
        "aws_sns_sqs.aws_access_key_id": "AKIAXNTIENCJIY2STOCI",  # specify AWS access key (example: 'AKIAXNTIENCJIY2STOCI') - this is not real credentials
        "aws_sns_sqs.aws_secret_access_key": "f7sha92hNotarealsecretkeyn29ShnSYQi3nzgA",  # specify AWS secret key (example: 'f7sha92hNotarealsecretkeyn29ShnSYQi3nzgA') - this is not real credentials
        "aws_endpoint_urls.sns": "http://localhost:4567",  # For example 'http://localhost:4566' (or 4567, port may vary) if localstack is used for testing
        "aws_endpoint_urls.sqs": "http://localhost:4567",  # For example 'http://localhost:4566' (or 4567, port may vary) if localstack is used for testing
    }

    @aws_sns_sqs("example-route1", queue_name="queue-1")
    async def route1a(self, data: Any) -> None:
        self.log('Received data (function: route1a) - "{}"'.format(data))

    @aws_sns_sqs("example-route1", queue_name="queue-2")
    async def route1b(self, data: Any) -> None:
        self.log('Received data (function: route1b) - "{}"'.format(data))

    @aws_sns_sqs("example-route2", queue_name="queue-3")
    async def route2(self, data: Any) -> None:
        self.log('Received data (function: route2) - "{}"'.format(data))

    async def _started_service(self) -> None:
        async def publish(data: Any, topic: str) -> None:
            self.log('Publish data "{}"'.format(data))
            await aws_sns_sqs_publish(self, data, topic=topic, wait=False)

        await publish("友達", "example-route1")
        await publish("other data", "example-route2")
