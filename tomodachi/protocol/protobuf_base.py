import ujson
import uuid
import time
import base64
from typing import Any, Dict, Tuple, Union

PROTOCOL_VERSION = 'protobuf_base-wip'
COMPATIBLE_PROTOCOL_VERSIONS = ['protobuf_base-wip']


class ProtobufBase(object):

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        if 'proto_class' not in kwargs:
            raise Exception('No proto_class defined')
        if kwargs.get('proto_class', None).__class__.__name__ != 'GeneratedProtocolMessageType':
            raise Exception('proto_class is not a GeneratedProtocolMessageType')

    @classmethod
    async def build_message(cls, service: Any, topic: str, data: Any) -> str:
        _uuid = str(uuid.uuid4())

        data_encoding = 'base64'

        data = base64.b64encode(data.SerializeToString())

        message = {
            'service': {
                'name': getattr(service, 'name', None),
                'uuid': getattr(service, 'uuid', None)
            },
            'metadata': {
                'message_uuid': '{}.{}'.format(getattr(service, 'uuid', ''), _uuid),
                'protocol_version': PROTOCOL_VERSION,
                'compatible_protocol_versions': COMPATIBLE_PROTOCOL_VERSIONS,
                'timestamp': time.time(),
                'topic': topic,
                'data_encoding': data_encoding
            },
            'data': data
        }
        return ujson.dumps(message)

    @classmethod
    async def parse_message(cls, payload: str, proto_class: Any) -> Union[Dict, Tuple]:
        message = ujson.loads(payload)

        compatible_protocol_versions = message.get('metadata', {}).get('compatible_protocol_versions')
        message_uuid = message.get('metadata', {}).get('message_uuid')
        timestamp = message.get('metadata', {}).get('timestamp')
        if PROTOCOL_VERSION not in compatible_protocol_versions:
            return False, message_uuid, timestamp

        data = base64.b64decode(message.get('data'))

        obj = proto_class()
        obj.ParseFromString(data)

        return {
            'service': {
                'name': message.get('service', {}).get('name'),
                'uuid': message.get('service', {}).get('uuid')
            },
            'metadata': {
                'message_uuid': message.get('metadata', {}).get('message_uuid'),
                'protocol_version': message.get('metadata', {}).get('protocol_version'),
                'compatible_protocol_versions': message.get('metadata', {}).get('compatible_protocol_versions'),
                'timestamp': message.get('metadata', {}).get('timestamp'),
                'topic': message.get('metadata', {}).get('topic'),
                'data_encoding': message.get('metadata', {}).get('data_encoding')
            },
            'data': obj
        }, message_uuid, timestamp
