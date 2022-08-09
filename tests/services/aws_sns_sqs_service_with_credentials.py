import asyncio
import json
import os
import signal
import uuid as uuid_
from typing import Any, Dict, List, Set

import tomodachi
from tomodachi.discovery.aws_sns_registration import AWSSNSRegistration
from tomodachi.envelope.json_base import JsonBase
from tomodachi.transport.aws_sns_sqs import AWSSNSSQSInternalServiceError, aws_sns_sqs, aws_sns_sqs_publish

data_uuid = str(uuid_.uuid4())


@tomodachi.service
class AWSSNSSQSService(tomodachi.Service):
    name = "test_aws_sns_sqs"
    log_level = "INFO"
    discovery = [AWSSNSRegistration]
    message_envelope = JsonBase
    options = {
        "aws": {
            "region_name": os.environ.get("TOMODACHI_TEST_AWS_REGION"),
            "aws_access_key_id": os.environ.get("TOMODACHI_TEST_AWS_ACCESS_KEY_ID"),
            "aws_secret_access_key": os.environ.get("TOMODACHI_TEST_AWS_ACCESS_SECRET"),
        },
        "aws_sns_sqs": {
            "queue_name_prefix": os.environ.get("TOMODACHI_TEST_SQS_QUEUE_PREFIX"),
            "topic_prefix": os.environ.get("TOMODACHI_TEST_SNS_TOPIC_PREFIX"),
        },
    }
    uuid = os.environ.get("TOMODACHI_TEST_SERVICE_UUID") or ""
    closer: asyncio.Future = asyncio.Future()
    test_topic_data_received = False
    test_topic_specified_queue_name_data_received = False
    test_topic_metadata_topic = None
    test_topic_service_uuid = None
    test_message_attribute_currencies: Set = set()
    test_message_attribute_amounts: Set = set()
    test_fifo_failed = False
    test_fifo_messages: List[str] = []
    data_uuid = data_uuid

    def check_closer(self) -> None:
        if (
            self.test_topic_data_received
            and self.test_topic_specified_queue_name_data_received
            and len(self.test_message_attribute_currencies) == 7
            and len(self.test_message_attribute_amounts) == 2
            and len(self.test_fifo_messages) == 3
        ):
            if not self.closer.done():
                self.closer.set_result(None)

    @aws_sns_sqs("test-topic", competing=False)
    async def test(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            self.test_topic_data_received = True
            self.test_topic_metadata_topic = metadata.get("topic")
            self.test_topic_service_uuid = service.get("uuid")

            self.check_closer()

    @aws_sns_sqs("test-fifo-topic", queue_name="test-fifo-queue-{}.fifo".format(data_uuid), fifo=True)
    async def test_fifo(self, data: Any, metadata: Any, service: Any) -> None:
        data_val, data_uuid_match = data.split(".")
        if data_uuid_match == self.data_uuid:
            # Fail the second message once in order to ensure that the third
            # message won't be handled until the second has been processed
            # successfully.
            if data_val == "2" and not self.test_fifo_failed:
                self.test_fifo_failed = True
                raise AWSSNSSQSInternalServiceError("boom")

            self.test_fifo_messages.append(data_val)
            self.check_closer()

    @aws_sns_sqs(
        "test-topic-filtered",
        queue_name="test-queue-filter-currency-{}".format(data_uuid),
        filter_policy={"currency": ["SEK", "EUR", "USD", "GBP", "CNY"]},
    )
    async def test_filter_policy_currency(
        self, data: Any, queue_url: str, receipt_handle: str, message_attributes: Dict
    ) -> None:
        if data == self.data_uuid and queue_url and receipt_handle:
            self.test_message_attribute_currencies.add(json.dumps(message_attributes, sort_keys=True))

            self.check_closer()

    @aws_sns_sqs(
        "test-topic-filtered",
        queue_name="test-queue-filter-amount-{}".format(data_uuid),
        filter_policy={"currency": ["SEK", "EUR", "USD", "GBP", "CNY"], "amount": [{"numeric": [">=", 99.51]}]},
    )
    async def test_filter_policy_amount(
        self, data: Any, queue_url: str, receipt_handle: str, message_attributes: Dict
    ) -> None:
        if data == self.data_uuid and queue_url and receipt_handle:
            self.test_message_attribute_amounts.add(json.dumps(message_attributes, sort_keys=True))

            self.check_closer()

    @aws_sns_sqs("test-topic-unique", queue_name="test-queue-{}".format(data_uuid))
    async def test_specified_queue_name(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            if self.test_topic_specified_queue_name_data_received:
                raise Exception("test_topic_specified_queue_name_data_received already set")
            self.test_topic_specified_queue_name_data_received = True

            self.check_closer()

    @aws_sns_sqs("test-topic-unique", queue_name="test-queue-{}".format(data_uuid))
    async def test_specified_queue_name_again(self, data: Any, metadata: Any, service: Any) -> None:
        if data == self.data_uuid:
            if self.test_topic_specified_queue_name_data_received:
                raise Exception("test_topic_specified_queue_name_data_received already set")
            self.test_topic_specified_queue_name_data_received = True

            self.check_closer()

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
            os.kill(os.getpid(), signal.SIGINT)

        asyncio.ensure_future(_async())

        async def _async_publisher() -> None:
            await publish(self.data_uuid, "test-topic")
            await publish(self.data_uuid, "test-topic-unique")

            await publish(self.data_uuid, "test-topic-filtered")
            for ma in (
                {},
                {"currency": "DKK"},
                {"currency": "sek"},
                {"currency": ["SEK"], "amount": 1338, "value": "1338.00 SEK"},
                {"value": "100 SEK"},
                {"currency": "100 SEK"},
                {"currency": "NOK"},
                {"currency": "USD", "amount": 99.50, "value": "99.50 USD"},
                {"amount": 4000},
                {"currency": "EUR"},
                {"currency": ["BTC", "ETH"]},
                {"currency": ["JPY"]},
                {"currency": ["GBP"]},
                {"currency": "EUR"},
                {"currency": "SEK", "amount": 4711},
                {"currency": "SEK", "amount": 4711},
                {"currency": "SEK", "amount": "9001.00"},
                {"currency": ["CNY", "USD", "JPY"]},
                {"currency": "EUR"},
            ):
                await publish(self.data_uuid, "test-topic-filtered", message_attributes=ma)

            for _ in range(10):
                if self.test_topic_data_received:
                    break
                await publish(self.data_uuid, "test-topic")
                await asyncio.sleep(0.5)

        asyncio.ensure_future(_async_publisher())

        # Send three consecutive messages on a FIFO topic. These messages belong to
        # the same group and should be thus handled sequentially.
        await aws_sns_sqs_publish(self, "1.{}".format(data_uuid), topic="test-fifo-topic", group_id="group-1.{}".format(data_uuid), deduplication_id="1.{}".format(data_uuid))
        await aws_sns_sqs_publish(self, "1.{}".format(data_uuid), topic="test-fifo-topic", group_id="group-1.{}".format(data_uuid), deduplication_id="1.{}".format(data_uuid))
        await aws_sns_sqs_publish(self, "2.{}".format(data_uuid), topic="test-fifo-topic", group_id="group-1.{}".format(data_uuid), deduplication_id="2.{}".format(data_uuid))
        await aws_sns_sqs_publish(self, "3.{}".format(data_uuid), topic="test-fifo-topic", group_id="group-1.{}".format(data_uuid), deduplication_id="3.{}".format(data_uuid))

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
