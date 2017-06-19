import asyncio
import os
import signal
import pytest
from typing import Any
from tomodachi.transport.aws_sns_sqs import AWSSNSSQSTransport, AWSSNSSQSException
from run_test_service_helper import start_service


def test_topic_name(monkeypatch: Any) -> None:
    topic_name = AWSSNSSQSTransport.get_topic_name('test-topic', {})
    assert topic_name == 'test-topic'

    topic_name = AWSSNSSQSTransport.get_topic_name('test-topic', {'options': {'aws_sns_sqs': {'topic_prefix': 'prefix-'}}})
    assert topic_name == 'prefix-test-topic'


def test_encode_topic(monkeypatch: Any) -> None:
    topic_name = AWSSNSSQSTransport.encode_topic('test-topic')
    assert topic_name == 'test-topic'

    topic_name = AWSSNSSQSTransport.encode_topic('test.topic')
    assert topic_name == 'test___2e_topic'


def test_decode_topic(monkeypatch: Any) -> None:
    topic_name = AWSSNSSQSTransport.decode_topic('test-topic')
    assert topic_name == 'test-topic'

    topic_name = AWSSNSSQSTransport.decode_topic('test___2e_topic')
    assert topic_name == 'test.topic'


def test_queue_name(monkeypatch: Any) -> None:
    _uuid = '5d0b530f-5c44-4981-b01f-342801bd48f5'
    queue_name = AWSSNSSQSTransport.get_queue_name('test-topic', 'func', _uuid, False, {})
    assert queue_name == '45b56d76d14276da54c0ef65ca5c604ab9d0301bbebf4d6ad11e91dd496c2975'

    queue_name = AWSSNSSQSTransport.get_queue_name('test-topic', 'func2', _uuid, False, {})
    assert queue_name != '45b56d76d14276da54c0ef65ca5c604ab9d0301bbebf4d6ad11e91dd496c2975'

    queue_name = AWSSNSSQSTransport.get_queue_name('test-topic', 'func', _uuid, False, {'options': {'aws_sns_sqs': {'queue_name_prefix': 'prefix-'}}})
    assert queue_name == 'prefix-45b56d76d14276da54c0ef65ca5c604ab9d0301bbebf4d6ad11e91dd496c2975'

    queue_name = AWSSNSSQSTransport.get_queue_name('test-topic', 'func', _uuid, True, {})
    assert queue_name == 'c6fb053c1b70aabd10bfefd087166b532b7c79ed12d24f2d43a9999c724797fd'

    queue_name = AWSSNSSQSTransport.get_queue_name('test-topic', 'func2', _uuid, True, {})
    assert queue_name == 'c6fb053c1b70aabd10bfefd087166b532b7c79ed12d24f2d43a9999c724797fd'

    queue_name = AWSSNSSQSTransport.get_queue_name('test-topic', 'func', _uuid, True, {'options': {'aws_sns_sqs': {'queue_name_prefix': 'prefix-'}}})
    assert queue_name == 'prefix-c6fb053c1b70aabd10bfefd087166b532b7c79ed12d24f2d43a9999c724797fd'


def test_publish_invalid_credentials(monkeypatch: Any, capsys: Any) -> None:
    services, future = start_service('tests/services/dummy_service.py', monkeypatch)

    instance = services.get('test_dummy')

    loop = asyncio.get_event_loop()

    with pytest.raises(AWSSNSSQSException):
        loop.run_until_complete(AWSSNSSQSTransport.publish(instance, 'data', 'test-topic', wait=True))

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert 'The security token included in the request is invalid' in err
    assert out == ''
