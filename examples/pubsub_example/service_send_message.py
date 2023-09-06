import uuid

import tomodachi
from tomodachi import Options, aws_sns_sqs_publish, schedule
from tomodachi.envelope import JsonBase


class ServiceSendMessage(tomodachi.Service):
    name = "example-service-send-message"
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

    @schedule(interval=10, immediately=True)
    async def send_message_interval(self) -> None:
        data = str(uuid.uuid4())
        topic = "example-pubsub-new-message"

        tomodachi.get_logger().info(f"Publishing message '{data}' on topic '{topic}'")
        await aws_sns_sqs_publish(self, data, topic=topic, wait=True)
