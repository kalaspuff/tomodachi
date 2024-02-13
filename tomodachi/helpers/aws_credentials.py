from typing import (
    Any,
    Dict,
    ItemsView,
    Iterator,
    KeysView,
    Literal,
    Optional,
    Set,
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
    __unset: Set[str]

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
            value = getattr(self, key, None)
            if value is Ellipsis:
                value = None
            result[key] = value
        return result

    def values(
        self,
    ) -> ValuesView[Optional[str]]:
        return cast(Dict[CredentialsTypeKeys, Optional[str]], self.dict()).values()

    def items(
        self,
    ) -> ItemsView[CredentialsTypeKeys, Optional[str]]:
        return cast(Dict[CredentialsTypeKeys, Optional[str]], self.dict()).items()

    @overload
    def __init__(
        self,
        __map: Union[
            CredentialsDict,
            CredentialsTypeProtocol,
            "Credentials",
            BotocoreCredentials,
            BotocoreReadOnlyCredentials,
            Dict[
                Literal[
                    "region_name", "aws_access_key_id", "aws_secret_access_key", "aws_session_token", "endpoint_url"
                ],
                Optional[str],
            ],
        ],
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
            Union[
                CredentialsDict,
                CredentialsTypeProtocol,
                "Credentials",
                BotocoreCredentials,
                BotocoreReadOnlyCredentials,
                Dict[
                    Literal[
                        "region_name", "aws_access_key_id", "aws_secret_access_key", "aws_session_token", "endpoint_url"
                    ],
                    Optional[str],
                ],
            ]
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
                    __map = cast(CredentialsDict, dict(__map))  # type: ignore[arg-type]
                except TypeError:
                    __map = cast(CredentialsDict, dict(__map.__dict__))
            if __map and isinstance(__map, dict):
                for key, value in __map.items():
                    setattr(self, key, value)
        for key in kwargs:
            if key not in self.keys():
                raise TypeError(f"__init__() got an unexpected keyword argument '{key}'")
            setattr(self, key, kwargs[key])

        self.__unset = set()
        for key in self.keys():
            try:
                self.get(key, default=Ellipsis)
            except AttributeError:
                setattr(self, key, None)
                self.__unset.add(key)

    def __iter__(
        self,
    ) -> Iterator[CredentialsTypeKeys]:
        return cast(Iterator[CredentialsTypeKeys], iter(cast(CredentialsDict, self.dict())))

    def __getitem__(
        self,
        key: CredentialsTypeKeys,
    ) -> Optional[str]:
        return self.get(key, default=Ellipsis) if key not in self.__unset else None

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
        default: Any = None,
    ) -> Any:
        if default is Ellipsis:
            return getattr(self, key) if key not in self.__unset else None
        return getattr(self, key, default) if key not in self.__unset else default


CredentialsMapping = Union[
    Credentials, CredentialsDict, CredentialsTypeProtocol, BotocoreCredentials, BotocoreReadOnlyCredentials
]
