import asyncio
import functools
import os
import uuid as uuid_
from contextlib import contextmanager
from typing import Any, Awaitable, Callable, Dict, Generator, List, Optional

import tomodachi
from tomodachi import Options
from tomodachi.envelope import JsonBase
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs, aws_sns_sqs_publish


def middleware_decorator(middleware_func: Callable[..., Generator[Awaitable, None, None]]) -> Callable[..., Awaitable]:
    _middleware_func = contextmanager(middleware_func)

    @functools.wraps(middleware_func)
    async def wrapped_middleware_func(func: Callable, service: Any, *args: Any, **kwargs: Any) -> Any:
        with _middleware_func(func, service, *args, **kwargs) as task:
            await task

    return wrapped_middleware_func


@middleware_decorator
def middleware_init_000(
    func: Callable,
    _: Any,
    *,
    message_attributes: Dict,
) -> Generator[Awaitable, None, None]:
    # Message attribute "initial_a_value" set to both "initial_a_value" and "a_value" kwargs. Default to 1 if missing.
    initial_a_value = int(message_attributes.get("initial_a_value", 1))

    # Adds a keyword argument "middlewares_called" which following middlewares will append data to.
    middlewares_called = ["middleware_init_000"]

    # Calls the function (or next middleware in chain) with the above defined keyword arguments.
    yield func(
        initial_a_value=initial_a_value,
        a_value=initial_a_value,
        middlewares_called=middlewares_called,
    )


@middleware_decorator
def middleware_func_abc(
    func: Callable,
    _: Any,
    *,
    a_value: int = 0,
    middlewares_called: Optional[List] = None,
) -> Generator[Awaitable, None, None]:
    # Adds another kwarg, "kwarg_abc" with static value 4711.
    kwarg_abc = 4711

    # Multiplies the keyword argument "a_value" by two.
    a_value = a_value * 2

    # Appends a string to the list associated with keyword argument "middlewares_called".
    middlewares_called = (middlewares_called or []) + ["middleware_func_abc"]

    # Calls the function (or next middleware in chain) with the above defined keyword arguments.
    yield func(
        kwarg_abc=kwarg_abc,
        a_value=a_value,
        middlewares_called=middlewares_called,
    )


@middleware_decorator
def middleware_func_xyz(
    func: Callable,
    _: Any,
    a_value: int = 0,
    **kwargs: Any,
) -> Generator[Awaitable, None, None]:
    # Adds another kwarg, "kwarg_xyz", adding 1 to the value of "kwarg_abc" if present.
    kwarg_xyz = int(kwargs.get("kwarg_abc", 0)) + 1

    # Multiplies the keyword argument "a_value" by three.
    a_value = a_value * 3

    # Appends a string to the list associated with keyword argument "middlewares_called".
    middlewares_called = kwargs.get("middlewares_called", []) + ["middleware_func_xyz"]

    # Calls the function (or next middleware in chain) with the above defined keyword arguments.
    yield func(
        kwarg_xyz=kwarg_xyz,
        a_value=a_value,
        middlewares_called=middlewares_called,
    )


async def middleware_last_in_chain(
    func: Callable,
    *,
    message_uuid: str,
    message: dict,
    topic: str,
    message_attributes: dict,
    middlewares_called: list[str],
) -> None:
    if not message_uuid or message["metadata"].get("message_uuid") != message_uuid:
        raise ValueError(
            f"Message UUID mismatch (kwarg: '{message_uuid}', metadata: '{message['metadata'].get('message_uuid')}'"
        )

    # Mutable values such as lists, dicts and objects could cause unwanted effects if modified in place.
    # This is not a recommended pattern, but for these test cases we're changing the mutable object.
    middlewares_called.append("middleware_last_in_chain")
    await func()

    """
    A better way instead of modifying the mutable object, would be to do something like this:
    1. First create a new list that holds both the old and the new values.
    2. Then pass the new list to the function or next middleware in chain by specifying it as a kwarg.
    """
    # middlewares_called = middlewares_called + ["middleware_last_in_chain"]
    # await func(middlewares_called=middlewares_called)

    """
    The same but done as on one line:
    """
    # await func(middlewares_called=middlewares_called + ["middleware_last_in_chain"])


data_uuid = str(uuid_.uuid4())


class AWSSNSSQSService(tomodachi.Service):
    name = "test_aws_sns_sqs"
    log_level = "INFO"
    message_envelope = JsonBase
    options = Options(
        aws_sns_sqs=Options.AWSSNSSQS(
            region_name=os.environ.get("TOMODACHI_TEST_AWS_REGION"),
            aws_access_key_id=os.environ.get("TOMODACHI_TEST_AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("TOMODACHI_TEST_AWS_ACCESS_SECRET"),
            queue_name_prefix=os.environ.get("TOMODACHI_TEST_SQS_QUEUE_PREFIX") or "",
            topic_prefix=os.environ.get("TOMODACHI_TEST_SNS_TOPIC_PREFIX") or "",
        ),
        aws_endpoint_urls=Options.AWSEndpointURLs(
            sns=os.environ.get("TOMODACHI_TEST_AWS_SNS_ENDPOINT_URL") or None,
            sqs=os.environ.get("TOMODACHI_TEST_AWS_SQS_ENDPOINT_URL") or None,
        ),
    )
    message_middleware: List[Callable[..., Awaitable[Any]]] = [
        middleware_init_000,
        middleware_func_abc,
        middleware_func_xyz,
        middleware_last_in_chain,
    ]

    uuid = os.environ.get("TOMODACHI_TEST_SERVICE_UUID") or ""
    closer: asyncio.Future
    test_topic_data_received = False
    test_topic_name: str = ""
    test_queue_url: str = ""
    test_receipt_handle: str = ""
    test_message_attributes: Optional[Dict] = None
    test_approximate_receive_count: int = 0
    test_middleware_values: Optional[Dict] = None

    data_uuid = data_uuid

    def check_closer(self) -> None:
        if self.test_topic_data_received and self.test_message_attributes:
            if not self.closer.done():
                self.closer.set_result(None)

    @aws_sns_sqs("test-middleware-topic", queue_name="test-middleware-{}".format(data_uuid))
    async def test_middleware_kwargs(
        self,
        data: Any,
        kwarg_abc: int,
        kwarg_xyz: int,
        message_attributes: Dict,
        initial_a_value: int,
        topic: str,
        a_value: int = 0,
        another_value: int = 42,
        queue_url: str = "",
        receipt_handle: str = "",
        approximate_receive_count: int = 0,
        *,
        middlewares_called: List[str],
    ) -> None:
        if not self.test_topic_data_received and data == self.data_uuid:
            self.test_topic_data_received = True
            self.test_topic_name = topic
            self.test_queue_url = queue_url
            self.test_receipt_handle = receipt_handle
            self.test_message_attributes = message_attributes
            self.test_approximate_receive_count = approximate_receive_count
            self.test_middleware_values = {
                "kwarg_abc": kwarg_abc,
                "kwarg_xyz": kwarg_xyz,
                "initial_a_value": initial_a_value,
                "a_value": a_value,
                "another_value": another_value,
                "middlewares_called": middlewares_called,
            }

            self.check_closer()

    async def _start_service(self) -> None:
        self.closer = asyncio.Future()

    async def _started_service(self) -> None:
        async def publish(data: Any, topic: str, **kwargs: Any) -> None:
            await aws_sns_sqs_publish(self, data, topic=topic, wait=False, **kwargs)

        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(90.0)
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
                if self.test_topic_data_received:
                    break

                await publish(
                    self.data_uuid,
                    "test-middleware-topic",
                    message_attributes={"attr_1": "value_1", "attr_2": "value_2", "initial_a_value": 5},
                )
                await asyncio.sleep(0.5)

        asyncio.ensure_future(_async_publisher())

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
