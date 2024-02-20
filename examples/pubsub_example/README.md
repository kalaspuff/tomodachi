# Services publishing and subscribing to messages

Example of microservices utilizing a PubSub architecture, subscribing to topics via AWS SNS and AWS SQS. The same solution could also be utilized for AMQP / RabbitMQ by using the ``@amqp`` decorator instead of ``@aws_sns_sqs``.

## ``service_a.py``

Consumes an SQS queue which subscribes to messages from the SNS topic ``example-pubsub-new-message``. When receiving a new message it will forward the message onto the SNS topic ``example-pubsub-callback``.

## ``service_b.py``

Consumes an SQS queue which subscribes to messages from the SNS topic ``example-pubsub-callback``.

## ``service_send_message.py``

Sends a new message every 10 seconds on the SNS topic ``example-pubsub-new-message``.

---

Modify the options in the three example files to either use your own AWS credentials or to set them up to connect to a locally running localstack environment.

```python
# example of options for connecting to localstack

options = Options(
    aws_sns_sqs=Options.AWSSNSSQS(
        region_name="eu-west-1",
        aws_access_key_id="AKIAXXXXXXXXXXXXXXXX",
        aws_secret_access_key="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
    ),
    aws_endpoint_urls=Options.AWSEndpointURLs(
        sns="http://localhost:4566",
        sqs="http://localhost:4566",
    ),
)
```

**Run the examples by starting the three services in different shells and watch the output.**

```bash
tomodachi run examples/pubsub_example/service_send_message.py
```

```bash
tomodachi run examples/pubsub_example/service_a.py
```

```bash
tomodachi run examples/pubsub_example/service_b.py
```

## Full code for ``service_a.py``

```python
from typing import Any

import tomodachi
from tomodachi import aws_sns_sqs, aws_sns_sqs_publish, Options
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
        tomodachi.get_logger().info(f"Received data (function: new_message) - '{data}'")

        callback_data = f"message received: '{data}'"
        await aws_sns_sqs_publish(self, callback_data, topic="example-pubsub-callback", wait=True)

    async def _started_service(self) -> None:
        tomodachi.get_logger().info("Subscribing to messages on topic 'example-pubsub-new-message'")
```
