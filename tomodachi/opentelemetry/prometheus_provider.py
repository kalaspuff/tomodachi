from typing import Any

from prometheus_client import start_http_server

from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import Metric, MetricsData, ResourceMetrics, ScopeMetrics


class TomodachiPrometheusMetricReader(PrometheusMetricReader):
    def _transform_metric(self, metric: Metric) -> Metric:
        unit = metric.unit.replace("{", "").replace("}", "") if metric.unit else ""

        if unit in ("s", "second"):
            unit = "seconds"
        elif unit in ("request",):
            unit = "requests"
        elif unit in ("task",):
            unit = "tasks"
        elif unit in ("message",):
            unit = "messages"
        elif unit in ("byte", "By", "by"):
            unit = "bytes"
        elif unit in ("fault",):
            unit = "faults"
        elif unit in ("operation",):
            unit = "operations"
        elif unit in ("packet",):
            unit = "packets"
        elif unit in ("error",):
            unit = "errors"
        elif unit in ("connection",):
            unit = "connections"
        elif unit in ("thread",):
            unit = "threads"
        elif unit in ("class",):
            unit = "classes"
        elif unit in ("buffer",):
            unit = "buffers"
        elif unit in ("count",):
            unit = "count"
        elif unit in ("1", 1):
            unit = "info"

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

        transformed_metrics_data = MetricsData(
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

        super()._receive_metrics(transformed_metrics_data, timeout_millis=timeout_millis, **kwargs)


class PrometheusMeterProvider(MeterProvider):
    def __init__(self) -> None:
        # Start Prometheus client
        start_http_server(port=8000, addr="localhost")

        # Exporter to export metrics to Prometheus
        reader = TomodachiPrometheusMetricReader("tomodachi")

        super().__init__(metric_readers=[reader])
