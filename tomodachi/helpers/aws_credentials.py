from typing import (
    Any,
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
        for key in CredentialsDict.__optional_keys__ | CredentialsDict.__required_keys__:
            result[key] = ...
        return cast(dict[CredentialsTypeKeys, Optional[str]], result).keys()

    def dict(self) -> CredentialsDict:
        result: CredentialsDict = {}
        for key in self.keys():
            result[key] = getattr(self, key, None)
        return result

    def values(
        self,
    ) -> ValuesView[Optional[str]]:
        return cast(dict[CredentialsTypeKeys, Optional[str]], self.dict()).values()

    def items(
        self,
    ) -> ItemsView[CredentialsTypeKeys, Optional[str]]:
        return cast(dict[CredentialsTypeKeys, Optional[str]], self.items()).items()

    @overload
    def __init__(
        self,
        __map: Union[CredentialsDict, CredentialsTypeProtocol],
        /,
        *,
        region_name: Optional[str] = ...,
        aws_access_key_id: Optional[str] = ...,
        aws_secret_access_key: Optional[str] = ...,
        aws_session_token: Optional[str] = ...,
        endpoint_url: Optional[str] = ...,
    ) -> None:
        ...

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
    ) -> None:
        ...

    def __init__(
        self,
        __map: Optional[Union[CredentialsDict, CredentialsTypeProtocol]] = None,
        /,
        # region_name: Union[Optional[str], ellipsis] = Ellipsis,
        # aws_access_key_id: Union[Optional[str], ellipsis] = Ellipsis,
        # aws_secret_access_key: Union[Optional[str], ellipsis] = Ellipsis,
        # aws_session_token: Union[Optional[str], ellipsis] = Ellipsis,
        # endpoint_url: Union[Optional[int], ellipsis] = Ellipsis,
        **kwargs: Any,
    ) -> None:
        # if __map is not Ellipsis and not isinstance(__map, ellipsis):
        if __map is not None:
            if not isinstance(__map, dict):
                try:
                    __map = cast(CredentialsDict, dict(__map))
                except TypeError:
                    __map = cast(CredentialsDict, dict(__map.__dict__))
            if __map and isinstance(__map, dict):
                for key, value in __map.items():
                    setattr(self, key, value)
        # if region_name is not Ellipsis and not isinstance(region_name, ellipsis):
        #     self.region_name = region_name
        # if aws_access_key_id is not Ellipsis and not isinstance(aws_access_key_id, ellipsis):
        #     self.aws_access_key_id = aws_access_key_id
        # if aws_secret_access_key is not Ellipsis and not isinstance(aws_secret_access_key, ellipsis):
        #     self.aws_secret_access_key = aws_secret_access_key
        # if aws_session_token is not Ellipsis and not isinstance(aws_session_token, ellipsis):
        #     self.aws_session_token = aws_session_token
        # if endpoint_url is not Ellipsis and not isinstance(endpoint_url, ellipsis):
        #     self.endpoint_url = endpoint_url
        for key in kwargs:
            if key not in CredentialsDict.__optional_keys__ | CredentialsDict.__required_keys__:
                raise TypeError(f"__init__() got an unexpected keyword argument '{key}'")
            setattr(self, key, kwargs[key])

    def __iter__(
        self,
    ) -> Iterator[CredentialsTypeKeys]:
        return cast(Iterator[CredentialsTypeKeys], iter(cast(CredentialsDict, self.dict())))
        # return iter(cast(dict[CredentialsTypeKeys, Optional[str]], self.dict()))

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
    ) -> Optional[str]:
        ...

    @overload
    def get(
        self,
        key: str,
        default: T,
    ) -> T:
        ...

    def get(
        self,
        key: str,
        default: Any = ...,
    ) -> Any:
        if default is Ellipsis:
            return getattr(self, key)
        return getattr(self, key, default)


CredentialsMapping = Union[Credentials, CredentialsDict, CredentialsTypeProtocol]
