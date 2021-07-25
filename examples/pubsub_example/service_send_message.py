import uuid

import tomodachi
from tomodachi import aws_sns_sqs_publish, schedule
from tomodachi.envelope import JsonBase


class ServiceSendMessage(tomodachi.Service):
    name = "example-service-send-message"
    message_envelope = JsonBase

    options = {
        "aws_sns_sqs.region_name": None,  # specify AWS region (example: 'eu-west-1')
        "aws_sns_sqs.aws_access_key_id": None,  # specify AWS access key (example: 'AKIAXNTIENCJIY2STOCI')
        "aws_sns_sqs.aws_secret_access_key": None,  # specify AWS secret key
        "aws_endpoint_urls.sns": None,  # For example 'http://localhost:4575' if localstack is used for testing
        "aws_endpoint_urls.sqs": None,  # For example 'http://localhost:4576' if localstack is used for testing
    }

    @schedule(interval=10, immediately=True)
    async def send_message_interval(self) -> None:
        data = str(uuid.uuid4())
        topic = "example-pubsub-new-message"

        self.log(f"Publishing message '{data}' on topic '{topic}'")
        await aws_sns_sqs_publish(self, data, topic=topic, wait=True)
