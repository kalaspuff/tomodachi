from typing import Any

from tomodachi.envelope.json_base import JsonBase

try:
    from tomodachi.envelope.protobuf_base import ProtobufBase  # type: ignore
except Exception:  # pragma: no cover

    class ProtobufBase(object):  # type: ignore
        @classmethod
        def validate(cls, **kwargs: Any) -> None:
            raise Exception("google.protobuf package not installed")


__all__ = ["JsonBase", "ProtobufBase"]
