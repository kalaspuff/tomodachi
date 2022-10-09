import asyncio
import os
import signal
import uuid
from typing import Any

import tomodachi
from tomodachi.transport.amqp import amqp, amqp_publish

data_uuid = str(uuid.uuid4())


@tomodachi.service
class AWSSNSSQSService(tomodachi.Service):
    name = "test_amqp"
    log_level = "INFO"
    options = {"amqp": {"login": "guest", "password": "guest"}}
    closer: asyncio.Future
    test_topic_data_received = False
    test_topic_data = None
    data_uuid = data_uuid

    def check_closer(self) -> None:
        if self.test_topic_data_received:
            if not self.closer.done():
                self.closer.set_result(None)

    @amqp("test.raw.topic")
    async def test(self, value: Any, default_value: bool = True) -> None:
        if value == self.data_uuid:
            self.test_topic_data_received = default_value
            self.test_topic_data = value

            self.check_closer()

    async def _start_service(self) -> None:
        self.closer = asyncio.Future()

    async def _started_service(self) -> None:
        async def publish(data: Any, routing_key: str) -> None:
            await amqp_publish(self, data, routing_key=routing_key, wait=False)

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

        await publish(self.data_uuid, "test.raw.topic")

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
