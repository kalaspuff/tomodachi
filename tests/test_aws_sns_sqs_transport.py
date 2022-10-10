import os
import signal
from typing import Any

import pytest

from run_test_service_helper import start_service
from tomodachi.transport.aws_sns_sqs import AWSSNSSQSException, AWSSNSSQSTransport


def test_get_standard_topic_name(monkeypatch: Any) -> None:
    topic_name = AWSSNSSQSTransport.get_topic_name("test-topic", {}, fifo=False)
    assert topic_name == "test-topic"

    topic_name = AWSSNSSQSTransport.get_topic_name(
        "test-topic", {"options": {"aws_sns_sqs": {"topic_prefix": "prefix-"}}}, fifo=False
    )
    assert topic_name == "prefix-test-topic"


def test_get_fifo_topic_name(monkeypatch: Any) -> None:
    topic_name = AWSSNSSQSTransport.get_topic_name("test-topic", {}, fifo=True)
    assert topic_name == "test-topic.fifo"

    topic_name = AWSSNSSQSTransport.get_topic_name(
        "test-topic", {"options": {"aws_sns_sqs": {"topic_prefix": "prefix-"}}}, fifo=True
    )
    assert topic_name == "prefix-test-topic.fifo"


def test_encode_standard_topic(monkeypatch: Any) -> None:
    topic_name = AWSSNSSQSTransport.encode_topic("test-topic")
    assert topic_name == "test-topic"

    topic_name = AWSSNSSQSTransport.encode_topic("test.topic")
    assert topic_name == "test___2e_topic"


def test_encode_fifo_topic(monkeypatch: Any) -> None:
    topic_name = AWSSNSSQSTransport.encode_topic("test-topic.fifo")
    assert topic_name == "test-topic.fifo"

    topic_name = AWSSNSSQSTransport.encode_topic("test.topic.fifo")
    assert topic_name == "test___2e_topic.fifo"


def test_decode_standard_topic(monkeypatch: Any) -> None:
    topic_name = AWSSNSSQSTransport.decode_topic("test-topic")
    assert topic_name == "test-topic"

    topic_name = AWSSNSSQSTransport.decode_topic("test___2e_topic")
    assert topic_name == "test.topic"


def test_decode_fifo_topic(monkeypatch: Any) -> None:
    topic_name = AWSSNSSQSTransport.decode_topic("test-topic.fifo")
    assert topic_name == "test-topic.fifo"

    topic_name = AWSSNSSQSTransport.decode_topic("test___2e_topic.fifo")
    assert topic_name == "test.topic.fifo"


def test_get_standard_queue_name(monkeypatch: Any) -> None:
    _uuid = "5d0b530f-5c44-4981-b01f-342801bd48f5"
    queue_name = AWSSNSSQSTransport.get_queue_name("test-topic", "func", _uuid, False, {}, fifo=False)
    assert queue_name == "45b56d76d14276da54c0ef65ca5c604ab9d0301bbebf4d6ad11e91dd496c2975"

    queue_name = AWSSNSSQSTransport.get_queue_name("test-topic", "func2", _uuid, False, {}, fifo=False)
    assert queue_name != "45b56d76d14276da54c0ef65ca5c604ab9d0301bbebf4d6ad11e91dd496c2975"

    queue_name = AWSSNSSQSTransport.get_queue_name(
        "test-topic",
        "func",
        _uuid,
        False,
        {"options": {"aws_sns_sqs": {"queue_name_prefix": "prefix-"}}},
        fifo=False,
    )
    assert queue_name == "prefix-45b56d76d14276da54c0ef65ca5c604ab9d0301bbebf4d6ad11e91dd496c2975"

    queue_name = AWSSNSSQSTransport.get_queue_name("test-topic", "func", _uuid, True, {}, fifo=False)
    assert queue_name == "c6fb053c1b70aabd10bfefd087166b532b7c79ed12d24f2d43a9999c724797fd"

    queue_name = AWSSNSSQSTransport.get_queue_name("test-topic", "func2", _uuid, True, {}, fifo=False)
    assert queue_name == "c6fb053c1b70aabd10bfefd087166b532b7c79ed12d24f2d43a9999c724797fd"

    queue_name = AWSSNSSQSTransport.get_queue_name(
        "test-topic",
        "func",
        _uuid,
        True,
        {"options": {"aws_sns_sqs": {"queue_name_prefix": "prefix-"}}},
        fifo=False,
    )
    assert queue_name == "prefix-c6fb053c1b70aabd10bfefd087166b532b7c79ed12d24f2d43a9999c724797fd"


def test_get_fifo_queue_name(monkeypatch: Any) -> None:
    _uuid = "5d0b530f-5c44-4981-b01f-342801bd48f5"
    queue_name = AWSSNSSQSTransport.get_queue_name("test-topic.fifo", "func", _uuid, False, {}, fifo=True)
    assert queue_name == "ad38a445b6b80e599dfff888caf6806f300ad3f565a8906b38176003b913f893.fifo"

    queue_name = AWSSNSSQSTransport.get_queue_name("test-topic.fifo", "func2", _uuid, False, {}, fifo=True)
    assert queue_name != "4276da54c0ef65ca5c604ab9d0301bbebf4d6ad11e91dd496c2975.fifo"

    queue_name = AWSSNSSQSTransport.get_queue_name(
        "test-topic.fifo",
        "func",
        _uuid,
        False,
        {"options": {"aws_sns_sqs": {"queue_name_prefix": "prefix-"}}},
        fifo=True,
    )
    assert queue_name == "prefix-ad38a445b6b80e599dfff888caf6806f300ad3f565a8906b38176003b913f893.fifo"

    queue_name = AWSSNSSQSTransport.get_queue_name("test-topic.fifo", "func", _uuid, True, {}, fifo=True)
    assert queue_name == "1183df5a6172224209951ac7251ea9bdab277dbe988cde334fd30f84144cafeb.fifo"

    queue_name = AWSSNSSQSTransport.get_queue_name("test-topic.fifo", "func2", _uuid, True, {}, fifo=True)
    assert queue_name == "1183df5a6172224209951ac7251ea9bdab277dbe988cde334fd30f84144cafeb.fifo"

    queue_name = AWSSNSSQSTransport.get_queue_name(
        "test-topic.fifo",
        "func",
        _uuid,
        True,
        {"options": {"aws_sns_sqs": {"queue_name_prefix": "prefix-"}}},
        fifo=True,
    )
    assert queue_name == "prefix-1183df5a6172224209951ac7251ea9bdab277dbe988cde334fd30f84144cafeb.fifo"


def test_publish_invalid_credentials(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/dummy_service.py", monkeypatch, loop=loop)

    instance = services.get("test_dummy")

    with pytest.raises(AWSSNSSQSException):
        loop.run_until_complete(AWSSNSSQSTransport.publish(instance, "data", "test-topic", wait=True))

    async def _async_kill():
        os.kill(os.getpid(), signal.SIGINT)

    loop.create_task(_async_kill())
    loop.run_until_complete(future)

    if not future.done():
        future.set_result(None)

    out, err = capsys.readouterr()
    assert "The security token included in the request is invalid" in err
    assert out == ""


def test_validate_topic() -> None:
    with pytest.raises(Exception) as e:
        AWSSNSSQSTransport.validate_topic_name("#")
    assert "#" in str(e)
    with pytest.raises(Exception) as e:
        AWSSNSSQSTransport.validate_queue_name(
            "XS8zQl3sdze1kjyZmxDrRW1PN2o2OZAJts6SgUYCy5NsaGpb6MyWUOwHzVPpzMnmBSI12Buuu43Upz2evMysWbA8T7fTo02TvNTZtLc4MJok4N7IUkK9EDtBzXcdEbRLGLPGuRJtEiaiWqfbDPDMWapkB2jKwFLgxsYGark4lpZ1gxly6wnhhBTXDTGwoW39NYnadTUA8v8QyPqPhFDLRfh9CNBmNtcnWq6nsSZ0QTQb2aMETPZ7rIQ5DC2X16pif"
        )
    assert "XS8zQl3sd" in str(e)
    assert AWSSNSSQSTransport.validate_topic_name("abcd") is None


def test_validate_queue_name() -> None:
    with pytest.raises(Exception) as e:
        AWSSNSSQSTransport.validate_queue_name("#")
    assert "#" in str(e)
    with pytest.raises(Exception) as e:
        AWSSNSSQSTransport.validate_queue_name(
            "vKbED4a66BaGI0cGF0iP8HNF202Sk2XuFnEuJI59GX5VfgEzLaMIU10cVscG7E8vvLIU0MhL7kmsPEy81"
        )
    assert "vKbED4a66BaGI0cGF0iP8HNF202Sk2XuFnEuJI59GX5VfgEzLaMIU10cVscG7E8vvLIU0MhL7kmsPEy81" in str(e)
    assert AWSSNSSQSTransport.validate_queue_name("abcd") is None
