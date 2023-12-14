import platform

import tomodachi
from tomodachi.options import Options


def test_init_options_class() -> None:
    options = Options(
        http=Options.HTTP(
            port=8080,
            content_type="application/json; charset=utf-8",
            access_log=False,
            real_ip_from=["127.0.0.1/32", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
            keepalive_timeout=10,
            max_keepalive_time=30,
        ),
        aws_sns_sqs=Options.AWSSNSSQS(
            queue_name_prefix="queue-prefix-",
            topic_prefix="topic-prefix-",
            region_name="eu-west-1",
            aws_access_key_id="AKIAXXXXXXXXXXXXXXXX",
            aws_secret_access_key="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            sqs_kms_master_key_id="arn:aws:kms:eu-west-1:123456789012:key/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
            sns_kms_master_key_id="arn:aws:kms:eu-west-1:000000004711:key/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
        ),
        aws_endpoint_urls=Options.AWSEndpointURLs(
            sns="http://localhost:4566",
            sqs=None,
        ),
    )

    assert options.http.port == 8080
    assert "127.0.0.1/32" in options.http.real_ip_from
    assert "127.0.0.1" not in options.http.real_ip_from
    assert options.aws_endpoint_urls.sns == "http://localhost:4566"
    assert options.aws_endpoint_urls.sqs is None
    assert options.aws_sns_sqs.queue_name_prefix == "queue-prefix-"
    assert options.aws_sns_sqs.topic_prefix == "topic-prefix-"
    assert options.aws_sns_sqs.region_name == "eu-west-1"

    assert options.http.real_ip_header == "X-Forwarded-For"
    assert options.amqp.login == "guest"

    assert options.get("http", {}).get("port") == 8080
    assert options.get("http.port") == 8080
    assert options.http["port"] == 8080
    assert options.get("http")["port"] == 8080
    assert options.aws_endpoint_urls.get("sns") == "http://localhost:4566"
    assert options.aws_endpoint_urls.get("sns", None) == "http://localhost:4566"

    assert options.aws_endpoint_urls.get("key_does_not_exist", "abcd") == "abcd"
    assert options.get("aws_endpoint_urls.key_does_not_exist", []) == []
    assert options.get("invalid_option_key.key_does_not_exist", 0) == 0

    assert options.asdict().get("http.port") == 8080
    assert options.asdict()["http.port"] == 8080


def test_default_values() -> None:
    options = Options()

    assert options.http.port == 9700
    assert options.asdict() == {
        "http.port": 9700,
        "http.host": "0.0.0.0",
        "http.reuse_port": True if platform.system() == "Linux" else False,
        "http.content_type": "text/plain; charset=utf-8",
        "http.charset": "utf-8",
        "http.client_max_size": 104857600,
        "http.termination_grace_period_seconds": 30,
        "http.access_log": True,
        "http.real_ip_from": [],
        "http.real_ip_header": "X-Forwarded-For",
        "http.keepalive_timeout": 0,
        "http.keepalive_expiry": 0,
        "http.max_keepalive_time": None,
        "http.max_keepalive_requests": None,
        "http.server_header": "tomodachi",
        "aws_sns_sqs.region_name": None,
        "aws_sns_sqs.aws_access_key_id": None,
        "aws_sns_sqs.aws_secret_access_key": None,
        "aws_sns_sqs.topic_prefix": "",
        "aws_sns_sqs.queue_name_prefix": "",
        "aws_sns_sqs.sns_kms_master_key_id": None,
        "aws_sns_sqs.sqs_kms_master_key_id": None,
        "aws_sns_sqs.sqs_kms_data_key_reuse_period": None,
        "aws_sns_sqs.queue_policy": None,
        "aws_sns_sqs.wildcard_queue_policy": None,
        "aws_endpoint_urls.sns": None,
        "aws_endpoint_urls.sqs": None,
        "amqp.host": "127.0.0.1",
        "amqp.port": 5672,
        "amqp.login": "guest",
        "amqp.password": "guest",
        "amqp.exchange_name": "amq.topic",
        "amqp.routing_key_prefix": "",
        "amqp.queue_name_prefix": "",
        "amqp.virtualhost": "/",
        "amqp.ssl": False,
        "amqp.heartbeat": 60,
        "amqp.queue_ttl": 86400,
        "amqp.qos.queue_prefetch_count": 100,
        "amqp.qos.global_prefetch_count": 400,
        "watcher.ignored_dirs": [],
        "watcher.watched_file_endings": [],
    }

    assert Options.HTTP().port == 9700
    assert Options.HTTP().asdict() == {
        "port": 9700,
        "host": "0.0.0.0",
        "reuse_port": True if platform.system() == "Linux" else False,
        "content_type": "text/plain; charset=utf-8",
        "charset": "utf-8",
        "client_max_size": 104857600,
        "termination_grace_period_seconds": 30,
        "access_log": True,
        "real_ip_from": [],
        "real_ip_header": "X-Forwarded-For",
        "keepalive_timeout": 0,
        "keepalive_expiry": 0,
        "max_keepalive_time": None,
        "max_keepalive_requests": None,
        "server_header": "tomodachi",
    }


def test_modify_values() -> None:
    options = Options()

    assert options.http.port == 9700
    options.http.port = 1234
    assert options.http.port == 1234
    assert options["http"].port == 1234
    assert options["http.port"] == 1234

    options["http.port"] = 9999
    assert options.http.port == 9999
    assert options["http"].port == 9999
    assert options["http.port"] == 9999

    options.get("http").port = 4711
    assert options.http.port == 4711

    options.http["port"] = 1338
    assert options.http.port == 1338

    options["http"]["port"] = 1337
    assert options.http.port == 1337

    options.http = Options.HTTP(port=9876)
    assert options.http.port == 9876

    options["http"] = Options.HTTP(port=1111)
    assert options.http.port == 1111


def test_dict_init() -> None:
    assert Options(**{"http.port": 1234}).http.port == 1234

    assert Options(**{"http": {"port": 404}}).http.port == 404
    assert Options(**{"http": {"port": 404}}).http.termination_grace_period_seconds == 30

    assert Options(**{"http.port": 1234, "http.termination_grace_period_seconds": 60}).http.port == 1234
    assert (
        Options(
            **{"http.port": 1234, "http.termination_grace_period_seconds": 60}
        ).http.termination_grace_period_seconds
        == 60
    )

    assert Options(**{"http.port": 555, "http": {"keepalive_timeout": 5, "max_keepalive_time": 30}}).http.port == 555
    assert (
        Options(**{"http.port": 555, "http": {"keepalive_timeout": 5, "max_keepalive_time": 30}}).http.keepalive_timeout
        == 5
    )
    assert (
        Options(
            **{"http.port": 555, "http": {"keepalive_timeout": 5, "max_keepalive_time": 30}}
        ).http.max_keepalive_time
        == 30
    )

    assert Options(**{"http": {"keepalive_timeout": 5, "max_keepalive_time": 30}, "http.port": 555}).http.port == 555
    assert (
        Options(**{"http": {"keepalive_timeout": 5, "max_keepalive_time": 30}, "http.port": 555}).http.keepalive_timeout
        == 5
    )
    assert (
        Options(
            **{"http": {"keepalive_timeout": 5, "max_keepalive_time": 30}, "http.port": 555}
        ).http.max_keepalive_time
        == 30
    )

    assert Options(http={"keepalive_timeout": 5, "max_keepalive_time": 30}, **{"http.port": 555}).http.port == 555
    assert (
        Options(http={"keepalive_timeout": 5, "max_keepalive_time": 30}, **{"http.port": 555}).http.keepalive_timeout
        == 5
    )
    assert (
        Options(http={"keepalive_timeout": 5, "max_keepalive_time": 30}, **{"http.port": 555}).http.max_keepalive_time
        == 30
    )

    assert (
        Options(
            **{"amqp.login": "tron", "amqp.qos": {"queue_prefetch_count": 10, "global_prefetch_count": 50}}
        ).amqp.login
        == "tron"
    )
    assert (
        Options(
            **{"amqp.login": "tron", "amqp.qos": {"queue_prefetch_count": 42, "global_prefetch_count": 0}}
        ).amqp.qos.queue_prefetch_count
        == 42
    )
    assert Options(**{"amqp.qos.queue_prefetch_count": 999}).amqp.login == "guest"
    assert Options(**{"amqp.qos.queue_prefetch_count": 999}).amqp.qos.queue_prefetch_count == 999

    assert (
        Options(amqp={"login": "tron", "qos": {"queue_prefetch_count": 10, "global_prefetch_count": 50}}).amqp.login
        == "tron"
    )
    assert Options(amqp={"login": "tron", "qos.queue_prefetch_count": 4711}).amqp.qos.asdict() == {
        "queue_prefetch_count": 4711,
        "global_prefetch_count": 400,
    }
    assert (
        Options(
            amqp={"login": "tron", "qos": {"queue_prefetch_count": 10, "global_prefetch_count": 50}}
        ).amqp.qos.queue_prefetch_count
        == 10
    )


def test_legacy_fallback_init() -> None:
    options = Options(
        **{
            "aws": {
                "region_name": "eu-west-1",
                "aws_secret_access_key": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                "endpoint_url": "http://localhost:4566",
                "kms_master_key_id": "arn:aws:kms:eu-west-1:123456789012:key/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
            },
            "aws_sns_sqs": {
                "queue_name_prefix": "queue-name-prefix",
                "topic_prefix": "topic-name-prefix",
            },
            "aws.access_key_id": "AKIAXXXXXXXXXXXXXXXX",
        }
    )

    assert options.aws_sns_sqs.asdict() == {
        "region_name": "eu-west-1",
        "aws_access_key_id": "AKIAXXXXXXXXXXXXXXXX",
        "aws_secret_access_key": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "topic_prefix": "topic-name-prefix",
        "queue_name_prefix": "queue-name-prefix",
        "sns_kms_master_key_id": "arn:aws:kms:eu-west-1:123456789012:key/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
        "sqs_kms_master_key_id": "arn:aws:kms:eu-west-1:123456789012:key/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
        "sqs_kms_data_key_reuse_period": None,
        "queue_policy": None,
        "wildcard_queue_policy": None,
    }
    assert options.aws_endpoint_urls.asdict() == {"sns": "http://localhost:4566", "sqs": "http://localhost:4566"}

    assert Options(
        **{
            "aws": {
                "aws_sqs_endpoint_url": "http://localhost:4566",
            },
        }
    ).aws_endpoint_urls.asdict() == {"sns": None, "sqs": "http://localhost:4566"}


def test_service_new_class() -> None:
    class Service(tomodachi.Service):
        options = {  # type: ignore
            "http.port": 31337,
        }

    service = Service()
    assert service.options.http.port == 31337  # type: ignore
    assert service.options["http"]["port"] == 31337  # type: ignore
    assert service.options.get("http").get("port") == 31337  # type: ignore


def test_service_init_object() -> None:
    class Service(tomodachi.Service):
        def __init__(self) -> None:
            self.options = {  # type: ignore
                "http.port": 31337,
            }

    service = Service()
    assert service.options.http.port == 31337
    assert service.options["http"]["port"] == 31337
    assert service.options.get("http").get("port") == 31337


def test_service_init_suboption_assignment() -> None:
    class Service(tomodachi.Service):
        def __init__(self) -> None:
            self.options.http.port = 31337

    service = Service()
    assert service.options.http.port == 31337
    assert service.options["http"]["port"] == 31337
    assert service.options.get("http").get("port") == 31337


def test_service_dict_option_init_suboption_assignment() -> None:
    class Service(tomodachi.Service):
        options = {  # type: ignore
            "http": {
                "server_header": "example",
            },
            "http.keepalive_timeout": 100,
        }

        def __init__(self) -> None:
            self.options.http.port = 31337  # type: ignore

    service = Service()
    assert service.options.http.port == 31337  # type: ignore
    assert service.options["http"]["port"] == 31337  # type: ignore
    assert service.options.get("http").get("port") == 31337  # type: ignore
    assert service.options.http.keepalive_timeout == 100  # type: ignore
    assert service.options.http.server_header == "example"  # type: ignore
