from typing import Any, Dict

import tomodachi
from tomodachi import Options, amqp, amqp_publish
from tomodachi.envelope import JsonBase


class ExampleAmqpService(tomodachi.Service):
    name = "example-amqp-service"

    # The message envelope class defines how a message should be processed when sent and received
    # See tomodachi/envelope/json_base.py for a basic example using JSON and transferring some metadata
    message_envelope = JsonBase

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = Options(amqp=Options.AMQP(queue_ttl=60))

    @amqp("example.route1")
    async def route1a(self, data: Any) -> None:
        tomodachi.get_logger().info('Received data (function: route1a) - "{}"'.format(data))

    @amqp("example.route1")
    async def route1b(self, data: Any) -> None:
        tomodachi.get_logger().info('Received data (function: route1b) - "{}"'.format(data))

    @amqp("example.route2")
    async def route2(self, data: Any) -> None:
        tomodachi.get_logger().info('Received data (function: route2) - "{}"'.format(data))

    @amqp("example.#")
    async def wildcard_route(self, metadata: Dict, data: Any) -> None:
        tomodachi.get_logger().info(
            'Received data (function: wildcard_route, topic: {}) - "{}"'.format(metadata.get("topic", ""), data)
        )

    async def _started_service(self) -> None:
        async def publish(data: Any, routing_key: str) -> None:
            tomodachi.get_logger().info('Publish data "{}"'.format(data))
            await amqp_publish(self, data, routing_key=routing_key)

        await publish("友達", "example.route1")
        await publish("other data", "example.route2")
