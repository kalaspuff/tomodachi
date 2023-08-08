import asyncio
import os
import uuid
from functools import wraps
from typing import Any, Callable, Set

import aiohttp
from aiohttp import web

import tomodachi

data_uuid = str(uuid.uuid4())


class MessageEvent:
    def __init__(self, data: Any, topic: str, sns_message_id: str = "") -> None:
        self.data = data
        self.topic = topic
        self.sns_message_id = sns_message_id


def sqs_wrapper(*args: Any, **kwargs: Any) -> Any:
    def _wrap(func: Callable) -> Any:
        @tomodachi.aws_sns_sqs(*args, **kwargs)
        @wraps(func, assigned=("__module__", "__doc__", "__name__", "__qualname__"))
        async def _wrapper(self: Any, data: Any, topic: str, sns_message_id: str) -> None:
            await func(self, event=MessageEvent(data, topic, sns_message_id))

        return _wrapper

    return _wrap


class Service(tomodachi.Service):
    name = "service"
    options = tomodachi.Options(
        http=tomodachi.Options.HTTP(port=0),
        aws_sns_sqs=tomodachi.Options.AWSSNSSQS(
            region_name=os.environ.get("TOMODACHI_TEST_AWS_REGION"),
            aws_access_key_id=os.environ.get("TOMODACHI_TEST_AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("TOMODACHI_TEST_AWS_ACCESS_SECRET"),
            queue_name_prefix=os.environ.get("TOMODACHI_TEST_SQS_QUEUE_PREFIX") or "",
            topic_prefix=os.environ.get("TOMODACHI_TEST_SNS_TOPIC_PREFIX") or "",
        ),
        aws_endpoint_urls=tomodachi.Options.AWSEndpointURLs(
            sns=os.environ.get("TOMODACHI_TEST_AWS_SNS_ENDPOINT_URL") or None,
            sqs=os.environ.get("TOMODACHI_TEST_AWS_SQS_ENDPOINT_URL") or None,
        ),
    )

    closer: asyncio.Future
    test_received_from_topics: Set[str]
    test_topic_data_received: bool = False
    test_http_handler_called: bool = False
    test_http_endpoint_response: str = ""

    data_uuid = data_uuid

    def check_closer(self) -> None:
        if all(
            [
                len(self.test_received_from_topics) == 2,
                self.test_http_handler_called,
                self.test_http_endpoint_response == "the-expected-response",
            ]
        ):
            if not self.closer.done():
                self.closer.set_result(None)

    @tomodachi.http("GET", r"/")
    async def basic_http_request_handler(self, request: web.Request) -> web.Response:
        self.test_http_handler_called = True
        return web.Response(body="the-expected-response")

    @tomodachi.http("GET", r"/x/(?P<value1>[^/]+)/?")
    @tomodachi.http("GET", r"/y(?P<value1>[^/]+)/(?P<value2>[^/]+)/?")
    @tomodachi.http("GET", r"/z/?")
    async def multi_http_request_handler(
        self, request: web.Request, value1: str = "", value2: str = ""
    ) -> web.Response:
        self.test_http_handler_called = True
        return web.Response(body=f"{request.path} {value1} {value2}")

    @sqs_wrapper("test-wrapped-invoker", queue_name="test-wrapped-invoker-{}".format(data_uuid))
    @sqs_wrapper("test-wrapped-invoker-2", queue_name="test-wrapped-invoker-2-{}".format(data_uuid))
    async def sqs_handler(
        self,
        event: MessageEvent,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if args or kwargs:
            raise Exception("function should be called without any additional arguments")
        if not event.sns_message_id or not event.topic:
            raise Exception("event should include sns_message_id and topic")

        if event.topic not in self.test_received_from_topics and event.data == self.data_uuid:
            self.test_received_from_topics.add(event.topic)
            self.check_closer()

    async def _start_service(self) -> None:
        self.closer = asyncio.Future()
        self.test_received_from_topics = set()

    async def _started_service(self) -> None:
        async def publish(data: Any, topic: str, **kwargs: Any) -> None:
            await tomodachi.aws_sns_sqs_publish(self, data, topic=topic, wait=False, **kwargs)

        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(30.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            task = asyncio.ensure_future(sleep_and_kill())
            await self.closer
            if not task.done():
                task.cancel()
            tomodachi.exit()

        asyncio.ensure_future(_async())

        async def _async_publisher() -> None:
            for _ in range(10):
                if len(self.test_received_from_topics) == 2:
                    break

                if "test-wrapped-invoker" not in self.test_received_from_topics:
                    await publish(self.data_uuid, "test-wrapped-invoker")

                if "test-wrapped-invoker-2" not in self.test_received_from_topics:
                    await publish(self.data_uuid, "test-wrapped-invoker-2")

                await asyncio.sleep(0.5)

        async def _http_requester() -> None:
            port = getattr(self, "context", {}).get("_http_port")

            async with aiohttp.ClientSession() as client:
                response = await client.get("http://127.0.0.1:{}/x/4711".format(port))
                if response.status != 200 or (await response.text()) != "/x/4711 4711 ":
                    raise Exception("invalid response")

            async with aiohttp.ClientSession() as client:
                response = await client.get("http://127.0.0.1:{}/ytest/0".format(port))
                if response.status != 200 or (await response.text()) != "/ytest/0 test 0":
                    raise Exception("invalid response")

            async with aiohttp.ClientSession() as client:
                response = await client.get("http://127.0.0.1:{}/z".format(port))
                if response.status != 200 or (await response.text()) != "/z  ":
                    raise Exception("invalid response")

            async with aiohttp.ClientSession() as client:
                response = await client.get("http://127.0.0.1:{}/".format(port))
                if response.status != 200:
                    raise Exception("invalid response status code")
                self.test_http_endpoint_response = await response.text()
                self.check_closer()

        asyncio.ensure_future(_async_publisher())
        asyncio.ensure_future(_http_requester())

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
