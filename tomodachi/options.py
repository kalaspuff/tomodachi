from __future__ import annotations

import platform
from typing import Any, Dict, ItemsView, KeysView, List, Mapping, Optional, Tuple, Union

DEFAULT = object()


class OptionsMapping:
    _hierarchy: Tuple[str, ...] = ()
    _legacy_fallback: Dict[str, Union[str, Tuple[str, ...]]] = {}
    _parent: Optional[OptionsMapping] = None

    def get(self, item: str, default: Any = DEFAULT) -> Any:
        if "." in item:
            item, attr = item.split(".", 1)
            try:
                return getattr(self, item).get(attr)
            except AttributeError:
                if default is not DEFAULT:
                    return default
                raise

        if default is not DEFAULT:
            try:
                return getattr(self, item, default)
            except AttributeError:
                return default

        return getattr(self, item)

    def __getitem__(self, item: str) -> Any:
        return self.get(item)

    def __setattr__(self, item: str, value: Any) -> None:
        if not hasattr(self, item) and item not in self.keys():
            exc = AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")
            exc.name = item
            exc.obj = self
            raise exc

        super().__setattr__(item, value)

    def __setitem__(self, item: str, value: Any) -> None:
        if "." in item:
            item, attr = item.split(".", 1)
            getattr(self, item)[attr] = value
            return

        if not hasattr(self, item):
            exc = AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")
            exc.name = item
            exc.obj = self
            raise exc

        setattr(self, item, value)

    def keys(self) -> KeysView:
        return self.__annotations__.keys()

    def items(self) -> ItemsView:
        return self.asdict().items()

    def asdict(self, *, prefix: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key in self.keys():
            if key.startswith("_"):
                continue
            _prefix = f"{prefix}{str(key)}"
            value = getattr(self, key)
            if not isinstance(value, OptionsMapping):
                result[_prefix] = value
                continue
            values = value.asdict(prefix=f"{_prefix}.")
            for full_key, v in values.items():
                result[full_key] = v
        return result

    def __repr__(self) -> str:
        result: str = ""
        base_indent: int = 0 if not self._hierarchy else 2
        indent: int = 2
        prefix: str = ".".join(self._hierarchy)
        if prefix:
            cls_name = str(type(self)).split("'")[-2].split("tomodachi.options.", 1)[-1]
            result = f"∴ {self._hierarchy[-1]} <class \"{cls_name}\" -- prefix: \"{prefix}\">:"
            prefix += "."
        prev: Tuple[str, ...] = self._hierarchy
        for full_key, value in self.asdict(prefix=prefix).items():
            key_prefix, key = full_key.rsplit(".", 1)
            curr: Tuple[str, ...] = tuple(key_prefix.split("."))
            if curr != prev:
                for i, subkey in enumerate(curr):
                    if i >= len(prev) or subkey != prev[i]:
                        indent = base_indent + ((i - len(self._hierarchy) + 1) * 2)
                        if result:
                            result += f"" if i else "\n"
                        cls_name = str(type(self.get('.'.join(curr[len(self._hierarchy):i + 1])))).split("'")[-2].split("tomodachi.options.", 1)[-1]
                        lead_char = "·" if i != 0 else "∴"
                        result += f"\n{' ' * (indent - 2)}{lead_char} {subkey} <class: \"{cls_name}\" -- prefix: \"{'.'.join(curr)}\">:"
                        if i >= len(prev):
                            break
                prev = curr
            if type(value) is str:
                value=f"\"{value}\""
            result += f"\n{' ' * indent}| {key} = {value}"
        return result.lstrip("\n") + "\n"

    def _load_keyword_options(self, **kwargs: Any) -> None:
        if not self._parent:
            self._parent = kwargs.pop("_parent", None)

        flattened_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, (dict, OptionsMapping)):
                added_attributes = []
                error_attributes = []
                for subkey, subvalue in value.items():
                    key_str_tuple = self._legacy_fallback.get(f"{key}.{subkey}", f"{key}.{subkey}")
                    key_tuple = tuple((key_str_tuple, )) if not isinstance(key_str_tuple, tuple) else key_str_tuple
                    for full_key in key_tuple:
                        if full_key.startswith("."):
                            if not self._parent:
                                raise AttributeError(f"Cannot set attribute '{full_key}' on '{type(self).__name__}' object – deprecated attribute has moved and OptionsMapping has no parent")
                            self._parent[full_key[1:]] = subvalue
                            continue
                        try:
                            self.get(full_key)
                            flattened_kwargs[full_key] = subvalue
                            added_attributes.append(subkey)
                        except AttributeError:
                            if isinstance(value, OptionsMapping):
                                raise
                            if isinstance(value, dict):
                                error_attributes.append(subkey)
                if error_attributes and added_attributes:
                    raise AttributeError(f"Invalid attribute(s) in dict: {', '.join(error_attributes)}")
                elif error_attributes and not added_attributes:
                    key_str_tuple = self._legacy_fallback.get(key, key)
                    key_tuple = tuple((key_str_tuple, )) if not isinstance(key_str_tuple, tuple) else key_str_tuple
                    for full_key in key_tuple:
                        if full_key.startswith("."):
                            if not self._parent:
                                raise AttributeError(f"Cannot set attribute '{full_key}' on '{type(self).__name__}' object – deprecated attribute has moved and OptionsMapping has no parent")
                            self._parent[full_key[1:]] = value
                            continue
                        flattened_kwargs[full_key] = value
            else:
                key_str_tuple = self._legacy_fallback.get(key, key)
                key_tuple = tuple((key_str_tuple, )) if not isinstance(key_str_tuple, tuple) else key_str_tuple
                for full_key in key_tuple:
                    if full_key.startswith("."):
                        if not self._parent:
                            raise AttributeError(f"Cannot set attribute '{full_key}' on '{type(self).__name__}' object – deprecated attribute has moved and OptionsMapping has no parent")
                        self._parent[full_key[1:]] = value
                        continue
                    flattened_kwargs[full_key] = value

        for key, value in flattened_kwargs.items():
            self.__setitem__(key, value)


class Options(OptionsMapping):
    class HTTP(OptionsMapping):
        port: int
        host: Optional[str]
        reuse_port: bool
        content_type: str
        client_max_size: Union[str, int]
        termination_grace_period_seconds: int
        access_log: Union[bool, str]
        real_ip_from: Union[str, List[str]]
        real_ip_header: str
        keepalive_timeout: int
        keepalive_expiry: int
        max_keepalive_time: Optional[int]
        max_keepalive_requests: Optional[int]
        server_header: str

        _hierarchy: Tuple[str, ...] = ("http",)
        __slots__: Tuple[str, ...] = ("port", "host", "reuse_port", "content_type", "client_max_size", "termination_grace_period_seconds", "access_log", "real_ip_from", "real_ip_header", "keepalive_timeout", "keepalive_expiry", "max_keepalive_time", "max_keepalive_requests", "server_header")

        def __init__(
            self,
            *,
            port: int = 9700,
            host: Optional[str] = "0.0.0.0",
            reuse_port: bool = (True if platform.system() == "Linux" else False),
            content_type: str = "text/plain; charset=utf-8",
            client_max_size: Union[str, int] = (1024**2) * 100,
            termination_grace_period_seconds: int = 30,
            access_log: Union[bool, str] = True,
            real_ip_from: Optional[Union[str, List[str]]] = None,
            real_ip_header: str = "X-Forwarded-For",
            keepalive_timeout: int = 0,
            keepalive_expiry: int = 0,
            max_keepalive_time: Optional[int] = None,
            max_keepalive_requests: Optional[int] = None,
            server_header: str = "tomodachi",
            **kwargs: Any,
        ):
            self.port = port
            self.host = host
            self.reuse_port = reuse_port
            self.content_type = content_type
            self.client_max_size = client_max_size
            self.termination_grace_period_seconds = termination_grace_period_seconds
            self.access_log = access_log
            self.real_ip_from = real_ip_from if real_ip_from is not None and real_ip_from != "" else []
            self.real_ip_header = real_ip_header
            self.keepalive_timeout = keepalive_timeout
            self.keepalive_expiry = keepalive_expiry
            self.max_keepalive_time = max_keepalive_time
            self.max_keepalive_requests = max_keepalive_requests
            self.server_header = server_header

            self._load_keyword_options(**kwargs)

    class AWSSNSSQS(OptionsMapping):
        region_name: Optional[str]
        aws_access_key_id: Optional[str]
        aws_secret_access_key: Optional[str]
        topic_prefix: str
        queue_name_prefix: str
        sns_kms_master_key_id: Optional[str]
        sqs_kms_master_key_id: Optional[str]
        sqs_kms_data_key_reuse_period: Optional[str]
        queue_policy: Optional[str]
        wildcard_queue_policy: Optional[str]

        _hierarchy: Tuple[str, ...] = ("aws_sns_sqs",)
        __slots__: Tuple[str, ...] = ("region_name", "aws_access_key_id", "aws_secret_access_key", "topic_prefix", "queue_name_prefix", "sns_kms_master_key_id", "sqs_kms_master_key_id", "sqs_kms_data_key_reuse_period", "queue_policy", "wildcard_queue_policy")

        def __init__(
            self,
            *,
            region_name: Optional[str] = None,
            aws_access_key_id: Optional[str] = None,
            aws_secret_access_key: Optional[str] = None,
            topic_prefix: str = "",
            queue_name_prefix: str = "",
            sns_kms_master_key_id: Optional[str] = None,
            sqs_kms_master_key_id: Optional[str] = None,
            sqs_kms_data_key_reuse_period: Optional[str] = None,
            queue_policy: Optional[str] = None,
            wildcard_queue_policy: Optional[str] = None,
            **kwargs: Any,
        ):
            self.region_name = region_name
            self.aws_access_key_id = aws_access_key_id
            self.aws_secret_access_key = aws_secret_access_key
            self.topic_prefix = topic_prefix
            self.queue_name_prefix = queue_name_prefix
            self.sns_kms_master_key_id = sns_kms_master_key_id
            self.sqs_kms_master_key_id = sqs_kms_master_key_id
            self.sqs_kms_data_key_reuse_period = sqs_kms_data_key_reuse_period
            self.queue_policy = queue_policy
            self.wildcard_queue_policy = wildcard_queue_policy

            self._load_keyword_options(**kwargs)

        _legacy_fallback: Dict[str, Union[str, Tuple[str, ...]]] = {
            "aws_region_name": "region_name",
            "secret_access_key": "aws_secret_access_key",
            "access_key_id": "aws_access_key_id",

            "endpoint_url": (".aws_endpoint_urls.sns", ".aws_endpoint_urls.sqs"),
            "aws_endpoint_url": (".aws_endpoint_urls.sns", ".aws_endpoint_urls.sqs"),
            "endpoint_urls.sns": ".aws_endpoint_urls.sns",
            "endpoint_urls.sqs": ".aws_endpoint_urls.sqs",
            "aws_sns_endpoint_url": ".aws_endpoint_urls.sns",
            "aws_sqs_endpoint_url": ".aws_endpoint_urls.sqs",
            "sns_endpoint_url": ".aws_endpoint_urls.sns",
            "sqs_endpoint_url": ".aws_endpoint_urls.sqs",

            "aws_kms_master_key_id": ("sns_kms_master_key_id", "sqs_kms_master_key_id"),
            "kms_master_key_id": ("sns_kms_master_key_id", "sqs_kms_master_key_id"),
            "aws_sns_kms_master_key_id": "sns_kms_master_key_id",
            "aws_sqs_kms_master_key_id": "sqs_kms_master_key_id",
            "aws_sqs_kms_data_key_reuse_period": "sqs_kms_data_key_reuse_period",
            "aws_kms_data_key_reuse_period": "sqs_kms_data_key_reuse_period",
            "kms_data_key_reuse_period": "sqs_kms_data_key_reuse_period",
        }

    class AWSEndpointURLs(OptionsMapping):
        sns: Optional[str]
        sqs: Optional[str]

        _hierarchy: Tuple[str, ...] = ("aws_endpoint_urls",)
        __slots__: Tuple[str, ...] = ("sns", "sqs")

        def __init__(
            self,
            *,
            sns: Optional[str] = None,
            sqs: Optional[str] = None,
            **kwargs: Any,
        ):
            self.sns = sns
            self.sqs = sqs

            self._load_keyword_options(**kwargs)

    class AMQP(OptionsMapping):
        host: Optional[str]
        port: int
        login: str
        password: str
        exchange_name: str
        routing_key_prefix: str
        queue_name_prefix: str
        virtualhost: str
        ssl: bool
        heartbeat: int
        queue_ttl: int

        _hierarchy: Tuple[str, ...] = ("amqp",)
        __slots__: Tuple[str, ...] = ("host", "port", "login", "password", "exchange_name", "routing_key_prefix", "queue_name_prefix", "virtualhost", "ssl", "heartbeat", "queue_ttl")

        def __init__(
            self,
            *,
            host: str = "127.0.0.1",
            port: int = 5672,
            login: str = "guest",
            password: str = "guest",
            exchange_name: str = "amq_topic",
            routing_key_prefix: str = "",
            queue_name_prefix: str = "",
            virtualhost: str = "/",
            ssl: bool = False,
            heartbeat: int = 60,
            queue_ttl: int = 86400,
            **kwargs: Any,
        ):
            self.host = host
            self.port = port
            self.login = login
            self.password = password
            self.exchange_name = exchange_name
            self.routing_key_prefix = routing_key_prefix
            self.queue_name_prefix = queue_name_prefix
            self.virtualhost = virtualhost
            self.ssl = ssl
            self.heartbeat = heartbeat
            self.queue_ttl = queue_ttl

            self._load_keyword_options(**kwargs)

    class Watcher(OptionsMapping):
        ignored_dirs: List[str]
        watched_file_endings: List[str]

        _hierarchy: Tuple[str, ...] = ("watcher",)
        __slots__: Tuple[str, ...] = ("ignored_dirs", "watched_file_endings")

        def __init__(
            self,
            *,
            ignored_dirs: Optional[List[str]] = None,
            watched_file_endings: Optional[List[str]] = None,
            **kwargs: Any,
        ):
            self.ignored_dirs = ignored_dirs if ignored_dirs is not None else []
            self.watched_file_endings = watched_file_endings if watched_file_endings is not None else []

            self._load_keyword_options(**kwargs)

    http: HTTP
    aws_sns_sqs: AWSSNSSQS
    aws_endpoint_urls: AWSEndpointURLs
    amqp: AMQP
    watcher: Watcher

    _HTTP_DEFAULT: HTTP = HTTP()
    _AWSSNSSQS_DEFAULT: AWSSNSSQS = AWSSNSSQS()
    _AWSEndpointURLs_DEFAULT: AWSEndpointURLs = AWSEndpointURLs()
    _AMQP_DEFAULT: AMQP = AMQP()
    _Watcher_DEFAULT: Watcher = Watcher()

    __slots__: Tuple[str, ...] = ("http", "aws_sns_sqs", "aws_endpoint_urls", "amqp", "watcher")

    def __init__(
        self,
        *,
        http: Union[Mapping[str, Any], HTTP] = _HTTP_DEFAULT,
        aws_sns_sqs: Union[Mapping[str, Any], AWSSNSSQS] = _AWSSNSSQS_DEFAULT,
        aws_endpoint_urls: Union[Mapping[str, Any], AWSEndpointURLs] = _AWSEndpointURLs_DEFAULT,
        amqp: Union[Mapping[str, Any], AMQP] = _AMQP_DEFAULT,
        watcher: Union[Mapping[str, Any], Watcher] = _Watcher_DEFAULT,
        **kwargs: Any,
    ):
        if isinstance(http, self.HTTP) and http is not self._HTTP_DEFAULT:
            self.http = http
            self.http._parent = self
        else:
            self.http = self.HTTP(_parent=self)

        if isinstance(aws_endpoint_urls, self.AWSEndpointURLs) and aws_endpoint_urls is not self._AWSEndpointURLs_DEFAULT:
            self.aws_endpoint_urls = aws_endpoint_urls
            self.aws_endpoint_urls._parent = self
        else:
            self.aws_endpoint_urls = self.AWSEndpointURLs(_parent=self)

        if isinstance(aws_sns_sqs, self.AWSSNSSQS) and aws_sns_sqs is not self._AWSSNSSQS_DEFAULT:
            self.aws_sns_sqs = aws_sns_sqs
            self.aws_sns_sqs._parent = self
        else:
            self.aws_sns_sqs = self.AWSSNSSQS(_parent=self)

        if isinstance(amqp, self.AMQP) and amqp is not self._AMQP_DEFAULT:
            self.amqp = amqp
            self.amqp._parent = self
        else:
            self.amqp = self.AMQP(_parent=self)

        if isinstance(watcher, self.Watcher) and watcher is not self._Watcher_DEFAULT:
            self.watcher = watcher
            self.watcher._parent = self
        else:
            self.watcher = self.Watcher(_parent=self)

        if not isinstance(http, self.HTTP):
            self.http._load_keyword_options(**http)

        if not isinstance(aws_endpoint_urls, self.AWSEndpointURLs):
            self.aws_endpoint_urls._load_keyword_options(**aws_endpoint_urls)

        if not isinstance(aws_sns_sqs, self.AWSSNSSQS):
            self.aws_sns_sqs._load_keyword_options(**aws_sns_sqs)

        if not isinstance(amqp, self.AMQP):
            self.amqp._load_keyword_options(**amqp)

        if not isinstance(watcher, self.Watcher):
            self.watcher._load_keyword_options(**watcher)

        self._load_keyword_options(**kwargs)

    # Options of options
    Http = HTTP
    Amqp = AMQP
    AwsSnsSqs = AWSSNSSQS
    AwsEndpointUrls = AWSEndpointURLs
    AWSEndpointUrls = AWSEndpointURLs

    _legacy_fallback: Dict[str, Union[str, Tuple[str, ...]]] = {
        "aws.region_name": "aws_sns_sqs.region_name",
        "aws.aws_region_name": "aws_sns_sqs.region_name",
        "aws_sns_sqs.aws_region_name": "aws_sns_sqs.region_name",

        "aws.secret_access_key": "aws_sns_sqs.aws_secret_access_key",
        "aws.aws_secret_access_key": "aws_sns_sqs.aws_secret_access_key",
        "aws_sns_sqs.secret_access_key": "aws_sns_sqs.aws_secret_access_key",

        "aws.access_key_id": "aws_sns_sqs.aws_access_key_id",
        "aws.aws_access_key_id": "aws_sns_sqs.aws_access_key_id",
        "aws_sns_sqs.access_key_id": "aws_sns_sqs.aws_access_key_id",

        "aws.endpoint_url": ("aws_endpoint_urls.sns", "aws_endpoint_urls.sqs"),
        "aws_sns_sqs.endpoint_url": ("aws_endpoint_urls.sns", "aws_endpoint_urls.sqs"),
        "aws.aws_endpoint_url": ("aws_endpoint_urls.sns", "aws_endpoint_urls.sqs"),
        "aws_sns_sqs.aws_endpoint_url": ("aws_endpoint_urls.sns", "aws_endpoint_urls.sqs"),

        "aws.endpoint_urls.sns": "aws_endpoint_urls.sns",
        "aws.endpoint_urls.sqs": "aws_endpoint_urls.sqs",
        "aws_sns_sqs.endpoint_urls.sns": "aws_endpoint_urls.sns",
        "aws_sns_sqs.endpoint_urls.sqs": "aws_endpoint_urls.sqs",
        "aws.aws_sns_endpoint_url": "aws_endpoint_urls.sns",
        "aws.aws_sqs_endpoint_url": "aws_endpoint_urls.sqs",
        "aws_sns_sqs.aws_sns_endpoint_url": "aws_endpoint_urls.sns",
        "aws_sns_sqs.aws_sqs_endpoint_url": "aws_endpoint_urls.sqs",
        "aws.sns_endpoint_url": "aws_endpoint_urls.sns",
        "aws.sqs_endpoint_url": "aws_endpoint_urls.sqs",
        "aws_sns_sqs.sns_endpoint_url": "aws_endpoint_urls.sns",
        "aws_sns_sqs.sqs_endpoint_url": "aws_endpoint_urls.sqs",

        "aws.topic_prefix": "aws_sns_sqs.topic_prefix",
        "aws.queue_name_prefix": "aws_sns_sqs.queue_name_prefix",

        "aws_sns_sqs.aws_kms_master_key_id": ("aws_sns_sqs.sns_kms_master_key_id", "aws_sns_sqs.sqs_kms_master_key_id"),
        "aws_sns_sqs.kms_master_key_id": ("aws_sns_sqs.sns_kms_master_key_id", "aws_sns_sqs.sqs_kms_master_key_id"),
        "aws.aws_kms_master_key_id": ("aws_sns_sqs.sns_kms_master_key_id", "aws_sns_sqs.sqs_kms_master_key_id"),
        "aws.kms_master_key_id": ("aws_sns_sqs.sns_kms_master_key_id", "aws_sns_sqs.sqs_kms_master_key_id"),

        "aws_sns_sqs.aws_sns_kms_master_key_id": "aws_sns_sqs.sns_kms_master_key_id",
        "aws_sns_sqs.aws_sqs_kms_master_key_id": "aws_sns_sqs.sqs_kms_master_key_id",
        "aws.aws_sns_kms_master_key_id": "aws_sns_sqs.sns_kms_master_key_id",
        "aws.aws_sqs_kms_master_key_id": "aws_sns_sqs.sqs_kms_master_key_id",
        "aws.sns_kms_master_key_id": "aws_sns_sqs.sns_kms_master_key_id",
        "aws.sqs_kms_master_key_id": "aws_sns_sqs.sqs_kms_master_key_id",

        "aws_sns_sqs.aws_sqs_kms_data_key_reuse_period": "aws_sns_sqs.sqs_kms_data_key_reuse_period",
        "aws_sns_sqs.aws_kms_data_key_reuse_period": "aws_sns_sqs.sqs_kms_data_key_reuse_period",
        "aws_sns_sqs.kms_data_key_reuse_period": "aws_sns_sqs.sqs_kms_data_key_reuse_period",
        "aws.aws_sqs_kms_data_key_reuse_period": "aws_sns_sqs.sqs_kms_data_key_reuse_period",
        "aws.aws_kms_data_key_reuse_period": "aws_sns_sqs.sqs_kms_data_key_reuse_period",
        "aws.kms_data_key_reuse_period": "aws_sns_sqs.sqs_kms_data_key_reuse_period",

        "aws.queue_policy": "aws_sns_sqs.queue_policy",
        "aws.wildcard_queue_policy": "aws_sns_sqs.wildcard_queue_policy",
    }

HTTP = Options.HTTP
AWSSNSSQS = Options.AWSSNSSQS
AWSEndpointURLs = Options.AWSEndpointURLs
AMQP = Options.AMQP
Watcher = Options.Watcher

# Options of options
Http = HTTP
Amqp = AMQP
AwsSnsSqs = AWSSNSSQS
AwsEndpointUrls = AWSEndpointURLs
AWSEndpointUrls = AWSEndpointURLs
