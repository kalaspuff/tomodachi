Services publishing and subscribing to messages
-----------------------------------------------
Example of microservices utilizing a PubSub architecture, subscribing to topics via AWS SNS and AWS SQS. The same solution could also be utilized for AMQP / RabbitMQ by using the ``@amqp`` decorator instead of ``@aws_sns_sqs``.

``service_a.py``
  consumes an SQS queue which subscribes to messages from the SNS topic ``example-pubsub-new-message``. When receiving a new message it will forward the message onto the SNS topic ``example-pubsub-callback``.

``service_b.py``
  consumes an SQS queue which subscribes to messages from the SNS topic ``example-pubsub-callback``.

``service_send_message.py``
  sends a new message every 10 seconds on the SNS topic ``example-pubsub-new-message``.


Preferrably set up a configuration file with your AWS credentials or manually change the values in the example files.

**Example** ``aws_sns_sqs_credentials.json``

.. code:: json

    {
        "options": {
            "aws": {
                "region_name": "eu-west-1",
                "aws_access_key_id": "AKIFAKEKEYNOTREALZ35",
                "aws_secret_access_key": "abtst2/Passw0rdSup3rS3creT.5o2gNDsS/00f"
            },
            "aws_sns_sqs": {
                "queue_name_prefix": "tomodachi-",
                "topic_prefix": "tomodachi-"
            }
        }
    }


**Run the examples by starting the three services in different shells and watch the output.**

.. code:: bash

    $ tomodachi run examples/pubsub_example/service_send_message.py -c aws_sns_sqs_credentials.json

.. code:: bash

    $ tomodachi run examples/pubsub_example/service_a.py -c aws_sns_sqs_credentials.json

.. code:: bash

    $ tomodachi run examples/pubsub_example/service_b.py -c aws_sns_sqs_credentials.json


Full code for ``service_a.py``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

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
            self.log(f"Received data (function: new_message) - '{data}'")

            callback_data = f"message received: '{data}'"
            await aws_sns_sqs_publish(self, callback_data, topic="example-pubsub-callback", wait=True)

        async def _started_service(self) -> None:
            self.log("Subscribing to messages on topic 'example-pubsub-new-message'")
