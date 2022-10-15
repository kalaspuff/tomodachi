from __future__ import annotations

import platform
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type, TypeVar, Union, cast

from .interface import OptionsInterface

T = TypeVar("T")


def DEFAULT(cls: Type[T]) -> T:
    return cast(T, type("DEFAULT", (type(cls),), {"_default": True}))


class _HTTP(OptionsInterface):
    port: int
    host: Optional[str]
    reuse_port: bool
    content_type: str
    charset: str
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
    _legacy_fallback: Dict[str, Union[str, Tuple[str, ...]]] = {
        "max_buffer_size": "client_max_size",
        "max_upload_size": "client_max_size",
    }

    def __init__(
        self,
        *,
        port: int = 9700,
        host: Optional[str] = "0.0.0.0",
        reuse_port: bool = (True if platform.system() == "Linux" else False),
        content_type: str = "text/plain; charset=utf-8",
        charset: str = "utf-8",
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
        self.charset = charset
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


class _AWSSNSSQS(OptionsInterface):
    region_name: Optional[str]
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    topic_prefix: str
    queue_name_prefix: str
    sns_kms_master_key_id: Optional[str]
    sqs_kms_master_key_id: Optional[str]
    sqs_kms_data_key_reuse_period: Optional[int]
    queue_policy: Optional[str]
    wildcard_queue_policy: Optional[str]

    _hierarchy: Tuple[str, ...] = ("aws_sns_sqs",)
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
        sqs_kms_data_key_reuse_period: Optional[int] = None,
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


class _AWSEndpointURLs(OptionsInterface):
    sns: Optional[str]
    sqs: Optional[str]

    _hierarchy: Tuple[str, ...] = ("aws_endpoint_urls",)

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


class _AMQP_QOS(OptionsInterface):
    queue_prefetch_count: int
    global_prefetch_count: int

    _hierarchy: Tuple[str, ...] = ("amqp", "qos")

    def __init__(
        self,
        *,
        queue_prefetch_count: int = 100,
        global_prefetch_count: int = 400,
        **kwargs: Any,
    ):
        self.queue_prefetch_count = queue_prefetch_count
        self.global_prefetch_count = global_prefetch_count

        self._load_keyword_options(**kwargs)


class _AMQP(OptionsInterface):
    class QOS(_AMQP_QOS):
        pass

    host: str
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
    qos: QOS

    _hierarchy: Tuple[str, ...] = ("amqp",)

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 5672,
        login: str = "guest",
        password: str = "guest",
        exchange_name: str = "amq.topic",
        routing_key_prefix: str = "",
        queue_name_prefix: str = "",
        virtualhost: str = "/",
        ssl: bool = False,
        heartbeat: int = 60,
        queue_ttl: int = 86400,
        qos: Union[Mapping[str, Any], QOS] = DEFAULT(QOS),
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

        input_: Tuple[Tuple[str, Union[Mapping[str, Any], OptionsInterface], type], ...] = (("qos", qos, self.QOS),)
        self._load_initial_input(input_)
        self._load_keyword_options(**kwargs)


class _Watcher(OptionsInterface):
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


class Options(OptionsInterface):
    class HTTP(_HTTP):
        pass

    class AWSSNSSQS(_AWSSNSSQS):
        pass

    class AWSEndpointURLs(_AWSEndpointURLs):
        pass

    class AMQP(_AMQP):
        class QOS(_AMQP_QOS):
            pass

    class Watcher(_Watcher):
        pass

    http: HTTP
    aws_sns_sqs: AWSSNSSQS
    aws_endpoint_urls: AWSEndpointURLs
    amqp: AMQP
    watcher: Watcher

    _hierarchy: Tuple[str, ...] = ()
    _legacy_fallback: Dict[str, Union[str, Tuple[str, ...]]] = {
        "aws.region_name": "aws_sns_sqs.region_name",
        "aws.aws_region_name": "aws_sns_sqs.region_name",
        "aws.secret_access_key": "aws_sns_sqs.aws_secret_access_key",
        "aws.aws_secret_access_key": "aws_sns_sqs.aws_secret_access_key",
        "aws.access_key_id": "aws_sns_sqs.aws_access_key_id",
        "aws.aws_access_key_id": "aws_sns_sqs.aws_access_key_id",
        "aws.endpoint_url": ("aws_endpoint_urls.sns", "aws_endpoint_urls.sqs"),
        "aws.aws_endpoint_url": ("aws_endpoint_urls.sns", "aws_endpoint_urls.sqs"),
        "aws.endpoint_urls.sns": "aws_endpoint_urls.sns",
        "aws.endpoint_urls.sqs": "aws_endpoint_urls.sqs",
        "aws.aws_sns_endpoint_url": "aws_endpoint_urls.sns",
        "aws.aws_sqs_endpoint_url": "aws_endpoint_urls.sqs",
        "aws.sns_endpoint_url": "aws_endpoint_urls.sns",
        "aws.sqs_endpoint_url": "aws_endpoint_urls.sqs",
        "aws.topic_prefix": "aws_sns_sqs.topic_prefix",
        "aws.queue_name_prefix": "aws_sns_sqs.queue_name_prefix",
        "aws.aws_kms_master_key_id": ("aws_sns_sqs.sns_kms_master_key_id", "aws_sns_sqs.sqs_kms_master_key_id"),
        "aws.kms_master_key_id": ("aws_sns_sqs.sns_kms_master_key_id", "aws_sns_sqs.sqs_kms_master_key_id"),
        "aws.aws_sns_kms_master_key_id": "aws_sns_sqs.sns_kms_master_key_id",
        "aws.aws_sqs_kms_master_key_id": "aws_sns_sqs.sqs_kms_master_key_id",
        "aws.sns_kms_master_key_id": "aws_sns_sqs.sns_kms_master_key_id",
        "aws.sqs_kms_master_key_id": "aws_sns_sqs.sqs_kms_master_key_id",
        "aws.aws_sqs_kms_data_key_reuse_period": "aws_sns_sqs.sqs_kms_data_key_reuse_period",
        "aws.aws_kms_data_key_reuse_period": "aws_sns_sqs.sqs_kms_data_key_reuse_period",
        "aws.kms_data_key_reuse_period": "aws_sns_sqs.sqs_kms_data_key_reuse_period",
        "aws.queue_policy": "aws_sns_sqs.queue_policy",
        "aws.wildcard_queue_policy": "aws_sns_sqs.wildcard_queue_policy",
    }

    def __init__(
        self,
        *,
        http: Union[Mapping[str, Any], HTTP] = DEFAULT(HTTP),
        aws_sns_sqs: Union[Mapping[str, Any], AWSSNSSQS] = DEFAULT(AWSSNSSQS),
        aws_endpoint_urls: Union[Mapping[str, Any], AWSEndpointURLs] = DEFAULT(AWSEndpointURLs),
        amqp: Union[Mapping[str, Any], AMQP] = DEFAULT(AMQP),
        watcher: Union[Mapping[str, Any], Watcher] = DEFAULT(Watcher),
        **kwargs: Any,
    ):
        input_: Tuple[Tuple[str, Union[Mapping[str, Any], OptionsInterface], type], ...] = (
            ("http", http, self.HTTP),
            ("aws_sns_sqs", aws_sns_sqs, self.AWSSNSSQS),
            ("aws_endpoint_urls", aws_endpoint_urls, self.AWSEndpointURLs),
            ("amqp", amqp, self.AMQP),
            ("watcher", watcher, self.Watcher),
        )

        self._load_initial_input(input_)
        self._load_keyword_options(**kwargs)
