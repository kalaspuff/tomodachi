import asyncio
import os
import signal
import uuid
from typing import Any

import tomodachi
from tomodachi.envelope.json_base import JsonBase
from tomodachi.transport.amqp import amqp, amqp_publish


@tomodachi.service
class AMQPService(tomodachi.Service):
    name = "test_amqp"
    log_level = "INFO"
    message_envelope = JsonBase
    options = {"amqp": {"login": "guest", "password": "guest"}}
    closer: asyncio.Future
    test_topic_data_received = False
    test_topic_specified_queue_name_data_received = False
    test_topic_metadata_topic = None
    test_topic_service_uuid = None
    wildcard_topic_data_received = False
    data_uuid = None

    def check_closer(self) -> None:
        if (
            self.test_topic_data_received
            and self.test_topic_specified_queue_name_data_received
            and self.test_topic_specified_queue_name_data_received
        ):
            if not self.closer.done():
                self.closer.set_result(None)

    @amqp("test.topic")
    async def test(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            self.test_topic_data_received = True
            self.test_topic_metadata_topic = metadata.get("topic")
            self.test_topic_service_uuid = service.get("uuid")

            self.check_closer()

    @amqp("test.topic", queue_name="test-queue")
    async def test_specified_queue_name(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            if self.test_topic_specified_queue_name_data_received:
                raise Exception("test_topic_specified_queue_name_data_received already set")
            self.test_topic_specified_queue_name_data_received = True

            self.check_closer()

    @amqp("test.topic", queue_name="test-queue")
    async def test_specified_queue_name_again(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            if self.test_topic_specified_queue_name_data_received:
                raise Exception("test_topic_specified_queue_name_data_received already set")
            self.test_topic_specified_queue_name_data_received = True

            self.check_closer()

    @amqp("test.#")
    async def wildcard_topic(self, metadata: Any, data: Any) -> None:
        if data == self.data_uuid:
            self.wildcard_topic_data_received = True

            self.check_closer()

    async def _start_service(self) -> None:
        self.closer = asyncio.Future()

    async def _started_service(self) -> None:
        async def publish(data: Any, routing_key: str) -> None:
            await amqp_publish(self, data, routing_key=routing_key, wait=True)

        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(10.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            task = asyncio.ensure_future(sleep_and_kill())
            await self.closer
            if not task.done():
                task.cancel()
            tomodachi.exit()

        asyncio.ensure_future(_async())

        self.data_uuid = str(uuid.uuid4())
        await publish(self.data_uuid, "test.topic")

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
