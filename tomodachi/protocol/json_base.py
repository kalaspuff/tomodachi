import ujson
import uuid
import time
from typing import Any, Dict, Tuple, Union

PROTOCOL_VERSION = 'json_base-wip'
COMPATIBLE_PROTOCOL_VERSIONS = ['json_base-wip']


class JsonBase(object):
    @classmethod
    async def build_message(cls, service: Any, topic: str, data: Any) -> str:
        _uuid = str(uuid.uuid4())
        message = {
            'service': {
                'name': service.name,
                'uuid': service.uuid
            },
            'metadata': {
                'message_uuid': '{}.{}'.format(service.uuid, _uuid),
                'protocol_version': PROTOCOL_VERSION,
                'compatible_protocol_versions': COMPATIBLE_PROTOCOL_VERSIONS,
                'timestamp': time.time(),
                'topic': topic
            },
            'data': data
        }
        return ujson.dumps(message)

    @classmethod
    async def parse_message(cls, payload: str) -> Union[Dict, Tuple]:
        message = ujson.loads(payload)

        compatible_protocol_versions = message.get('metadata', {}).get('compatible_protocol_versions')
        message_uuid = message.get('metadata', {}).get('message_uuid')
        timestamp = message.get('metadata', {}).get('timestamp')
        if PROTOCOL_VERSION not in compatible_protocol_versions:
            return False, message_uuid, timestamp

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
                'topic': message.get('metadata', {}).get('topic')
            },
            'data': message.get('data')
        }, message_uuid, timestamp
