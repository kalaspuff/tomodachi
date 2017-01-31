import ujson
import uuid

PROTOCOL_VERSION = 1
COMPATIBLE_PROTOCOL_VERSIONS = (1,)


class JsonBase(object):
    @classmethod
    async def build_message(cls, service, data):
        _uuid = str(uuid.uuid1())
        message = {
            'service': {
                'name': service.name,
                'uuid': service.uuid
            },
            'metadata': {
                'message_uuid': _uuid,
                'protocol_version': PROTOCOL_VERSION
            },
            'data': data
        }
        return ujson.dumps(message)

    @classmethod
    async def parse_message(cls, payload):
        message = ujson.loads(payload)

        protocol_version = message.get('metadata', {}).get('protocol_version')
        if protocol_version != PROTOCOL_VERSION and protocol_version not in COMPATIBLE_PROTOCOL_VERSIONS:
            return False

        return {
            'service': {
                'name': message.get('service', {}).get('name'),
                'uuid': message.get('service', {}).get('uuid')
            },
            'metadata': {
                'message_uuid': message.get('metadata', {}).get('message_uuid'),
                'protocol_version': message.get('metadata', {}).get('protocol_version')
            },
            'data': message.get('data')
        }
