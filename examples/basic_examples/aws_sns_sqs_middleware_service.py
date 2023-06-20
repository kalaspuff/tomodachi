import contextvars
import functools
import time
from contextlib import contextmanager
from typing import Any, Awaitable, Callable, Dict, Generator, List, Optional, SupportsInt

import tomodachi
from tomodachi import Options, aws_sns_sqs, aws_sns_sqs_publish
from tomodachi.envelope import JsonBase
from tomodachi.transport.aws_sns_sqs import MessageAttributesType

# Call depth for chained middlewares are tracked for demonstration purposes and used in the service' log function.
CALL_DEPTH_CONTEXTVAR = contextvars.ContextVar("service.middleware.depth", default=0)


def middleware_decorator(middleware_func: Callable[..., Generator[Awaitable, None, None]]) -> Callable[..., Awaitable]:
    _middleware_func = contextmanager(middleware_func)

    @functools.wraps(middleware_func)
    async def wrapped_middleware_func(func: Callable, service: Any, *args: Any, **kwargs: Any) -> Any:
        original_call_depth = CALL_DEPTH_CONTEXTVAR.get()
        if not original_call_depth:
            start_time = time.perf_counter_ns()
            service.log("---")
            CALL_DEPTH_CONTEXTVAR.set(CALL_DEPTH_CONTEXTVAR.get() + 1)

        # Before function (or next middleware in chain) is called.
        service.log("middleware -- {} -- begin".format(middleware_func.__name__))

        # Calls the function (or next middleware in chain).
        with _middleware_func(func, service, *args, **kwargs) as task:
            token = CALL_DEPTH_CONTEXTVAR.set(CALL_DEPTH_CONTEXTVAR.get() + 1)
            await task
            CALL_DEPTH_CONTEXTVAR.reset(token)

        # Calculates total execution time for middlewares and handler.
        elapsed_time_str = ""
        if not original_call_depth:
            elapsed_time_ms = (time.perf_counter_ns() - start_time) / 1000000.0
            elapsed_time_str = " (total elapsed time: {} ms)".format(elapsed_time_ms)

        # After function (or next middleware in chain) is called.
        service.log("middleware -- {} -- end{}".format(middleware_func.__name__, elapsed_time_str))

    return wrapped_middleware_func


@middleware_decorator
def middleware_init_000(
    func: Callable,
    _: Any,
    *,
    message_attributes: MessageAttributesType,
) -> Generator[Awaitable, None, None]:
    # Message attribute "initial_a_value" set to both "initial_a_value" and "a_value" kwargs. Default to 1 if missing.
    initial_a_value = 1
    if "initial_a_value" in message_attributes:
        if not isinstance(message_attributes["initial_a_value"], SupportsInt):
            raise ValueError("Invalid value type for message attribute 'initial_a_value'")
        initial_a_value = int(message_attributes["initial_a_value"])

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


async def a_simple_middleware(
    func: Callable,
    *,
    message: Dict,
    message_uuid: str,
    topic: str,
    middlewares_called: List[str],
) -> None:
    if not message_uuid or not topic or message["metadata"].get("message_uuid") != message_uuid:
        raise ValueError("Invalid message_uuid, topic or message metadata")

    # Mutable values such as lists, dicts and objects could cause unwanted effects if modified in place.
    # It's instead recommended to create a new object and pass it on as the new value for the keyword argument.
    middlewares_called = middlewares_called + ["a_simple_middleware"]
    await func(middlewares_called=middlewares_called)


class ExampleAWSSNSSQSService(tomodachi.Service):
    name = "example-aws-sns-sqs-service"

    # The message envelope class defines how a message should be processed when sent and received
    # See tomodachi/envelope/json_base.py for a basic example using JSON and transferring some metadata
    message_envelope = JsonBase

    # Adds the four example middlewares to run on every incoming message. Middlewares are chained so that
    # the first defined middleware will be called first (and exit last as in a stack).
    message_middleware: List[Callable[..., Awaitable[Any]]] = [
        middleware_init_000,
        middleware_func_abc,
        middleware_func_xyz,
        a_simple_middleware,
    ]

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = Options(
        aws_sns_sqs=Options.AWSSNSSQS(
            region_name="eu-west-1",  # Specify AWS region (example: "eu-west-1")
            aws_access_key_id="AKIAXXXXXXXXXXXXXXXX",  # Specify AWS access key (example: "AKIA****************"")
            aws_secret_access_key="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",  # Specify AWS secret key (example: "****************************************")
        ),
        aws_endpoint_urls=Options.AWSEndpointURLs(
            sns="http://localhost:4567",  # For example 'http://localhost:4566' (or 4567, port may vary) if localstack is used for testing
            sqs="http://localhost:4567",  # For example 'http://localhost:4566' (or 4567, port may vary) if localstack is used for testing
        ),
    )

    @aws_sns_sqs("example-route", max_number_of_consumed_messages=1)
    async def route(
        self,
        data: Any,
        kwarg_abc: int,
        kwarg_xyz: int,
        message_attributes: Dict,
        initial_a_value: int,
        a_value: int = 0,
        another_value: int = 42,
        queue_url: str = "",
        receipt_handle: str = "",
        approximate_receive_count: int = 0,
        *,
        middlewares_called: List[str],
    ) -> None:
        """
        Message handler for the topic "example-route" that demonstrated how middlewares can be used to modify the
        keywords sent to the handler. This handler receives most of its keyword arguments from middlewares, but also
        some from the transport layer (in this case AWS SNS+SQS). The star in the function signature is merely to
        indicate that keywords can be added both before and after the star.

        Args:
            data (Any): The message data received.
            kwarg_abc (int): Value added by the middleware `middleware_func_abc`.
            kwarg_xyz (int): Value added by the middleware `middleware_func_xyz`.
            message_attributes (dict): Message attributes as key-value pairs accompanying the published data.
            initial_a_value (int): Added in `middleware_init_000` using message attribute value (default: `1`).
            a_value (int): Value modified by all three middlewares (should become: `initial_a_value * 2 * 3`).
            another_value (int): Value not modified by any middleware (should always be `42`).
            queue_url (str): Value provided from transport.
            receipt_handle (str): Value provided from transport.
            approximate_receive_count (int): Value provided from transport.
            middlewares_called (list[str]): Appended to by all three middlewares in this example.
        """
        self.log("handler -- route(data='{}', ...)".format(data))

        self.log("value: kwarg_abc (expect 4711) = {}".format(kwarg_abc))
        self.log("value: kwarg_xyz (expect 4712) = {}".format(kwarg_xyz))
        self.log("value: initial_a_value (message attribute) = {}".format(message_attributes.get("initial_a_value")))
        self.log("value: initial_a_value (from keyword args) = {}".format(initial_a_value))
        self.log("value: a_value (expect {}) = {}".format(initial_a_value * 2 * 3, a_value))
        self.log("value: another_value (expect 42) = {}".format(another_value))
        self.log("value: middlewares_called (list) = {}".format(str(middlewares_called)))

        # Some values from the transport layer (in this case AWS SNS+SQS) are passed as keyword arguments if they are
        # specified in the function signature of the message handler. Such kwargs cannot be overwritten by middlewares.
        # If the handler doesn't have a catch-all **kwargs value and does not specify these keywords, the values
        # will not be passed to the handler.

        # * AWS SNS+SQS handler kwargs: queue_url, receipt_handle, message_attributes, approximate_receive_count
        self.log("value: queue_url (str) = '{}'".format(queue_url))
        self.log("value: receipt_handle (str) = '{}'".format(receipt_handle))
        self.log("value: message_attributes (dict) = {}".format(message_attributes))
        self.log("value: approximate_receive_count (int) = {}".format(approximate_receive_count))

    async def _started_service(self) -> None:
        async def publish(data: Any, topic: str, message_attributes: Optional[Dict] = None) -> None:
            if not message_attributes:
                message_attributes = {}
            self.log("publish -- sns.publish(data='{}', message_attributes={})".format(data, message_attributes))
            await aws_sns_sqs_publish(self, data, topic=topic, message_attributes=message_attributes, wait=False)

        await publish("a simple message", "example-route")
        await publish("a message with additional attribute", "example-route", message_attributes={"initial_a_value": 5})

    def log(self, msg: str) -> None:
        # Adds a prefix to the log message to indicate the middleware depth for demonstration purposes.
        call_depth_str = (("+" * CALL_DEPTH_CONTEXTVAR.get()) + " ") if CALL_DEPTH_CONTEXTVAR.get() > 0 else ""
        super().log("{}{}".format(call_depth_str, msg))
