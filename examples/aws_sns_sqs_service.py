import logging
import os
from tomodachi.discovery.aws_sns_registration import AWSSNSRegistration
from tomodachi.protocol.json_base import JsonBase
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs, aws_sns_sqs_publish


class ExampleAWSSNSSQSService(object):
    name = 'example_aws_sns_sqs_service'
    log_level = 'INFO'
    discovery = [AWSSNSRegistration]
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

    @aws_sns_sqs('example.route1', ('data',))
    async def route1a(self, data):
        self.logger.info('Received data (function: route1a) - "{}"'.format(data))

    @aws_sns_sqs('example.route1', ('data',))
    async def route1b(self, data):
        self.logger.info('Received data (function: route1b) - "{}"'.format(data))

    @aws_sns_sqs('example.route2', ('data',))
    async def route2(self, data):
        self.logger.info('Received data (function: route2) - "{}"'.format(data))

    @aws_sns_sqs('example.#', ('metadata', 'data'))
    async def wildcard_route(self, metadata, data):
        self.logger.info('Received data (function: wildcard_route, topic: {}) - "{}"'.format(metadata.get('topic', ''), data))

    async def _started_service(self):
        async def publish(data, topic):
            self.logger.info('Publish data "{}"'.format(data))
            await aws_sns_sqs_publish(self, data, topic=topic, wait=False)

        await publish('友達', 'example.route1')
        await publish('other data', 'example.route2')
