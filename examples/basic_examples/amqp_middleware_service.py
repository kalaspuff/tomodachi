import os
import tomodachi
from typing import Any, Dict, Callable
from tomodachi import amqp, amqp_publish
from tomodachi.discovery import DummyRegistry
from tomodachi.protocol import JsonBase


async def middleware_function(func: Callable, service: Any, message: Any, *args: Any, **kwargs: Any) -> Any:
    # Functionality before function is called
    service.log('middleware before')

    return_value = await func(*args, **kwargs)

    # There's also the possibility to pass in extra arguments or keywords arguments, for example:
    # return_value = await func(*args, id='overridden', **kwargs)

    # Functinoality after function is called
    service.log('middleware after')

    return return_value


@tomodachi.service
class ExampleAmqpService(tomodachi.Service):
    name = 'example_amqp_service'
    log_level = 'INFO'
    uuid = os.environ.get('SERVICE_UUID')

    # Build own "discovery" functions, to be run on start and stop
    # See tomodachi/discovery/dummy_registry.py for example
    discovery = [DummyRegistry]

    # The message protocol class defines how a message should be processed when sent and received
    # See tomodachi/protocol/json_base.py for a basic example using JSON and transferring some metadata
    message_protocol = JsonBase

    # Adds a middleware function that is run on every incoming message.
    # Several middlewares can be chained.
    message_middleware = [middleware_function]

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = {
        'amqp': {
            'queue_ttl': 60
        }
    }

    @amqp('example.route1')
    async def route1a(self, data: Any) -> None:
        self.log('Received data (function: route1a) - "{}"'.format(data))

    async def _started_service(self) -> None:
        async def publish(data: Any, routing_key: str) -> None:
            self.log('Publish data "{}"'.format(data))
            await amqp_publish(self, data, routing_key=routing_key)

        await publish('友達', 'example.route1')
