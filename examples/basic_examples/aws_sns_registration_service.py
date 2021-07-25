import os
from typing import Dict

import tomodachi
from tomodachi import aws_sns_sqs
from tomodachi.envelope import JsonBase


class AWSSNSRegistrationService(tomodachi.Service):
    name = "example-aws-sns-registration-service"
    log_level = "INFO"
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

    @aws_sns_sqs("services-registration-register", queue_name="registration-service--register")
    async def register(self, data: Dict) -> None:
        self.log('Register service "{}" [id: {}]'.format(data.get("name"), data.get("uuid")))

    @aws_sns_sqs("services-registration-deregister", queue_name="registration-service--deregister")
    async def deregister(self, data: Dict) -> None:
        self.log('Deregister service "{}" [id: {}]'.format(data.get("name"), data.get("uuid")))
