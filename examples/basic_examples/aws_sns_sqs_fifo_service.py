from typing import Any

import tomodachi
from tomodachi import Options, aws_sns_sqs, aws_sns_sqs_publish
from tomodachi.envelope import JsonBase
from tomodachi.transport.aws_sns_sqs import AWSSNSSQSInternalServiceError


class ExampleAWSSNSSQSService(tomodachi.Service):
    name = "example-aws-sns-sqs-service"

    # The message envelope class defines how a message should be processed when sent and received
    # See tomodachi/envelope/json_base.py for a basic example using JSON and transferring some metadata
    message_envelope = JsonBase

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = Options(
        aws_sns_sqs=Options.AWSSNSSQS(
            region_name=None,  # specify AWS region (example: "eu-west-1")
            aws_access_key_id=None,  # specify AWS access key (example: "AKIA****************"")
            aws_secret_access_key=None,  # specify AWS secret key (example: "****************************************")
        ),
    )

    _failed: bool = False

    @aws_sns_sqs("example-fifo-route-1", queue_name="test-fifo-queue.fifo", fifo=True)
    async def route(self, data: Any) -> None:
        tomodachi.get_logger().info('Received data (function: route) - "{}"'.format(data))
        if data == "2" and not self._failed:
            tomodachi.get_logger().info("Failing the message on purpose")
            self._failed = True
            raise AWSSNSSQSInternalServiceError("boom")

    async def _started_service(self) -> None:
        async def publish(data: Any, topic: str, group_id: str) -> None:
            tomodachi.get_logger().info('Publish data "{}"'.format(data))
            await aws_sns_sqs_publish(self, data, topic=topic, group_id=group_id)

        self._failed = False

        await publish("1", "example-fifo-route-1", "group-1")
        await publish("2", "example-fifo-route-1", "group-1")
        await publish("3", "example-fifo-route-1", "group-1")
