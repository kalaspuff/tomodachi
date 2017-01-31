import logging
from tomodachi.discovery.registry import Registry
from tomodachi.protocol.json_base import JsonBase
from tomodachi.transport.amqp import amqp, amqp_publish


class ExampleAmqpService(object):
    name = 'example_amqp_service'
    log_level = 'INFO'
    discovery = [Registry]
    options = {
        'amqp': {
            'exchange_name': 'example_exchange',
            'message_protocol': JsonBase,
            'queue_ttl': 60
        }
    }
    logger = logging.getLogger('log.{}'.format(name))

    @amqp('example.route1', ('data',))
    async def route1a(self, data):
        self.logger.info('Received data on example.route1a "{}"'.format(data))
        pass

    @amqp('example.route1', ('data',))
    async def route1b(self, data):
        self.logger.info('Received data on example.route1b "{}"'.format(data))
        pass

    @amqp('example.route2', ('data',))
    async def route2(self, data):
        self.logger.info('Received data on example.route2 "{}"'.format(data))
        pass

    async def _started_service(self):
        async def publish(data, routing_key):
            self.logger.info('Publish data "{}"'.format(data))
            await amqp_publish(self, data, routing_key=routing_key)

        await publish('友達', 'example.route1')
        await publish('other data', 'example.route2')
