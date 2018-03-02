import logging
import os
import tomodachi
from typing import Dict
from tomodachi.protocol.json_base import JsonBase
from tomodachi import aws_sns_sqs


@tomodachi.service
class AWSSNSRegistrationService(object):
    name = 'example_aws_sns_registration_service'
    log_level = 'INFO'
    message_protocol = JsonBase
    options = {
        'aws_sns_sqs': {
            'region_name': None,  # specify AWS region (example: 'eu-west-1')
            'aws_access_key_id': None,  # specify AWS access key (example: 'AKIAXNTIENCJIY2STOCI')
            'aws_secret_access_key': None  # specify AWS secret key (example: 'f7sha92hNotarealsecretkeyn29ShnSYQi3nzgA')
        },
        'aws_endpoint_urls': {
            'sns': None,  # For example 'http://localhost:4575' if localstack is used for testing
            'sqs': None  # For example 'http://localhost:4576' if localstack is used for testing
        }
    }
    logger = logging.getLogger('log.{}'.format(name))
    uuid = os.environ.get('SERVICE_UUID')

    @aws_sns_sqs('services.registration.register', queue_name='registration-service--register', competing=True)
    async def register(self, data: Dict) -> None:
        self.logger.info('Register service "{}" [id: {}]'.format(data.get('name'), data.get('uuid')))

    @aws_sns_sqs('services.registration.deregister', queue_name='registration-service--deregister', competing=True)
    async def deregister(self, data: Dict) -> None:
        self.logger.info('Deregister service "{}" [id: {}]'.format(data.get('name'), data.get('uuid')))
