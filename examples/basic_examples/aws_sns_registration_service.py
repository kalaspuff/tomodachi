import os
from typing import Dict

import tomodachi
from tomodachi import aws_sns_sqs
from tomodachi.envelope import JsonBase
from tomodachi.options import Options


class AWSSNSRegistrationService(tomodachi.Service):
    name = "example-aws-sns-registration-service"
    log_level = "INFO"
    uuid = str(os.environ.get("SERVICE_UUID") or "")

    # The message envelope class defines how a message should be processed when sent and received
    # See tomodachi/envelope/json_base.py for a basic example using JSON and transferring some metadata
    message_envelope = JsonBase

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = Options(
        aws_sns_sqs=Options.AWSSNSSQS(
            region_name=None,  # Specify AWS region (example: "eu-west-1")
            aws_access_key_id=None,  # Specify AWS access key (example: "AKIA****************"")
            aws_secret_access_key=None,  # Specify AWS secret key (example: "****************************************")
        ),
    )

    @aws_sns_sqs("services-registration-register", queue_name="registration-service--register")
    async def register(self, data: Dict) -> None:
        self.log('Register service "{}" [id: {}]'.format(data.get("name"), data.get("uuid")))

    @aws_sns_sqs("services-registration-deregister", queue_name="registration-service--deregister")
    async def deregister(self, data: Dict) -> None:
        self.log('Deregister service "{}" [id: {}]'.format(data.get("name"), data.get("uuid")))
