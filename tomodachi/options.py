import platform
from typing import Any, Dict, KeysView, List, Mapping, Optional, Tuple, Union

DEFAULT = object()


class OptionsMapping:
    _hierarchy: Tuple[str, ...] = ()

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            self.__setitem__(key, value)

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

    def __setitem__(self, item: str, value: Any) -> None:
        if "." in item:
            item, attr = item.split(".", 1)
            getattr(self, item)[attr] = value
            return

        if not hasattr(self, item):
            raise AttributeError

        setattr(self, item, value)

    def keys(self) -> KeysView:
        return getattr(self, "__dataclass_fields__", self.__annotations__).keys()

    def asdict(self, *, prefix: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key in self.keys():
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

        _hierarchy = ("http",)

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

            super().__init__(**kwargs)

    class AWSSNSSQS(OptionsMapping):
        region_name: Optional[str]
        aws_access_key_id: Optional[str]
        aws_secret_access_key: Optional[str]
        topic_prefix: str
        queue_name_prefix: str
        sns_kms_master_key_id: Optional[str]
        sqs_kms_master_key_id: Optional[str]
        sqs_kms_data_key_reuse_period: Optional[str]

        _hierarchy = ("aws_sns_sqs",)

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

            super().__init__(**kwargs)

    class AWSEndpointURLs(OptionsMapping):
        sns: Optional[str]
        sqs: Optional[str]

        _hierarchy = ("aws_endpoint_urls",)

        def __init__(
            self,
            *,
            sns: Optional[str] = None,
            sqs: Optional[str] = None,
            **kwargs: Any,
        ):
            self.sns = sns
            self.sqs = sqs

            super().__init__(**kwargs)

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

        _hierarchy = ("amqp",)

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

            super().__init__(**kwargs)

    class Watcher(OptionsMapping):
        ignored_dirs: List[str]
        watched_file_endings: List[str]

        _hierarchy = ("watcher",)

        def __init__(
            self,
            *,
            ignored_dirs: Optional[List[str]] = None,
            watched_file_endings: Optional[List[str]] = None,
            **kwargs: Any,
        ):
            self.ignored_dirs = ignored_dirs if ignored_dirs is not None else []
            self.watched_file_endings = watched_file_endings if watched_file_endings is not None else []

            super().__init__(**kwargs)

    # Options of options
    Http = HTTP
    Amqp = AMQP
    AwsSnsSqs = AWSSNSSQS
    AwsEndpointUrls = AWSEndpointURLs
    AWSEndpointUrls = AWSEndpointURLs

    http: HTTP
    aws_sns_sqs: AWSSNSSQS
    aws_endpoint_urls: AWSEndpointURLs
    amqp: AMQP
    watcher: Watcher

    def __init__(
        self,
        *,
        http: Union[Mapping[str, Any], HTTP] = HTTP(),
        aws_sns_sqs: Union[Mapping[str, Any], AWSSNSSQS] = AWSSNSSQS(),
        aws_endpoint_urls: Union[Mapping[str, Any], AWSEndpointURLs] = AWSEndpointURLs(),
        amqp: Union[Mapping[str, Any], AMQP] = AMQP(),
        watcher: Union[Mapping[str, Any], Watcher] = Watcher(),
        **kwargs: Any,
    ):
        if not isinstance(http, self.HTTP):
            http = self.HTTP(**http)

        if not isinstance(aws_sns_sqs, self.AWSSNSSQS):
            aws_sns_sqs = self.AWSSNSSQS(**aws_sns_sqs)

        if not isinstance(aws_endpoint_urls, self.AWSEndpointURLs):
            aws_endpoint_urls = self.AWSEndpointURLs(**aws_endpoint_urls)

        if not isinstance(amqp, self.AMQP):
            amqp = self.AMQP(**amqp)

        if not isinstance(watcher, self.Watcher):
            watcher = self.Watcher(**watcher)

        self.http = http
        self.aws_sns_sqs = aws_sns_sqs
        self.aws_endpoint_urls = aws_endpoint_urls
        self.amqp = amqp
        self.watcher = watcher

        super().__init__(**kwargs)


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
