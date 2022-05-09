import os
from typing import Any

import tomodachi
from tomodachi import aws_sns_sqs, aws_sns_sqs_publish
from tomodachi.discovery import AWSSNSRegistration
from tomodachi.envelope import JsonBase
from tomodachi.transport.aws_sns_sqs import AWSSNSSQSInternalServiceError

failed = False


class ExampleAWSSNSSQSService(tomodachi.Service):
    name = "example-aws-sns-sqs-fifo-service"
    log_level = "INFO"
    discovery = [AWSSNSRegistration]
    uuid = str(os.environ.get("SERVICE_UUID") or "")

    # The message envelope class defines how a message should be processed when sent and received
    # See tomodachi/envelope/json_base.py for a basic example using JSON and transferring some metadata
    message_envelope = JsonBase

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = {
        "aws_sns_sqs.region_name": None,  # specify AWS region (example: 'eu-west-1')
        "aws_sns_sqs.aws_access_key_id": None,  # specify AWS access key (example: 'AKIAXNTIENCJIY2STOCI')
        "aws_sns_sqs.aws_secret_access_key": None,  # specify AWS secret key (example: 'f7sha92hNotarealsecretkeyn29ShnSYQi3nzgA')
        "aws_endpoint_urls.sns": None,  # For example 'http://localhost:4575' if localstack is used for testing
        "aws_endpoint_urls.sqs": None,  # For example 'http://localhost:4576' if localstack is used for testing
    }

    failed: bool

    @aws_sns_sqs("example-fifo-route-1", queue_name="test-fifo-queue.fifo", fifo=True)
    async def route(self, data: Any) -> None:
        self.log('Received data (function: route) - "{}"'.format(data))
        if data == "2" and not self.failed:
            self.log("Failing the message on purpose")
            self.failed = True
            raise AWSSNSSQSInternalServiceError("boom")

    async def _started_service(self) -> None:
        async def publish(data: Any, topic: str, group_id: str) -> None:
            self.log('Publish data "{}"'.format(data))
            await aws_sns_sqs_publish(self, data, topic=topic, group_id=group_id)

        self.failed = False

        await publish("1", "example-fifo-route-1", "group-1")
        await publish("2", "example-fifo-route-1", "group-1")
        await publish("3", "example-fifo-route-1", "group-1")
