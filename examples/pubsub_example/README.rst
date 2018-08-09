The example has three parts:
* ``service_a.py``: consumes an SQS queue which subscribes to messages from the SNS topic ``example-pubsub-new-message``. When receiving a new message it will forward the message onto the SNS topic ``example-pubsub-callback``.
* ``service_b.py``: consumes an SQS queue which subscribes to messages from the SNS topic ``example-pubsub-callback``.
* ``service_send_message.py``: sends a new message every 10 seconds on the SNS topic ``example-pubsub-new-message``.

Preferrably set up a configuration file with your AWS credentials or manually change the values in the example files.

Example ``aws_sns_sqs_credentials.json``:
```json
{
    "options": {
        "aws": {
            "region_name": "eu-west-1",
            "aws_access_key_id": "AKIAXE2KODGEP8JJ6LZC",
            "aws_secret_access_key": "abtst2t32a84MJsA53gIKDR.CX55o2gNDsS/00f",
        },
        "aws_sns_sqs": {
            "queue_name_prefix": "tomodachi-",
            "topic_prefix": "tomodachi-"
        },
    }
}
```

Run the examples by starting the three services in different shells and watch the output.

```bash
$ tomodachi run examples/pubsub_example/service_send_message.py -c aws_sns_sqs_credentials.json
```

```bash
$ tomodachi run examples/pubsub_example/service_a.py -c aws_sns_sqs_credentials.json
```

```bash
$ tomodachi run examples/pubsub_example/service_b.py -c aws_sns_sqs_credentials.json
```