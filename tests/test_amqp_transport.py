import asyncio
import os
import signal
import pytest
from tomodachi.transport.amqp import AmqpTransport, AmqpException
from run_test_service_helper import start_service


def test_routing_key(monkeypatch):
    routing_key = AmqpTransport.get_routing_key('test.topic', {})
    assert routing_key == 'test.topic'

    routing_key = AmqpTransport.get_routing_key('test.topic', {'options': {'amqp': {'routing_key_prefix': 'prefix-'}}})
    assert routing_key == 'prefix-test.topic'


def test_encode_routing_key(monkeypatch):
    routing_key = AmqpTransport.encode_routing_key('test-topic')
    assert routing_key == 'test-topic'

    routing_key = AmqpTransport.encode_routing_key('test.topic')
    assert routing_key == 'test.topic'


def test_decode_routing_key(monkeypatch):
    routing_key = AmqpTransport.decode_routing_key('test-topic')
    assert routing_key == 'test-topic'

    routing_key = AmqpTransport.decode_routing_key('test.topic')
    assert routing_key == 'test.topic'


def test_queue_name(monkeypatch):
    _uuid = '5d0b530f-5c44-4981-b01f-342801bd48f5'
    queue_name = AmqpTransport.get_queue_name('test.topic', 'func', _uuid, False, {})
    assert queue_name == 'b444917b9b922e8c29235737c7775c823e092c2374d1bfde071d42c637e3b4fd'

    queue_name = AmqpTransport.get_queue_name('test.topic', 'func2', _uuid, False, {})
    assert queue_name != 'b444917b9b922e8c29235737c7775c823e092c2374d1bfde071d42c637e3b4fd'

    queue_name = AmqpTransport.get_queue_name('test.topic', 'func', _uuid, False, {'options': {'amqp': {'queue_name_prefix': 'prefix-'}}})
    assert queue_name == 'prefix-b444917b9b922e8c29235737c7775c823e092c2374d1bfde071d42c637e3b4fd'

    queue_name = AmqpTransport.get_queue_name('test.topic', 'func', _uuid, True, {})
    assert queue_name == '540e8e5bc604e4ea618f7e0517a04f030ad1dcbff2e121e9466ddd1c811450bf'

    queue_name = AmqpTransport.get_queue_name('test.topic', 'func2', _uuid, True, {})
    assert queue_name == '540e8e5bc604e4ea618f7e0517a04f030ad1dcbff2e121e9466ddd1c811450bf'

    queue_name = AmqpTransport.get_queue_name('test.topic', 'func', _uuid, True, {'options': {'amqp': {'queue_name_prefix': 'prefix-'}}})
    assert queue_name == 'prefix-540e8e5bc604e4ea618f7e0517a04f030ad1dcbff2e121e9466ddd1c811450bf'


def test_publish_invalid_credentials(monkeypatch, capsys):
    services, future = start_service('tests/services/dummy_service.py', monkeypatch)

    instance = services.get('test_dummy')

    loop = asyncio.get_event_loop()

    with pytest.raises(AmqpException):
        loop.run_until_complete(AmqpTransport.publish(instance, 'data', 'test.topic', wait=True))

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert 'Unable to connect [amqp] to 127.0.0.1:54321' in err
    assert out == ''
