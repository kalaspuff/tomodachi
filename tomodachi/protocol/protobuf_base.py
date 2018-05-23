import logging
import uuid
import time
import base64
from typing import Any, Dict, Tuple, Union

from tomodachi.proto_build.protobuf.sns_sqs_message_pb2 import SNSSQSMessage

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
        message = SNSSQSMessage()
        message.service.name = getattr(service, 'name', None)
        message.service.uuid = getattr(service, 'uuid', None)
        message.metadata.message_uuid = '{}.{}'.format(getattr(service, 'uuid', ''), str(uuid.uuid4()))
        message.metadata.protocol_version = PROTOCOL_VERSION
        message.metadata.compatible_protocol_versions.extend(COMPATIBLE_PROTOCOL_VERSIONS)
        message.metadata.timestamp = time.time()
        message.metadata.topic = topic
        message.metadata.data_encoding = 'base64'
        message.data = base64.b64encode(data.SerializeToString()).decode('ascii')
        return base64.b64encode(message.SerializeToString()).decode('ascii')

    @classmethod
    async def parse_message(cls, payload: str, proto_class: Any, validator: Any = None) -> Union[Dict, Tuple]:
        message = SNSSQSMessage()
        message.ParseFromString(base64.b64decode(payload))

        message_uuid = message.metadata.message_uuid
        timestamp = message.metadata.timestamp

        if PROTOCOL_VERSION not in message.metadata.compatible_protocol_versions:
            return False, message_uuid, timestamp

        obj = proto_class()
        obj.ParseFromString(base64.b64decode(message.data))

        if validator is not None:
            try:
                if hasattr(validator, '__func__'):
                    # for static functions
                    validator.__func__(obj)
                else:
                    # for non-static functions
                    validator(obj)
            except Exception as e:
                logging.getLogger('protocol.protobuf_base').warning(e.__str__())
                raise e

        return {
            'service': {
                'name': message.service.name,
                'uuid': message.service.uuid
            },
            'metadata': {
                'message_uuid': message.metadata.message_uuid,
                'protocol_version': message.metadata.protocol_version,
                'compatible_protocol_versions': message.metadata.compatible_protocol_versions,
                'timestamp': message.metadata.timestamp,
                'topic': message.metadata.topic,
                'data_encoding': message.metadata.data_encoding
            },
            'data': obj
        }, message_uuid, timestamp
