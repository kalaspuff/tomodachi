import os
from typing import Any, Callable, Dict

import tomodachi
from tomodachi import aws_sns_sqs, aws_sns_sqs_publish
from tomodachi.discovery import AWSSNSRegistration
from tomodachi.envelope import JsonBase


async def middleware_function(
    func: Callable, service: Any, message: Any, topic: str, context: Dict, *args: Any, **kwargs: Any
) -> Any:
    # Functionality before function is called
    service.log("middleware before")

    return_value = await func(*args, **kwargs)

    # There's also the possibility to pass in extra arguments or keywords arguments, for example:
    # return_value = await func(*args, id='overridden', **kwargs)

    # Functinoality after function is called
    service.log("middleware after")

    return return_value


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

    # Adds a middleware function that is run on every incoming message.
    # Several middlewares can be chained.
    message_middleware = [middleware_function]

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = {
        "aws_sns_sqs.region_name": None,  # specify AWS region (example: 'eu-west-1')
        "aws_sns_sqs.aws_access_key_id": None,  # specify AWS access key (example: 'AKIAXNTIENCJIY2STOCI')
        "aws_sns_sqs.aws_secret_access_key": None,  # specify AWS secret key (example: 'f7sha92hNotarealsecretkeyn29ShnSYQi3nzgA')
        "aws_endpoint_urls.sns": None,  # For example 'http://localhost:4575' if localstack is used for testing
        "aws_endpoint_urls.sqs": None,  # For example 'http://localhost:4576' if localstack is used for testing
    }

    @aws_sns_sqs("example-route1")
    async def route1a(self, data: Any) -> None:
        self.log('Received data (function: route1a) - "{}"'.format(data))

    async def _started_service(self) -> None:
        async def publish(data: Any, topic: str) -> None:
            self.log('Publish data "{}"'.format(data))
            await aws_sns_sqs_publish(self, data, topic=topic, wait=False)

        await publish("友達", "example-route1")
