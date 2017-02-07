import logging
from tomodachi.discovery.registry import Registry
from tomodachi.protocol.json_base import JsonBase
from tomodachi.transport.amqp import amqp, amqp_publish


class ExampleAmqpService(object):
    name = 'example_amqp_service'
    log_level = 'INFO'
    discovery = [Registry]
    message_protocol = JsonBase
    options = {
        'amqp': {
            'queue_ttl': 60
        }
    }
    logger = logging.getLogger('log.{}'.format(name))

    @amqp('example.route1', ('data',))
    async def route1a(self, data):
        self.logger.info('Received data (function: route1a) - "{}"'.format(data))
        pass

    @amqp('example.route1', ('data',))
    async def route1b(self, data):
        self.logger.info('Received data (function: route1b) - "{}"'.format(data))
        pass

    @amqp('example.route2', ('data',))
    async def route2(self, data):
        self.logger.info('Received data (function: route2) - "{}"'.format(data))
        pass

    @amqp('example.#', ('metadata', 'data'))
    async def wildcard_route(self, metadata, data):
        self.logger.info('Received data (function: wildcard_route, topic: {}) - "{}"'.format(metadata.get('topic', ''), data))
        pass

    async def _started_service(self):
        async def publish(data, routing_key):
            self.logger.info('Publish data "{}"'.format(data))
            await amqp_publish(self, data, routing_key=routing_key)

        await publish('友達', 'example.route1')
        await publish('other data', 'example.route2')
