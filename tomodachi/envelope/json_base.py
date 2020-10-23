import base64
import json
import time
import uuid
import zlib
from typing import Any, Dict, Tuple, Union

PROTOCOL_VERSION = "tomodachi-json-base--1.0.0"


class JsonBase(object):
    @classmethod
    async def build_message(cls, service: Any, topic: str, data: Any, **kwargs: Any) -> str:
        data_encoding = "raw"
        if len(json.dumps(data)) >= 60000:
            data = base64.b64encode(zlib.compress(json.dumps(data).encode("utf-8"))).decode("utf-8")
            data_encoding = "base64_gzip_json"

        message = {
            "service": {"name": getattr(service, "name", None), "uuid": getattr(service, "uuid", None)},
            "metadata": {
                "message_uuid": "{}.{}".format(getattr(service, "uuid", ""), str(uuid.uuid4())),
                "protocol_version": PROTOCOL_VERSION,
                "compatible_protocol_versions": ["json_base-wip"],  # deprecated
                "timestamp": time.time(),
                "topic": topic,
                "data_encoding": data_encoding,
            },
            "data": data,
        }
        return json.dumps(message)

    @classmethod
    async def parse_message(cls, payload: str, **kwargs: Any) -> Union[Dict, Tuple]:
        message = json.loads(payload)

        message_uuid = message.get("metadata", {}).get("message_uuid")
        timestamp = message.get("metadata", {}).get("timestamp")

        if message.get("metadata", {}).get("data_encoding") == "raw":
            data = message.get("data")
        elif message.get("metadata", {}).get("data_encoding") == "base64_gzip_json":
            data = json.loads(zlib.decompress(base64.b64decode(message.get("data").encode("utf-8"))).decode("utf-8"))

        return (
            {
                "service": {
                    "name": message.get("service", {}).get("name"),
                    "uuid": message.get("service", {}).get("uuid"),
                },
                "metadata": {
                    "message_uuid": message.get("metadata", {}).get("message_uuid"),
                    "protocol_version": message.get("metadata", {}).get("protocol_version"),
                    "timestamp": message.get("metadata", {}).get("timestamp"),
                    "topic": message.get("metadata", {}).get("topic"),
                    "data_encoding": message.get("metadata", {}).get("data_encoding"),
                },
                "data": data,
            },
            message_uuid,
            timestamp,
        )
