from typing import Any, Dict, Generator, List, Optional, Set, Tuple, cast

import botocore.exceptions
import pytest

from tomodachi.transport.aws_sns_sqs import (
    DEAD_LETTER_QUEUE_DEFAULT,
    MAX_RECEIVE_COUNT_DEFAULT,
    AWSSNSSQSException,
    AWSSNSSQSTransport,
    connector,
)

REGION = "eu-west-1"
ACCOUNT_ID = "123456789012"


def client_error(code: str, message: str, operation_name: str) -> botocore.exceptions.ClientError:
    return botocore.exceptions.ClientError({"Error": {"Code": code, "Message": message}}, operation_name)


class FakeMeta:
    region_name = REGION


class FakeSTSClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: List[str] = []

    async def get_caller_identity(self) -> Dict:
        self.calls.append("GetCallerIdentity")
        if self.fail:
            raise client_error("AccessDenied", "Not authorized to perform sts:GetCallerIdentity", "GetCallerIdentity")
        return {"Account": ACCOUNT_ID}


class FakeSNSClient:
    meta = FakeMeta()

    def __init__(self, existing_topics: Optional[Set[str]] = None, can_create_topic: bool = True) -> None:
        self.existing_topics: Set[str] = set(existing_topics or ())
        self.can_create_topic = can_create_topic
        self.calls: List[Tuple[str, Dict]] = []

    def calls_to(self, operation_name: str) -> List[Dict]:
        return [kwargs for name, kwargs in self.calls if name == operation_name]

    @staticmethod
    def arn(name: str) -> str:
        return f"arn:aws:sns:{REGION}:{ACCOUNT_ID}:{name}"

    async def get_topic_attributes(self, **kwargs: Any) -> Dict:
        self.calls.append(("GetTopicAttributes", kwargs))
        topic_arn = kwargs["TopicArn"]
        if topic_arn.split(":")[-1] not in self.existing_topics:
            raise client_error("NotFound", "Topic does not exist", "GetTopicAttributes")
        return {"Attributes": {"TopicArn": topic_arn}}

    async def create_topic(self, **kwargs: Any) -> Dict:
        self.calls.append(("CreateTopic", kwargs))
        if not self.can_create_topic:
            raise client_error(
                "AuthorizationError",
                "User is not authorized to perform: SNS:CreateTopic",
                "CreateTopic",
            )
        self.existing_topics.add(kwargs["Name"])
        return {"TopicArn": self.arn(kwargs["Name"])}

    async def set_topic_attributes(self, **kwargs: Any) -> Dict:
        self.calls.append(("SetTopicAttributes", kwargs))
        return {}

    async def subscribe(self, **kwargs: Any) -> Dict:
        self.calls.append(("Subscribe", kwargs))
        return {"SubscriptionArn": f"{kwargs['TopicArn']}:subscription-id"}

    async def publish(self, **kwargs: Any) -> Dict:
        self.calls.append(("Publish", kwargs))
        return {"MessageId": "message-id"}


class FakeSQSClient:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, Dict]] = []

    async def get_queue_url(self, **kwargs: Any) -> Dict:
        self.calls.append(("GetQueueUrl", kwargs))
        return {"QueueUrl": f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT_ID}/{kwargs['QueueName']}"}

    async def get_queue_attributes(self, **kwargs: Any) -> Dict:
        self.calls.append(("GetQueueAttributes", kwargs))
        queue_name = kwargs["QueueUrl"].split("/")[-1]
        return {"Attributes": {"QueueArn": f"arn:aws:sqs:{REGION}:{ACCOUNT_ID}:{queue_name}"}}

    async def set_queue_attributes(self, **kwargs: Any) -> Dict:
        self.calls.append(("SetQueueAttributes", kwargs))
        return {}


@pytest.fixture
def fake_aws() -> Generator:
    stored_clients = dict(connector.clients)
    stored_locks = dict(connector.locks)
    stored_conditions = dict(connector.conditions)
    stored_topics = AWSSNSSQSTransport.topics

    connector.clients.clear()
    connector.locks.clear()
    connector.conditions.clear()
    AWSSNSSQSTransport.topics = {}

    def install(sns: FakeSNSClient, sts: Optional[FakeSTSClient] = None, sqs: Optional[FakeSQSClient] = None) -> None:
        connector.clients["tomodachi.sns"] = cast(Any, sns)
        connector.clients["tomodachi.sts"] = cast(Any, sts or FakeSTSClient())
        if sqs:
            connector.clients["tomodachi.sqs"] = cast(Any, sqs)

    yield install

    connector.clients.clear()
    connector.clients.update(stored_clients)
    connector.locks.clear()
    connector.locks.update(stored_locks)
    connector.conditions.clear()
    connector.conditions.update(stored_conditions)
    AWSSNSSQSTransport.topics = stored_topics


def test_create_topic_uses_existing_topic_without_create_topic(loop: Any, fake_aws: Any) -> None:
    sns = FakeSNSClient(existing_topics={"test-topic"}, can_create_topic=False)
    fake_aws(sns)

    topic_arn = loop.run_until_complete(AWSSNSSQSTransport.create_topic("test-topic", {}))

    assert topic_arn == sns.arn("test-topic")
    assert len(sns.calls_to("GetTopicAttributes")) == 1
    assert sns.calls_to("CreateTopic") == []
    assert sns.calls_to("SetTopicAttributes") == []
    assert cast(Dict, AWSSNSSQSTransport.topics)["test-topic"] == topic_arn

    # cached - no further lookups
    assert loop.run_until_complete(AWSSNSSQSTransport.create_topic("test-topic", {})) == topic_arn
    assert len(sns.calls_to("GetTopicAttributes")) == 1


def test_create_topic_creates_missing_topic(loop: Any, fake_aws: Any) -> None:
    sns = FakeSNSClient()
    fake_aws(sns)
    context = {"options": {"aws_sns_sqs": {"topic_prefix": "prefix-"}}}

    topic_arn = loop.run_until_complete(AWSSNSSQSTransport.create_topic("test-topic", context, fifo=True))

    assert topic_arn == sns.arn("prefix-test-topic.fifo")
    assert sns.calls_to("GetTopicAttributes") == [{"TopicArn": sns.arn("prefix-test-topic.fifo")}]
    assert sns.calls_to("CreateTopic") == [
        {
            "Name": "prefix-test-topic.fifo",
            "Attributes": {"FifoTopic": "true", "ContentBasedDeduplication": "false"},
        }
    ]


def test_create_topic_with_attributes_on_existing_topic_still_updates_attributes(loop: Any, fake_aws: Any) -> None:
    sns = FakeSNSClient(existing_topics={"test-topic"})
    fake_aws(sns)
    context = {"options": {"aws_sns_sqs": {"sns_kms_master_key_id": "alias/test-key"}}}

    topic_arn = loop.run_until_complete(
        AWSSNSSQSTransport.create_topic("test-topic", context, attributes={"DisplayName": "test"})
    )

    assert topic_arn == sns.arn("test-topic")
    assert sns.calls_to("CreateTopic") == [
        {"Name": "test-topic", "Attributes": {"DisplayName": "test", "KmsMasterKeyId": "alias/test-key"}}
    ]


def test_create_topic_with_attributes_on_existing_topic_without_create_permission(loop: Any, fake_aws: Any) -> None:
    sns = FakeSNSClient(existing_topics={"test-topic"}, can_create_topic=False)
    fake_aws(sns)
    context = {"options": {"aws_sns_sqs": {"sns_kms_master_key_id": "alias/test-key"}}}

    topic_arn = loop.run_until_complete(
        AWSSNSSQSTransport.create_topic("test-topic", context, attributes={"DisplayName": "test"})
    )

    assert topic_arn == sns.arn("test-topic")
    assert len(sns.calls_to("CreateTopic")) == 1
    assert sns.calls_to("SetTopicAttributes") == []
    assert cast(Dict, AWSSNSSQSTransport.topics)["test-topic"] == topic_arn


def test_create_topic_without_create_permission_raises_on_missing_topic(loop: Any, fake_aws: Any) -> None:
    sns = FakeSNSClient(can_create_topic=False)
    fake_aws(sns)

    with pytest.raises(AWSSNSSQSException):
        loop.run_until_complete(AWSSNSSQSTransport.create_topic("test-topic", {}))

    assert len(sns.calls_to("CreateTopic")) == 1
    assert "test-topic" not in cast(Dict, AWSSNSSQSTransport.topics)


def test_create_topic_falls_back_to_create_topic_when_lookup_fails(loop: Any, fake_aws: Any) -> None:
    sns = FakeSNSClient(existing_topics={"test-topic"})
    sts = FakeSTSClient(fail=True)
    fake_aws(sns, sts)

    topic_arn = loop.run_until_complete(AWSSNSSQSTransport.create_topic("test-topic", {}))

    assert topic_arn == sns.arn("test-topic")
    assert sts.calls
    assert sns.calls_to("GetTopicAttributes") == []
    assert sns.calls_to("CreateTopic") == [{"Name": "test-topic", "Attributes": {}}]


def test_publish_to_existing_topic_does_not_create_topic(loop: Any, fake_aws: Any) -> None:
    sns = FakeSNSClient(existing_topics={"test-topic"}, can_create_topic=False)
    fake_aws(sns)

    class Service:
        context: Dict = {}

    message_id = loop.run_until_complete(
        AWSSNSSQSTransport.publish(Service(), "data", "test-topic", message_envelope=None)
    )

    assert message_id == "message-id"
    assert sns.calls_to("CreateTopic") == []
    assert len(sns.calls_to("Publish")) == 1
    assert sns.calls_to("Publish")[0]["TopicArn"] == sns.arn("test-topic")


def test_setup_queue_subscribes_to_existing_topic_without_create_topic(
    loop: Any, fake_aws: Any, monkeypatch: Any
) -> None:
    sns = FakeSNSClient(existing_topics={"test-topic"}, can_create_topic=False)
    sqs = FakeSQSClient()
    fake_aws(sns, sqs=sqs)

    consumed: List[str] = []

    async def consume_queue(*args: Any, queue_url: str, **kwargs: Any) -> None:
        consumed.append(queue_url)

    monkeypatch.setattr(AWSSNSSQSTransport, "consume_queue", consume_queue)

    async def handler() -> None:
        pass

    class Service:
        uuid = "service-uuid"

    context: Dict = {
        "_aws_sns_sqs_subscribers": [
            (
                "test-topic",
                True,
                "test-queue",
                handler,
                handler,
                None,
                None,
                DEAD_LETTER_QUEUE_DEFAULT,
                MAX_RECEIVE_COUNT_DEFAULT,
                False,
                None,
            )
        ]
    }

    async def _run() -> None:
        subscribe = await AWSSNSSQSTransport.subscribe(Service(), context)
        assert subscribe
        await subscribe()

    loop.run_until_complete(_run())

    assert sns.calls_to("CreateTopic") == []
    assert sns.calls_to("Subscribe") == [
        {
            "TopicArn": sns.arn("test-topic"),
            "Protocol": "sqs",
            "Endpoint": f"arn:aws:sqs:{REGION}:{ACCOUNT_ID}:test-queue",
        }
    ]
    assert len(consumed) == 1
