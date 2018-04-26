from typing import Any
from tomodachi.protocol.json_base import JsonBase
try:
    from tomodachi.protocol.protobuf_base import ProtobufBase
except ModuleNotFoundError:
    class ProtobufBase(object):
        @classmethod
        def validate(cls, **kwargs: Any) -> None:
            raise Exception('google.protobuf package not installed')

__all__ = ['JsonBase', 'ProtobufBase']
