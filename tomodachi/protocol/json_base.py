import ujson
import uuid
import time
import zlib
import base64
from typing import Any, Dict, Tuple, Union

PROTOCOL_VERSION = 'json_base-wip'
COMPATIBLE_PROTOCOL_VERSIONS = ['json_base-wip']


class JsonBase(object):
    @classmethod
    async def build_message(cls, service: Any, topic: str, data: Any) -> str:
        _uuid = str(uuid.uuid4())

        data_encoding = 'raw'
        if len(ujson.dumps(data)) >= 60000:
            data = base64.b64encode(zlib.compress(ujson.dumps(data).encode('utf-8'))).decode('utf-8')
            data_encoding = 'base64_gzip_json'

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
    async def parse_message(cls, payload: str) -> Union[Dict, Tuple]:
        message = ujson.loads(payload)

        compatible_protocol_versions = message.get('metadata', {}).get('compatible_protocol_versions')
        message_uuid = message.get('metadata', {}).get('message_uuid')
        timestamp = message.get('metadata', {}).get('timestamp')
        if PROTOCOL_VERSION not in compatible_protocol_versions:
            return False, message_uuid, timestamp

        data = message.get('data')
        if message.get('metadata', {}).get('data_encoding') == 'base64_gzip_json':
            data = ujson.loads(zlib.decompress(base64.b64decode(message.get('data').encode('utf-8'))).decode('utf-8'))

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
            'data': data
        }, message_uuid, timestamp
