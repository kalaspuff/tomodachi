import logging
import os
from tomodachi.protocol.json_base import JsonBase
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs


class AWSSNSRegistrationService(object):
    name = 'example_aws_sns_registration_service'
    log_level = 'INFO'
    message_protocol = JsonBase
    options = {
        'aws_sns_sqs': {
            'region_name': None,  # specify AWS region (example: eu-west-1)
            'aws_access_key_id': None,  # specify AWS access key (example: AKIAXNTIENCJIY2STOCI)
            'aws_secret_access_key': None  # specify AWS secret key (example: f7sha92hNotarealsecretkeyn29ShnSYQi3nzgA)
        }
    }
    logger = logging.getLogger('log.{}'.format(name))
    uuid = os.environ.get('SERVICE_UUID')

    @aws_sns_sqs('services.registration.register', ('data',), competing=True)
    async def register(self, data):
        self.logger.info('Register service "{}" [id: {}]'.format(data.get('name'), data.get('uuid')))

    @aws_sns_sqs('services.registration.deregister', ('data',), competing=True)
    async def deregister(self, data):
        self.logger.info('Deregister service "{}" [id: {}]'.format(data.get('name'), data.get('uuid')))
