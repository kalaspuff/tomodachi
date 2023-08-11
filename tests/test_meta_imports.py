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
