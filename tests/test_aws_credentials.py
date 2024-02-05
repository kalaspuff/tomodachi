from dataclasses import dataclass
from typing import Optional, cast

import pytest
from botocore.credentials import Credentials as BotocoreCredentials

from tomodachi.helpers.aws_credentials import Credentials, CredentialsDict, CredentialsTypeProtocol

TEST_AWS_ACCESS_KEY_ID = "AKIAXXXXXXXXXXXXXXXX"  # example, not real access key
TEST_AWS_SECRET_ACCESS_KEY = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # example, not real secret key
TEST_AWS_SESSION_TOKEN = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # example, not real session token


def test_aws_credentials_object() -> None:
    credentials = Credentials(
        region_name="eu-west-1",
        aws_access_key_id=TEST_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=TEST_AWS_SECRET_ACCESS_KEY,
    )
    assert credentials.region_name == "eu-west-1"
    assert credentials.aws_access_key_id == TEST_AWS_ACCESS_KEY_ID
    assert credentials.aws_secret_access_key == TEST_AWS_SECRET_ACCESS_KEY

    assert credentials.dict() == {
        "region_name": "eu-west-1",
        "aws_access_key_id": TEST_AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": TEST_AWS_SECRET_ACCESS_KEY,
        "aws_session_token": None,
        "endpoint_url": None,
    }

    assert list(credentials.keys()) == [
        "region_name",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "endpoint_url",
    ]

    assert list(credentials.values()) == [
        "eu-west-1",
        TEST_AWS_ACCESS_KEY_ID,
        TEST_AWS_SECRET_ACCESS_KEY,
        None,
        None,
    ]

    assert list(credentials.items()) == [
        ("region_name", "eu-west-1"),
        ("aws_access_key_id", TEST_AWS_ACCESS_KEY_ID),
        ("aws_secret_access_key", TEST_AWS_SECRET_ACCESS_KEY),
        ("aws_session_token", None),
        ("endpoint_url", None),
    ]

    assert "region_name" in credentials
    assert "aws_session_token" in credentials
    assert "not_a_valid_key" not in credentials

    assert credentials["region_name"] == "eu-west-1"
    assert credentials.get("region_name") == "eu-west-1"

    assert credentials.endpoint_url is None
    assert credentials["endpoint_url"] is None
    assert credentials.get("endpoint_url") is None
    assert credentials.get("endpoint_url", "a default value") == "a default value"
    assert credentials.get("not_a_valid_key") is None  # type: ignore[call-overload]
    assert credentials.get("not_a_valid_key", "a default value") == "a default value"

    keys = []
    values = []

    for key in credentials:
        keys.append(key)
        values.append(credentials[key])
        assert credentials[key] == getattr(credentials, key)
        assert credentials[key] == credentials.get(key)

    assert len(keys) == len(values)
    assert len(keys) == 5
    assert set(keys) == credentials.keys()
    assert values == list(credentials.values())

    assert credentials.dict() == credentials.dict()
    assert credentials.dict() == dict(credentials)
    assert credentials.dict() == Credentials(credentials).dict()
    assert credentials.dict() == Credentials(credentials.dict()).dict()

    _credentials: CredentialsDict = cast(CredentialsDict, credentials)
    assert credentials.dict() == Credentials(**_credentials).dict()


def test_aws_credentials_object_invalid_accessor() -> None:
    credentials = Credentials(
        region_name="eu-west-1",
        aws_access_key_id=TEST_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=TEST_AWS_SECRET_ACCESS_KEY,
    )

    with pytest.raises(AttributeError):
        _ = credentials["not_a_valid_key"]  # type: ignore[index]


def test_aws_credentials_object_invalid_attribute() -> None:
    credentials = Credentials(
        region_name="eu-west-1",
        aws_access_key_id=TEST_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=TEST_AWS_SECRET_ACCESS_KEY,
    )

    with pytest.raises(AttributeError):
        _ = credentials.not_a_valid_key  # type: ignore[attr-defined]


def test_aws_credentials_object_invalid_argument() -> None:
    with pytest.raises(TypeError):
        Credentials(
            region_name="eu-west-1",
            aws_access_key_id=TEST_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=TEST_AWS_SECRET_ACCESS_KEY,
            not_a_valid_argument="invalid",  # type: ignore[call-overload]
        )


def test_dict_credentials() -> None:
    credentials = Credentials({"aws_session_token": TEST_AWS_SESSION_TOKEN})
    assert credentials.aws_session_token == TEST_AWS_SESSION_TOKEN
    assert credentials.endpoint_url is None

    assert credentials.dict() == {
        "region_name": None,
        "aws_access_key_id": None,
        "aws_secret_access_key": None,
        "aws_session_token": TEST_AWS_SESSION_TOKEN,
        "endpoint_url": None,
    }


def test_compatible_credentials() -> None:
    @dataclass()
    class CompatibleCredentials(CredentialsTypeProtocol):
        region_name: str = "eu-west-1"
        aws_access_key_id: Optional[str] = None
        aws_secret_access_key: Optional[str] = None
        endpoint_url: Optional[str] = None

    credentials = Credentials(
        CompatibleCredentials(
            aws_access_key_id=TEST_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=TEST_AWS_SECRET_ACCESS_KEY,
            endpoint_url="http://localhost:4567",
        )
    )

    assert credentials.region_name == "eu-west-1"
    assert credentials.aws_access_key_id == TEST_AWS_ACCESS_KEY_ID
    assert credentials.aws_secret_access_key == TEST_AWS_SECRET_ACCESS_KEY
    assert credentials.endpoint_url == "http://localhost:4567"

    assert credentials.dict() == {
        "region_name": "eu-west-1",
        "aws_access_key_id": TEST_AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": TEST_AWS_SECRET_ACCESS_KEY,
        "aws_session_token": None,
        "endpoint_url": "http://localhost:4567",
    }


def test_botocore_credentials() -> None:
    credentials = Credentials(BotocoreCredentials(TEST_AWS_ACCESS_KEY_ID, TEST_AWS_SECRET_ACCESS_KEY))
    assert credentials.aws_access_key_id == TEST_AWS_ACCESS_KEY_ID
    assert credentials.aws_secret_access_key == TEST_AWS_SECRET_ACCESS_KEY

    assert credentials.dict() == {
        "region_name": None,
        "aws_access_key_id": TEST_AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": TEST_AWS_SECRET_ACCESS_KEY,
        "aws_session_token": None,
        "endpoint_url": None,
    }


def test_botocore_credentials_with_extra_input() -> None:
    credentials = Credentials(
        BotocoreCredentials(TEST_AWS_ACCESS_KEY_ID, TEST_AWS_SECRET_ACCESS_KEY, TEST_AWS_SESSION_TOKEN),
        region_name="eu-west-1",
        endpoint_url="http://localhost:4567",
    )
    assert credentials.region_name == "eu-west-1"
    assert credentials.aws_access_key_id == TEST_AWS_ACCESS_KEY_ID
    assert credentials.aws_secret_access_key == TEST_AWS_SECRET_ACCESS_KEY
    assert credentials.aws_session_token == TEST_AWS_SESSION_TOKEN
    assert credentials.endpoint_url == "http://localhost:4567"

    assert credentials.dict() == {
        "region_name": "eu-west-1",
        "aws_access_key_id": TEST_AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": TEST_AWS_SECRET_ACCESS_KEY,
        "aws_session_token": TEST_AWS_SESSION_TOKEN,
        "endpoint_url": "http://localhost:4567",
    }
