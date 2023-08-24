import os
from typing import Any, cast

from prometheus_client.registry import Collector, CollectorRegistry

from opentelemetry.exporter.prometheus import _CustomCollector
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import Metric, MetricReader, MetricsData, ResourceMetrics, ScopeMetrics
from tomodachi.opentelemetry.distro import _create_resource
from tomodachi.opentelemetry.environment_variables import (
    OTEL_PYTHON_PROMETHEUS_METRICS_EXPORT_ADDRESS,
    OTEL_PYTHON_PROMETHEUS_METRICS_EXPORT_PORT,
)

UNIT_TRANSFORM_MAP = {
    "s": "seconds",
    "second": "seconds",
    "request": "requests",
    "task": "tasks",
    "message": "messages",
    "byte": "bytes",
    "by": "bytes",
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
    "1": "info",
}

REGISTRY_ = CollectorRegistry(auto_describe=True)


class TomodachiPrometheusMetricReader(MetricReader):
    def __init__(self, prefix: str = "tomodachi") -> None:
        super().__init__()
        self._collector = _CustomCollector(prefix)
        REGISTRY_.register(cast(Collector, self._collector))
        setattr(self._collector, "_callback", self.collect)

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: Any) -> None:
        super().shutdown(timeout_millis=timeout_millis, **kwargs)
        REGISTRY_.unregister(cast(Collector, self._collector))

    def _transform_metric(self, metric: Metric) -> Metric:
        unit = str(metric.unit.replace("{", "").replace("}", "") if metric.unit else "").lower()
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
        if metrics_data is None:
            return

        metrics_data_ = MetricsData(
            resource_metrics=[
                ResourceMetrics(
                    resource=rm.resource,
                    scope_metrics=[
                        ScopeMetrics(
                            scope=sm.scope,
                            metrics=[self._transform_metric(metric) for metric in sm.metrics],
                            schema_url=sm.schema_url,
                        )
                        for sm in rm.scope_metrics
                    ],
                    schema_url=rm.schema_url,
                )
                for rm in metrics_data.resource_metrics
            ]
        )

        self._collector.add_metrics_data(metrics_data_)


class TomodachiPrometheusMeterProvider(MeterProvider):
    def __init__(self) -> None:
        from prometheus_client import start_http_server

        addr = str(
            os.environ.get(OTEL_PYTHON_PROMETHEUS_METRICS_EXPORT_ADDRESS)
            or os.environ.get("PROMETHEUS_METRICS_EXPORT_ADDRESS")
            or "0.0.0.0"
        )
        port = int(
            os.environ.get(OTEL_PYTHON_PROMETHEUS_METRICS_EXPORT_PORT)
            or os.environ.get("PROMETHEUS_METRICS_EXPORT_PORT")
            or 8000
        )

        resource = _create_resource()

        # start prometheus client
        start_http_server(port=port, addr=addr, registry=REGISTRY_)

        # exporter to export metrics to prometheus
        reader = TomodachiPrometheusMetricReader()

        super().__init__(metric_readers=[reader], resource=resource)
