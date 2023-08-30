import os
import re
from collections import deque
from json import dumps
from re import IGNORECASE, UNICODE, compile
from typing import Any, Dict, List, Optional, Type, cast

from opentelemetry.exporter.prometheus import _CustomCollector as _PrometheusCustomCollector
from opentelemetry.sdk.metrics import Meter, MeterProvider
from opentelemetry.sdk.metrics._internal.point import DataT, HistogramDataPoint, NumberDataPoint
from opentelemetry.sdk.metrics.export import Metric, MetricReader, MetricsData, ResourceMetrics, ScopeMetrics
from opentelemetry.sdk.resources import SERVICE_INSTANCE_ID as RESOURCE_SERVICE_INSTANCE_ID
from opentelemetry.sdk.resources import SERVICE_NAME as RESOURCE_SERVICE_NAME
from opentelemetry.sdk.resources import SERVICE_NAMESPACE as RESOURCE_SERVICE_NAMESPACE
from opentelemetry.sdk.util.instrumentation import InstrumentationScope
from opentelemetry.util.types import AttributeValue
from prometheus_client import Info
from prometheus_client.core import Metric as PrometheusMetric
from prometheus_client.registry import Collector, CollectorRegistry
from prometheus_client.samples import Exemplar as PrometheusExemplar

from tomodachi import logging
from tomodachi.opentelemetry.distro import _create_resource
from tomodachi.opentelemetry.environment_variables import (
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO,
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_TARGET_INFO,
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS,
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_PORT,
)
from tomodachi.opentelemetry.exemplars import Exemplar, ExemplarReservoir

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


class OtelScopeInfoCollector(Info):
    _registry: Optional[CollectorRegistry] = None
    _value: Dict[str, str]

    def __init__(self) -> None:
        super().__init__(
            "otel_scope",
            "Instrumentation Scope metadata",
        )
        self._value = {}

    def register(self, registry: Optional[CollectorRegistry] = REGISTRY_) -> None:
        if not self._registry and registry:
            registry.register(self)
            self._registry = registry

    def unregister(self) -> None:
        if self._registry:
            self._registry.unregister(self)
            self._registry = None

    @property
    def is_registered(self) -> bool:
        return True if self._registry else False

    @property
    def value(self) -> Dict[str, str]:
        return self._value

    def set_info(self, info: InstrumentationScope) -> None:
        value = {}
        if info.name:
            value["otel_scope_name"] = info.name
        if info.version:
            value["otel_scope_version"] = info.version
        self.info(value)


otel_scope_info_collector = OtelScopeInfoCollector()


class _CustomCollector(_PrometheusCustomCollector):
    def __init__(self, prefix: str = "", registry: CollectorRegistry = REGISTRY_) -> None:
        super().__init__(prefix)
        self._registry = registry
        self._exemplars_data: deque[List[Optional[Exemplar]]] = deque()

    def add_exemplars_data(self, exemplars_data: List[Optional[Exemplar]]) -> None:
        self._exemplars_data.append(exemplars_data)

    def _translate_to_prometheus(
        self,
        metrics_data: MetricsData,
        metric_family_id_metric_family: Dict[str, PrometheusMetric],
    ) -> None:
        metric_family_id_metric_family.clear()
        super()._translate_to_prometheus(metrics_data, metric_family_id_metric_family)
        exemplars = self._exemplars_data.popleft()
        if metric_family_id_metric_family:
            target_info: Dict[str, str] = self._registry.get_target_info() or {}
            add_metric_labels = {k: v for k, v in target_info.items() if k in ("job", "instance")}
            if otel_scope_info_collector.is_registered:
                add_metric_labels.update(otel_scope_info_collector.value)

            if add_metric_labels:
                for metric_family in metric_family_id_metric_family.values():
                    for sample in metric_family.samples:
                        sample.labels.update(add_metric_labels)

            for metric_family in metric_family_id_metric_family.values():
                if metric_family.__class__.__name__ in ("HistogramMetricFamily", "CounterMetricFamily"):
                    for idx, sample in enumerate(metric_family.samples[:]):
                        exemplar = exemplars.pop(0) if exemplars else None
                        if exemplar:
                            metric_family.samples[idx] = sample._replace(
                                exemplar=PrometheusExemplar(
                                    {"trace_id": exemplar.trace_id, "span_id": exemplar.span_id},
                                    exemplar.value,
                                    exemplar.time_unix_nano / 1e9,
                                )
                            )


class TomodachiPrometheusMetricReader(MetricReader):
    def __init__(self, prefix: str = "tomodachi", registry: CollectorRegistry = REGISTRY_) -> None:
        super().__init__()

        try:
            if str(
                os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO)
                or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO")
                or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_INCLUDE_OTEL_SCOPE_INFO")
                or os.environ.get("OTEL_EXPORTER_PROMETHEUS_INCLUDE_OTEL_SCOPE_INFO")
                or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_INCLUDE_SCOPE_INFO")
                or os.environ.get("OTEL_EXPORTER_PROMETHEUS_INCLUDE_SCOPE_INFO")
                or 0
            ).lower().strip() in (
                "1",
                "true",
            ):
                otel_scope_info_collector.register(registry)
        except ValueError:
            pass

        self._collector = _CustomCollector(prefix, registry)
        self._registry = registry
        self._registry.register(cast(Collector, self._collector))
        setattr(self._collector, "_callback", self.collect)

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: Any) -> None:
        super().shutdown(timeout_millis=timeout_millis, **kwargs)
        self._registry.unregister(cast(Collector, self._collector))
        otel_scope_info_collector.unregister()

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

        return Metric(
            name=metric.name,
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
                    metric_ = self._transform_metric(metric)
                    data_type: Type[DataT] = metric.data.__class__
                    data_kw: Dict[str, Any] = {
                        key: getattr(metric.data, key, None)
                        for key in ("is_monotonic", "aggregation_temporality")
                        if hasattr(metric_.data, key)
                    }
                    for data_point in metric.data.data_points:
                        metrics_data_ = MetricsData(
                            resource_metrics=[
                                ResourceMetrics(
                                    resource=resource_metric.resource,
                                    scope_metrics=[
                                        ScopeMetrics(
                                            scope=scope_metric.scope,
                                            metrics=[
                                                Metric(
                                                    name=metric_.name,
                                                    description=metric_.description,
                                                    unit=metric_.unit,
                                                    data=data_type(data_points=[cast(Any, data_point)], **data_kw),
                                                )
                                            ],
                                            schema_url=scope_metric.schema_url,
                                        )
                                    ],
                                    schema_url=resource_metric.schema_url,
                                )
                            ]
                        )

                        reservoir = ExemplarReservoir(instrument_name=metric.name, attributes=data_point.attributes)
                        exemplars: List[Optional[Exemplar]] = []

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
                                    exemplars.append(exemplar)

                        self._collector.add_metrics_data(metrics_data_)
                        self._collector.add_exemplars_data(exemplars)
                        reservoir.reset()


class TomodachiPrometheusMeterProvider(MeterProvider):
    def __init__(self, prefix: str = "tomodachi", registry: CollectorRegistry = REGISTRY_) -> None:
        self._prometheus_server_started = False
        self._prometheus_registry = registry
        self._non_letters_digits_underscore_re = compile(r"[^\w]", UNICODE | IGNORECASE)

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

        resource_attributes = {
            _sanitize_key(k): _sanitize_value(v)
            for k, v in resource.attributes.items()
            if k
            not in (RESOURCE_SERVICE_INSTANCE_ID, RESOURCE_SERVICE_NAME, RESOURCE_SERVICE_NAMESPACE, "job", "instance")
        }

        target_info: Dict[str, str] = self._prometheus_registry.get_target_info() or {}
        return {"job": job, "instance": instance, **resource_attributes, **target_info}

    def _start_prometheus_http_server(self) -> None:
        if self._prometheus_server_started:
            return

        import prometheus_client

        addr = str(
            os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS)
            or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS")
            or os.environ.get("OTEL_PYTHON_TOMODACHI_PROMETHEUS_ADDRESS")
            or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_ADDRESS")
            or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_HOST")
            or os.environ.get("OTEL_EXPORTER_PROMETHEUS_HOST")
            or "localhost"
        )
        port = int(
            os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_PORT)
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

        # start prometheus client
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
        otel_scope_info_collector.set_info(InstrumentationScope(name, version, schema_url))
        self._start_prometheus_http_server()
        return super().get_meter(name, version=version, schema_url=schema_url)
