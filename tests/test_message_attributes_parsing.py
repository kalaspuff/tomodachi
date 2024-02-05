import decimal

from tomodachi.transport.aws_sns_sqs import AWSSNSSQSTransport


def test_message_attributes_to_botocore() -> None:
    message_attributes = {
        "hello-world-attribute": "hello world",
        "service.app.attribute1": 1,
        "service.app.attribute4711": 4711,
        "service.app.attribute_approximation": decimal.Decimal("1338.42"),
        "service.app.binary_attribute": b"00000001 00000011 robo-boogie",
    }

    result = AWSSNSSQSTransport.transform_message_attributes_to_botocore(message_attributes)
    assert result == {
        "hello-world-attribute": {
            "DataType": "String",
            "StringValue": "hello world",
        },
        "service.app.attribute1": {
            "DataType": "Number",
            "StringValue": "1",
        },
        "service.app.attribute4711": {
            "DataType": "Number",
            "StringValue": "4711",
        },
        "service.app.attribute_approximation": {
            "DataType": "Number",
            "StringValue": "1338.42",
        },
        "service.app.binary_attribute": {
            "DataType": "Binary",
            "BinaryValue": b"00000001 00000011 robo-boogie",
        },
    }


def test_message_attributes_to_message_body_metadata() -> None:
    message_attributes = {
        "hello-world-attribute": "hello world",
        "service.app.attribute1": 1,
        "service.app.attribute4711": 4711,
        "service.app.attribute_approximation": decimal.Decimal("1338.42"),
        "service.app.binary_attribute": b"00000001 00000011 robo-boogie",
    }

    result = AWSSNSSQSTransport.transform_message_attributes_to_message_body_metadata(message_attributes)

    assert result == {
        "hello-world-attribute": {
            "Type": "String",
            "Value": "hello world",
        },
        "service.app.attribute1": {
            "Type": "Number",
            "Value": "1",
        },
        "service.app.attribute4711": {
            "Type": "Number",
            "Value": "4711",
        },
        "service.app.attribute_approximation": {
            "Type": "Number",
            "Value": "1338.42",
        },
        "service.app.binary_attribute": {
            "Type": "Binary",
            "Value": "MDAwMDAwMDEgMDAwMDAwMTEgcm9iby1ib29naWU=",
        },
    }


def test_message_attributes_from_sqs_message() -> None:
    message_attributes_sqs = {
        "hello-world-attribute": {
            "DataType": "String",
            "StringValue": "hello world",
        },
        "service.app.attribute1": {
            "DataType": "Number",
            "StringValue": "1",
        },
        "service.app.attribute4711": {
            "DataType": "Number",
            "StringValue": "4711",
        },
        "service.app.attribute_approximation": {
            "DataType": "Number",
            "StringValue": "1338.42",
        },
        "service.app.binary_attribute": {
            "DataType": "Binary",
            "BinaryValue": b"00000001 00000011 robo-boogie",
        },
        "service.app.binary_attribute2": {
            "DataType": "Binary",
            "BinaryValue": "MDAwMDAwMDEgMDAwMDAwMTEgcm9iby1ib29naWU=",
        },
    }

    result = AWSSNSSQSTransport.transform_message_attributes_from_response(message_attributes_sqs)
    assert result == {
        "hello-world-attribute": "hello world",
        "service.app.attribute1": 1,
        "service.app.attribute4711": 4711,
        "service.app.attribute_approximation": 1338.42,
        "service.app.binary_attribute": b"00000001 00000011 robo-boogie",
        "service.app.binary_attribute2": b"00000001 00000011 robo-boogie",
    }


def test_message_attributes_from_sqs_message_in_lambda() -> None:
    message_attributes_sqs = {
        "hello-world-attribute": {
            "dataType": "String",
            "stringValue": "hello world",
        },
        "service.app.attribute1": {
            "dataType": "Number",
            "stringValue": "1",
        },
        "service.app.attribute4711": {
            "dataType": "Number",
            "stringValue": "4711",
        },
        "service.app.attribute_approximation": {
            "dataType": "Number",
            "stringValue": "1338.42",
        },
        "service.app.binary_attribute": {
            "dataType": "Binary",
            "binaryValue": b"00000001 00000011 robo-boogie",
        },
        "service.app.binary_attribute2": {
            "dataType": "Binary",
            "binaryValue": "MDAwMDAwMDEgMDAwMDAwMTEgcm9iby1ib29naWU=",
        },
    }

    result = AWSSNSSQSTransport.transform_message_attributes_from_response(message_attributes_sqs)
    assert result == {
        "hello-world-attribute": "hello world",
        "service.app.attribute1": 1,
        "service.app.attribute4711": 4711,
        "service.app.attribute_approximation": 1338.42,
        "service.app.binary_attribute": b"00000001 00000011 robo-boogie",
        "service.app.binary_attribute2": b"00000001 00000011 robo-boogie",
    }


def test_message_attributes_from_sns_message_body_metadata() -> None:
    message_attributes_sqs = {
        "hello-world-attribute": {
            "Type": "String",
            "Value": "hello world",
        },
        "service.app.attribute1": {
            "Type": "Number",
            "Value": "1",
        },
        "service.app.attribute4711": {
            "Type": "Number",
            "Value": "4711",
        },
        "service.app.attribute_approximation": {
            "Type": "Number",
            "Value": "1338.42",
        },
        "service.app.binary_attribute": {
            "Type": "Binary",
            "Value": "MDAwMDAwMDEgMDAwMDAwMTEgcm9iby1ib29naWU=",
        },
    }

    result = AWSSNSSQSTransport.transform_message_attributes_from_response(message_attributes_sqs)
    assert result == {
        "hello-world-attribute": "hello world",
        "service.app.attribute1": 1,
        "service.app.attribute4711": 4711,
        "service.app.attribute_approximation": 1338.42,
        "service.app.binary_attribute": b"00000001 00000011 robo-boogie",
    }


def test_message_attributes_from_sns_message_body_metadata_in_lambda() -> None:
    message_attributes_sqs = {
        "hello-world-attribute": {
            "type": "String",
            "value": "hello world",
        },
        "service.app.attribute1": {
            "type": "Number",
            "value": "1",
        },
        "service.app.attribute4711": {
            "type": "Number",
            "value": "4711",
        },
        "service.app.attribute_approximation": {
            "type": "Number",
            "value": "1338.42",
        },
        "service.app.binary_attribute": {
            "type": "Binary",
            "value": "MDAwMDAwMDEgMDAwMDAwMTEgcm9iby1ib29naWU=",
        },
    }

    result = AWSSNSSQSTransport.transform_message_attributes_from_response(message_attributes_sqs)
    assert result == {
        "hello-world-attribute": "hello world",
        "service.app.attribute1": 1,
        "service.app.attribute4711": 4711,
        "service.app.attribute_approximation": 1338.42,
        "service.app.binary_attribute": b"00000001 00000011 robo-boogie",
    }
