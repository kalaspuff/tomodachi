import os
import re
from collections import deque
from json import dumps
from re import IGNORECASE, UNICODE, compile
from typing import Any, Callable, Deque, Dict, Generator, List, Optional, cast

from opentelemetry.exporter.prometheus import _CustomCollector as _PrometheusCustomCollector
from opentelemetry.sdk.metrics import Meter, MeterProvider
from opentelemetry.sdk.metrics._internal.point import HistogramDataPoint, NumberDataPoint
from opentelemetry.sdk.metrics.export import Metric, MetricReader, MetricsData, ResourceMetrics, ScopeMetrics
from opentelemetry.sdk.resources import SERVICE_INSTANCE_ID as RESOURCE_SERVICE_INSTANCE_ID
from opentelemetry.sdk.resources import SERVICE_NAME as RESOURCE_SERVICE_NAME
from opentelemetry.sdk.resources import SERVICE_NAMESPACE as RESOURCE_SERVICE_NAMESPACE
from opentelemetry.util.types import AttributeValue
from prometheus_client import Info
from prometheus_client.core import Metric as PrometheusMetric
from prometheus_client.registry import Collector, CollectorRegistry
from prometheus_client.samples import Exemplar as PrometheusExemplar
from prometheus_client.samples import Sample as PrometheusSample

from tomodachi import logging
from tomodachi.opentelemetry.distro import _create_resource
from tomodachi.opentelemetry.environment_variables import (
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_ADDRESS,
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO,
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_TARGET_INFO,
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_NAMESPACE_PREFIX,
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_PORT,
)
from tomodachi.opentelemetry.exemplars import IS_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED, Exemplar, ExemplarReservoir

# currently experimental workaround to provide metrics for Prometheus to scrape according to specification.


UNIT_TRANSFORM_MAP = {
    "s": "seconds",
    "d": "days",
    "h": "hours",
    "min": "minutes",
    "ms": "milliseconds",
    "us": "microseconds",
    "ns": "nanoseconds",
    "second": "seconds",
    "m": "meters",
    "v": "volts",
    "a": "amperes",
    "j": "joules",
    "w": "watts",
    "g": "grams",
    "cel": "celsius",
    "hz": "hertz",
    "request": "requests",
    "req": "requests",
    "task": "tasks",
    "message": "messages",
    "msg": "messages",
    "byte": "bytes",
    "by": "bytes",
    "kiby": "kibibytes",
    "miby": "mebibytes",
    "giby": "gibibytes",
    "tiby": "tebibytes",
    "kby": "kilobytes",
    "mby": "megabytes",
    "gby": "gigabytes",
    "tby": "terabytes",
    "page": "pages",
    "fault": "faults",
    "query": "queries",
    "invocation": "invocations",
    "operation": "operations",
    "packet": "packets",
    "error": "errors",
    "connection": "connections",
    "thread": "threads",
    "class": "classes",
    "buffer": "buffers",
    "%": "percent",
    "1": "ratio",
}

PER_UNIT_TRANSFORM_MAP = {
    "s": "second",
    "m": "minute",
    "h": "hour",
    "d": "day",
    "w": "week",
    "mo": "month",
    "y": "year",
}

REGISTRY_ = CollectorRegistry(auto_describe=True)


class _CustomCollector(_PrometheusCustomCollector):
    _metrics_datas: Deque[MetricsData]
    _callback: Callable  # type: ignore

    def __init__(self, prefix: str = "", registry: CollectorRegistry = REGISTRY_) -> None:
        super().__init__()
        self._prefix = prefix
        self._registry = registry
        self._exemplars: Deque[List[Optional[Exemplar]]] = deque()
        self._include_scope_info = bool(
            str(
                os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO)
                or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO")
                or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_INCLUDE_OTEL_SCOPE_INFO")
                or os.environ.get("OTEL_EXPORTER_PROMETHEUS_INCLUDE_OTEL_SCOPE_INFO")
                or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_INCLUDE_SCOPE_INFO")
                or os.environ.get("OTEL_EXPORTER_PROMETHEUS_INCLUDE_SCOPE_INFO")
                or 1
            )
            .lower()
            .strip()
            in (
                "1",
                "true",
            )
        )

    def add_exemplars(self, exemplars_data: List[Optional[Exemplar]]) -> None:
        self._exemplars.append(exemplars_data)

    def _is_valid_exemplar_metric(self, metric: PrometheusMetric, sample: PrometheusSample) -> bool:
        if metric.type == "counter" and sample.name.endswith("_total"):
            return True
        if metric.type in ("histogram", "gaugehistogram") and sample.name.endswith("_bucket"):
            return True
        return False

    def collect(self) -> Generator[PrometheusMetric, Any, Any]:  # type: ignore
        if self._callback is not None:
            self._callback()

        if self._metrics_datas:
            if self._include_scope_info:
                otel_scope_info_collector = Info(
                    "otel_scope",
                    "Instrumentation Scope metadata",
                    labelnames=("otel_scope_name", "otel_scope_version"),
                    registry=None,
                )
                for metrics_data in self._metrics_datas:
                    for resource_metric in metrics_data.resource_metrics:
                        for scope_metric in resource_metric.scope_metrics:
                            otel_scope_info_collector.labels(
                                otel_scope_name=scope_metric.scope.name,
                                otel_scope_version=scope_metric.scope.version or "",
                            )
                for metric_family in otel_scope_info_collector.collect():
                    yield metric_family

            target_info: Dict[str, str] = self._registry.get_target_info() or {}
            add_metric_labels = {k: v for k, v in target_info.items() if k in ("job", "instance")}

            metric_family_id_metric_family: Dict[str, PrometheusMetric] = {}

            while self._metrics_datas:
                metrics_data = self._metrics_datas.popleft()
                add_metric_labels_ = add_metric_labels.copy()
                if self._include_scope_info:
                    for resource_metric in metrics_data.resource_metrics:
                        for scope_metric in resource_metric.scope_metrics:
                            add_metric_labels_["otel_scope_name"] = scope_metric.scope.name
                            add_metric_labels_["otel_scope_version"] = scope_metric.scope.version or ""

                self.translate_to_prometheus(
                    metrics_data, self._exemplars.popleft(), add_metric_labels_, metric_family_id_metric_family
                )

                if metric_family_id_metric_family:
                    for metric_family in metric_family_id_metric_family.values():
                        yield metric_family

    def translate_to_prometheus(
        self,
        metrics_data: MetricsData,
        exemplars: List[Optional[Exemplar]],
        add_metric_labels: Dict[str, str],
        metric_family_id_metric_family: Dict[str, PrometheusMetric],
    ) -> None:
        metric_family_id_metric_family.clear()
        self._translate_to_prometheus(metrics_data, metric_family_id_metric_family)
        if metric_family_id_metric_family:
            if add_metric_labels:
                for metric_family in metric_family_id_metric_family.values():
                    for sample in metric_family.samples:
                        sample.labels.update(add_metric_labels)

            for metric_family in metric_family_id_metric_family.values():
                if metric_family.type in ("histogram", "gaugehistogram"):
                    for idx, sample in enumerate(metric_family.samples[:]):
                        if not self._is_valid_exemplar_metric(metric_family, sample):
                            continue
                        exemplar = exemplars.pop(0) if exemplars else None
                        if exemplar and not sample.exemplar:
                            exemplar_labels = {
                                **{
                                    self._sanitize(k): self._check_value(v)
                                    for k, v in (exemplar.attributes or {}).items()
                                },
                                "trace_id": exemplar.trace_id,
                                "span_id": exemplar.span_id,
                            }

                            metric_family.samples[idx] = sample._replace(
                                exemplar=PrometheusExemplar(
                                    exemplar_labels,
                                    exemplar.value,
                                    exemplar.time_unix_nano / 1e9,
                                )
                            )


class TomodachiPrometheusMetricReader(MetricReader):
    def __init__(self, prefix: str = "", registry: CollectorRegistry = REGISTRY_) -> None:
        super().__init__()
        self._collector = _CustomCollector(prefix, registry)
        self._registry = registry
        self._registry.register(cast(Collector, self._collector))
        setattr(self._collector, "_callback", self.collect)

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: Any) -> None:
        super().shutdown(timeout_millis=timeout_millis, **kwargs)
        self._registry.unregister(cast(Collector, self._collector))

    def _transform_metric(self, metric: Metric) -> Metric:
        # https://github.com/open-telemetry/opentelemetry-java/issues/5529
        # https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/pkg/translator/prometheus/normalize_name.go#L19

        unit = str(metric.unit.replace("{", "").replace("}", "") if metric.unit else "").lower()
        if "/" in unit:
            u, per_u = unit.split("/", 1)
            u = UNIT_TRANSFORM_MAP.get(u, u)
            per_u = PER_UNIT_TRANSFORM_MAP.get(per_u, per_u)
        else:
            unit = UNIT_TRANSFORM_MAP.get(unit, unit)

        metric_name = metric.name if not self._collector._prefix else f"{self._collector._prefix}_{metric.name}"

        return Metric(
            name=metric_name,
            description=metric.description,
            unit=unit,
            data=metric.data,
        )

    def _receive_metrics(
        self,
        metrics_data: MetricsData,
        timeout_millis: float = 10_000,
        **kwargs: Any,
    ) -> None:
        if metrics_data is None or not metrics_data.resource_metrics:
            return

        for resource_metric in metrics_data.resource_metrics:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    metrics_data_ = MetricsData(
                        resource_metrics=[
                            ResourceMetrics(
                                resource=resource_metric.resource,
                                scope_metrics=[
                                    ScopeMetrics(
                                        scope=scope_metric.scope,
                                        metrics=[self._transform_metric(metric)],
                                        schema_url=scope_metric.schema_url,
                                    )
                                ],
                                schema_url=resource_metric.schema_url,
                            )
                        ]
                    )
                    self._collector.add_metrics_data(metrics_data_)

                    if not IS_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED():
                        self._collector.add_exemplars([])
                        continue

                    # currently only provides exemplars for metrics on the "tomodachi" scope
                    # todo: add support to add exemplars on any instrumentation scope
                    if scope_metric.scope.name != "tomodachi":
                        self._collector.add_exemplars([])
                        continue

                    exemplars: List[Optional[Exemplar]] = []
                    for data_point in metric.data.data_points:
                        reservoir = ExemplarReservoir(
                            instrument_name=metric.name,
                            instrumentation_scope=scope_metric.scope,
                            attributes=data_point.attributes,
                        )

                        if isinstance(data_point, HistogramDataPoint):
                            current_exemplar = None
                            for bucket_count, explicit_bounds, bucket in zip(
                                data_point.bucket_counts,
                                (*data_point.explicit_bounds, None),
                                range(len(data_point.bucket_counts)),
                            ):
                                if bucket_count:
                                    for exemplar in reservoir.collect(
                                        filter_key=lambda e: e.time_unix_nano >= data_point.start_time_unix_nano
                                        and e.time_unix_nano <= data_point.time_unix_nano
                                        and (explicit_bounds is None or e.value <= explicit_bounds),
                                        sort_key=lambda e: -e.value,
                                        bucket=bucket,
                                        limit=1,
                                    ):
                                        current_exemplar = exemplar
                                exemplars.append(current_exemplar)
                        elif isinstance(data_point, NumberDataPoint):
                            is_monotonic = getattr(reservoir.aggregation, "_instrument_is_monotonic", None)
                            current_exemplar = None
                            if is_monotonic is None:
                                is_monotonic = getattr(metric.data, "is_monotonic", None)
                            if is_monotonic:
                                for exemplar in reservoir.collect(
                                    filter_key=lambda e: bool(
                                        e.time_unix_nano >= data_point.start_time_unix_nano
                                        and e.time_unix_nano <= data_point.time_unix_nano
                                    ),
                                    sort_key=lambda e: -e.time_unix_nano,
                                    limit=1,
                                ):
                                    current_exemplar = exemplar
                            exemplars.append(current_exemplar)

                        reservoir.reset()

                    self._collector.add_exemplars(exemplars)


class TomodachiPrometheusMeterProvider(MeterProvider):
    def __init__(self, prefix: Optional[str] = None, registry: CollectorRegistry = REGISTRY_) -> None:
        self._prometheus_server_started = False
        self._prometheus_registry = registry
        self._non_letters_digits_underscore_re = compile(r"[^\w]", UNICODE | IGNORECASE)

        if prefix is None:
            prefix = str(
                os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_NAMESPACE_PREFIX)
                or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_NAMESPACE_PREFIX")
                or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_NAMESPACE_PREFIX")
                or os.environ.get("OTEL_EXPORTER_PROMETHEUS_NAMESPACE_PREFIX")
                or ""
            )

        resource = _create_resource()
        reader = TomodachiPrometheusMetricReader(prefix, registry)

        super().__init__(metric_readers=[reader], resource=resource)

    def _get_target_info(self) -> Dict[str, str]:
        # https://opentelemetry.io/docs/specs/otel/compatibility/prometheus_and_openmetrics/#resource-attributes-1
        # https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md#supporting-target-metadata-in-both-push-based-and-pull-based-systems
        # https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/exporter/prometheusexporter/collector.go#L112-L137
        resource = self._sdk_config.resource

        service_name = str(resource.attributes.get(RESOURCE_SERVICE_NAME) or "")
        service_namespace = str(resource.attributes.get(RESOURCE_SERVICE_NAMESPACE) or "")
        service_instance_id = str(resource.attributes.get(RESOURCE_SERVICE_INSTANCE_ID) or "")

        job = f"{service_namespace}/{service_name}" if service_namespace else service_name
        instance = service_instance_id

        def _sanitize_key(key: str) -> str:
            return self._non_letters_digits_underscore_re.sub("_", key)

        def _sanitize_value(value: AttributeValue) -> str:
            return str(value if isinstance(value, str) else dumps(value, default=str))

        resource_attributes = {_sanitize_key(k): _sanitize_value(v) for k, v in resource.attributes.items()}
        target_info: Dict[str, str] = self._prometheus_registry.get_target_info() or {}
        return {**resource_attributes, **target_info, "job": job, "instance": instance}

    def _start_prometheus_http_server(self) -> None:
        if self._prometheus_server_started:
            return

        import prometheus_client

        addr = str(
            os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_ADDRESS)
            or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS")
            or os.environ.get("OTEL_PYTHON_TOMODACHI_PROMETHEUS_ADDRESS")
            or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_ADDRESS")
            or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_HOST")
            or os.environ.get("OTEL_EXPORTER_PROMETHEUS_HOST")
            or "localhost"
        )
        port = int(
            os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_PORT)
            or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_METER_PROVIDER_PORT")
            or os.environ.get("OTEL_PYTHON_TOMODACHI_PROMETHEUS_PORT")
            or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_PORT")
            or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_PORT")
            or os.environ.get("OTEL_EXPORTER_PROMETHEUS_PORT")
            or 9464
        )

        if str(
            os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_TARGET_INFO)
            or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_INCLUDE_TARGET_INFO")
            or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_INCLUDE_TARGET_INFO")
            or os.environ.get("OTEL_EXPORTER_PROMETHEUS_INCLUDE_TARGET_INFO")
            or 1
        ).lower().strip() in (
            "1",
            "true",
        ):
            try:
                self._prometheus_registry.set_target_info(self._get_target_info())
            except Exception as e:
                logging.get_logger("tomodachi.opentelemetry").warning(
                    "unable to add target_info to prometheus collector registry",
                    error=str(e),
                    opentelemetry_metric_provider="tomodachi_prometheus",
                )

        try:
            prometheus_client.start_http_server(port=port, addr=addr, registry=self._prometheus_registry)
        except OSError as e:
            error_message = re.sub(".*: ", "", e.strerror)
            logging.get_logger("tomodachi.opentelemetry").warning(
                "unable to bind prometheus http server [http] to http://{}:{}/ in otel metric provider".format(
                    "localhost" if addr in ("0.0.0.0", "127.0.0.1") else addr, port
                ),
                host=addr,
                port=port,
                error_message=error_message,
                opentelemetry_metric_provider="tomodachi_prometheus",
            )

            try:
                raise Exception(str(e)).with_traceback(e.__traceback__) from None
            except Exception as exc:
                exc.__traceback__ = e.__traceback__
                raise

        listen_url = "http://{}:{}/".format("localhost" if addr in ("0.0.0.0", "127.0.0.1") else addr, port)
        logging.get_logger("tomodachi.opentelemetry").info(
            "prometheus client started",
            listen_url=listen_url,
            listen_host=addr,
            listen_port=port,
        )
        self._prometheus_server_started = True

    def get_meter(
        self,
        name: str,
        version: Optional[str] = None,
        schema_url: Optional[str] = None,
    ) -> Meter:
        self._start_prometheus_http_server()
        return super().get_meter(name, version=version, schema_url=schema_url)
