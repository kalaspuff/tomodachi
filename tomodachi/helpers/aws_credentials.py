from typing import (
    Any,
    Dict,
    ItemsView,
    Iterator,
    KeysView,
    Literal,
    Optional,
    TypedDict,
    TypeVar,
    Union,
    ValuesView,
    cast,
    overload,
)

from botocore.credentials import Credentials as BotocoreCredentials
from botocore.credentials import ReadOnlyCredentials as BotocoreReadOnlyCredentials

T = TypeVar("T")


class CredentialsDict(TypedDict, total=False):
    region_name: Optional[str]
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    aws_session_token: Optional[str]
    endpoint_url: Optional[str]


class CredentialsTypeProtocol:
    region_name: Optional[str]
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    aws_session_token: Optional[str]
    endpoint_url: Optional[str]


CredentialsTypeKeys = Literal[
    "region_name", "aws_access_key_id", "aws_secret_access_key", "aws_session_token", "endpoint_url"
]


class Credentials:
    region_name: Optional[str]
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    aws_session_token: Optional[str]
    endpoint_url: Optional[str]

    def keys(
        self,
    ) -> KeysView[CredentialsTypeKeys]:
        result = {}
        for key in ("region_name", "aws_access_key_id", "aws_secret_access_key", "aws_session_token", "endpoint_url"):
            result[key] = ...
        return cast(Dict[CredentialsTypeKeys, Optional[str]], result).keys()

    def dict(self) -> CredentialsDict:
        result: CredentialsDict = {}
        for key in self.keys():
            result[key] = getattr(self, key, None)
        return result

    def values(
        self,
    ) -> ValuesView[Optional[str]]:
        return cast(Dict[CredentialsTypeKeys, Optional[str]], self.dict()).values()

    def items(
        self,
    ) -> ItemsView[CredentialsTypeKeys, Optional[str]]:
        return cast(Dict[CredentialsTypeKeys, Optional[str]], self.items()).items()

    @overload
    def __init__(
        self,
        __map: Union[CredentialsDict, CredentialsTypeProtocol, BotocoreCredentials, BotocoreReadOnlyCredentials],
        /,
        *,
        region_name: Optional[str] = ...,
        aws_access_key_id: Optional[str] = ...,
        aws_secret_access_key: Optional[str] = ...,
        aws_session_token: Optional[str] = ...,
        endpoint_url: Optional[str] = ...,
    ) -> None: ...

    @overload
    def __init__(
        self,
        /,
        *,
        region_name: Optional[str] = ...,
        aws_access_key_id: Optional[str] = ...,
        aws_secret_access_key: Optional[str] = ...,
        aws_session_token: Optional[str] = ...,
        endpoint_url: Optional[str] = ...,
    ) -> None: ...

    def __init__(
        self,
        __map: Optional[
            Union[CredentialsDict, CredentialsTypeProtocol, BotocoreCredentials, BotocoreReadOnlyCredentials]
        ] = None,
        /,
        **kwargs: Any,
    ) -> None:
        if __map is not None:
            if isinstance(__map, BotocoreCredentials):
                __map = __map.get_frozen_credentials()
            if isinstance(__map, BotocoreReadOnlyCredentials):
                __map = {
                    "aws_access_key_id": __map.access_key,
                    "aws_secret_access_key": __map.secret_key,
                    "aws_session_token": __map.token,
                }
            if not isinstance(__map, dict):
                try:
                    __map = cast(CredentialsDict, dict(__map))  # type: ignore[call-overload]
                except TypeError:
                    __map = cast(CredentialsDict, dict(__map.__dict__))
            if __map and isinstance(__map, dict):
                for key, value in __map.items():
                    setattr(self, key, value)
        for key in kwargs:
            if key not in (
                "region_name",
                "aws_access_key_id",
                "aws_secret_access_key",
                "aws_session_token",
                "endpoint_url",
            ):
                raise TypeError(f"__init__() got an unexpected keyword argument '{key}'")
            setattr(self, key, kwargs[key])

    def __iter__(
        self,
    ) -> Iterator[CredentialsTypeKeys]:
        return cast(Iterator[CredentialsTypeKeys], iter(cast(CredentialsDict, self.dict())))

    def __getitem__(
        self,
        key: CredentialsTypeKeys,
    ) -> Optional[str]:
        return self.get(key)

    def __contains__(
        self,
        key: str,
    ) -> bool:
        return key in self.keys()

    @overload
    def get(
        self,
        key: CredentialsTypeKeys,
        default: Any = ...,
    ) -> Optional[str]: ...

    @overload
    def get(
        self,
        key: str,
        default: T,
    ) -> T: ...

    def get(
        self,
        key: str,
        default: Any = ...,
    ) -> Any:
        if default is Ellipsis:
            return getattr(self, key)
        return getattr(self, key, default)


CredentialsMapping = Union[
    Credentials, CredentialsDict, CredentialsTypeProtocol, BotocoreCredentials, BotocoreReadOnlyCredentials
]
