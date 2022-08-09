from typing import ClassVar as _ClassVar
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message

DESCRIPTOR: _descriptor.FileDescriptor

class Metadata(_message.Message):
    __slots__ = ["data_encoding", "message_uuid", "protocol_version", "timestamp", "topic"]
    DATA_ENCODING_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_UUID_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_VERSION_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    data_encoding: str
    message_uuid: str
    protocol_version: str
    timestamp: float
    topic: str
    def __init__(self, message_uuid: _Optional[str] = ..., protocol_version: _Optional[str] = ..., timestamp: _Optional[float] = ..., topic: _Optional[str] = ..., data_encoding: _Optional[str] = ...) -> None: ...

class SNSSQSMessage(_message.Message):
    __slots__ = ["data", "metadata", "service"]
    DATA_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    metadata: Metadata
    service: Service
    def __init__(self, service: _Optional[_Union[Service, _Mapping]] = ..., metadata: _Optional[_Union[Metadata, _Mapping]] = ..., data: _Optional[bytes] = ...) -> None: ...

class Service(_message.Message):
    __slots__ = ["name", "uuid"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    UUID_FIELD_NUMBER: _ClassVar[int]
    name: str
    uuid: str
    def __init__(self, name: _Optional[str] = ..., uuid: _Optional[str] = ...) -> None: ...
