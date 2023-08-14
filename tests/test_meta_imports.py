from types import FunctionType, MethodType, ModuleType

import pytest


def test_getattr_import() -> None:
    import tomodachi

    assert tomodachi.transport.aws_sns_sqs


def test_meta_import() -> None:
    import tomodachi

    assert tomodachi.transport.awssnssqs


def test_meta_func_import() -> None:
    import tomodachi
    from tomodachi.transport.aws_sns_sqs import publish

    assert tomodachi.transport.awssnssqs.publish is publish
    assert id(tomodachi.transport.awssnssqs.publish) == id(publish)


def test_import_equality() -> None:
    import tomodachi

    assert tomodachi.transport.aws_sns_sqs is tomodachi.transport.aws_sns_sqs
    assert tomodachi.transport.awssnssqs is tomodachi.transport.awssnssqs
    assert tomodachi.transport.aws_sns_sqs is tomodachi.transport.awssnssqs
    assert id(tomodachi.transport.aws_sns_sqs) == id(tomodachi.transport.awssnssqs)

    aws_sns_sqs_ = tomodachi.transport.aws_sns_sqs

    import tomodachi.transport

    assert tomodachi.transport.aws_sns_sqs is aws_sns_sqs_

    from tomodachi.transport import aws_sns_sqs

    assert aws_sns_sqs is aws_sns_sqs_

    from tomodachi.transport import awssnssqs

    assert awssnssqs is aws_sns_sqs_


def test_lazy_imports_equality_envelope() -> None:
    import tomodachi

    assert tomodachi.envelope.JsonBase
    id_0 = id(tomodachi.envelope.JsonBase)

    assert tomodachi.envelope.json_base.JsonBase
    id_1 = id(tomodachi.envelope.json_base.JsonBase)

    assert tomodachi.envelope.ProtobufBase
    assert tomodachi.envelope.protobuf_base.ProtobufBase

    from tomodachi.envelope import JsonBase

    id_2 = id(JsonBase)

    from tomodachi.envelope import ProtobufBase

    assert ProtobufBase

    from tomodachi.envelope.json_base import JsonBase as JsonBase_

    id_3 = id(JsonBase_)

    assert JsonBase is JsonBase_

    from tomodachi.envelope.protobuf_base import ProtobufBase as ProtobufBase_

    assert ProtobufBase is ProtobufBase_

    from tomodachi.protocol import JsonBase as JsonBase_ProtocolImport

    assert JsonBase is JsonBase_ProtocolImport
    id_4 = id(JsonBase_ProtocolImport)

    from tomodachi.protocol import ProtobufBase as ProtobufBase_ProtocolImport

    assert ProtobufBase is ProtobufBase_ProtocolImport

    import tomodachi.protocol

    assert JsonBase is tomodachi.protocol.JsonBase

    id_5 = id(tomodachi.protocol.JsonBase)

    assert id_0 == id_1 == id_2 == id_3 == id_4 == id_5
    assert id_0 != id(ProtobufBase)


def test_lazy_imports_invalid_attribute() -> None:
    import tomodachi.protocol

    with pytest.raises(AttributeError):
        tomodachi.protocol.UnknownAttribute0

    with pytest.raises(ImportError):
        from tomodachi.protocol import AnotherUnknownAttribute0  # noqa

    with pytest.raises(AttributeError):
        tomodachi.envelope.UnknownAttribute1

    with pytest.raises(ImportError):
        from tomodachi.envelope import AnotherUnknownAttribute1  # noqa

    with pytest.raises(AttributeError):
        tomodachi.transport.awssnssqs.UnknownAttribute2

    with pytest.raises(ImportError):
        from tomodachi.transport.awssnssqs import AnotherUnknownAttribute2  # noqa

    with pytest.raises(AttributeError):
        tomodachi.discovery.UnknownAttribute3

    with pytest.raises(ImportError):
        from tomodachi.discovery import AnotherUnknownAttribute3  # noqa


@pytest.mark.parametrize(
    "path, comparison_path, type_",
    [
        ("tomodachi.envelope.JsonBase", "tomodachi.envelope.json_base.JsonBase", type),
        ("tomodachi.envelope.ProtobufBase", "tomodachi.envelope.protobuf_base.ProtobufBase", type),
        ("tomodachi.discovery.AWSSNSRegistration", "tomodachi.discovery.aws_sns_registration.AWSSNSRegistration", type),
        ("tomodachi.discovery.awssns", "tomodachi.discovery.aws_sns_registration.AWSSNSRegistration", type),
        ("tomodachi.discovery.aws_sns", "tomodachi.discovery.aws_sns_registration.AWSSNSRegistration", type),
        ("tomodachi.discovery.DummyRegistry", "tomodachi.discovery.dummy_registry.DummyRegistry", type),
        ("tomodachi.discovery.dummy", "tomodachi.discovery.dummy_registry.DummyRegistry", type),
        ("tomodachi.discovery.example", "tomodachi.discovery.dummy_registry.DummyRegistry", type),
        ("tomodachi.discovery.aws_sns_registration", "tomodachi.discovery.aws_sns_registration", ModuleType),
        ("tomodachi.discovery.dummy_registry", "tomodachi.discovery.dummy_registry", ModuleType),
        ("tomodachi.aws_sns_sqs", "tomodachi.transport.aws_sns_sqs.aws_sns_sqs", FunctionType),
        ("tomodachi.awssnssqs", "tomodachi.transport.aws_sns_sqs.awssnssqs", FunctionType),
        ("tomodachi.aws_sns_sqs", "tomodachi.transport.awssnssqs.aws_sns_sqs", FunctionType),
        ("tomodachi.awssnssqs", "tomodachi.transport.awssnssqs.awssnssqs", FunctionType),
        ("tomodachi.awssnssqs_publish", "tomodachi.transport.awssnssqs.awssnssqs_publish", MethodType),
        ("tomodachi.awssnssqs_publish", "tomodachi.transport.aws_sns_sqs.awssnssqs_publish", MethodType),
        ("tomodachi.get_forwarded_remote_ip", "tomodachi.transport.http.get_forwarded_remote_ip", FunctionType),
        ("tomodachi.get_logger", "tomodachi.logging.get_logger", FunctionType),
        ("tomodachi.Logger", "tomodachi.logging.Logger", type),
        ("tomodachi.Options", "tomodachi.options.Options", type),
    ],
)
def test_lazy_imports(path, comparison_path, type_) -> None:
    import sys

    def getattr_from_path(path: str):
        parts = path.split(".")

        base_module = parts[0]
        if base_module in sys.modules:
            obj = sys.modules[base_module]
        obj = __import__(base_module)
        if base_module not in sys.modules:
            sys.modules[base_module] = obj

        for part in parts[1:]:
            obj = getattr(obj, part)

        return obj

    path_obj = getattr_from_path(path)
    path_obj_2 = getattr_from_path(path)
    assert path_obj is path_obj_2
    assert id(path_obj) == id(path_obj_2)

    comparison_path_obj = getattr_from_path(comparison_path)
    assert path_obj is comparison_path_obj
    assert id(path_obj) == id(comparison_path_obj)

    assert isinstance(path_obj, type_)
