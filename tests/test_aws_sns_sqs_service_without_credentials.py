from typing import Any

from run_test_service_helper import start_service


def test_start_aws_sns_sqs_service_invalid_credentials(capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/aws_sns_sqs_service_invalid_credentials.py", loop=loop)

    assert services is not None
    assert len(services) == 1
    instance = services.get("test_aws_sns_sqs")
    assert instance is not None

    assert instance.uuid is not None
    instance.stop_service()
    loop.run_until_complete(future)

    out, err = capsys.readouterr()
    assert "The security token included in the request is invalid" in (out + err)
