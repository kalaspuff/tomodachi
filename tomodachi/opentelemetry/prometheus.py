import os
import re
from typing import Any, Optional, cast

from opentelemetry.exporter.prometheus import _CustomCollector
from opentelemetry.sdk.metrics import Meter, MeterProvider
from opentelemetry.sdk.metrics.export import Metric, MetricReader, MetricsData, ResourceMetrics, ScopeMetrics
from prometheus_client.registry import Collector, CollectorRegistry

from tomodachi import logging
from tomodachi.opentelemetry.distro import _create_resource
from tomodachi.opentelemetry.environment_variables import (
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS,
    OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_PORT,
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
    def __init__(self, prefix: str = "tomodachi", registry: CollectorRegistry = REGISTRY_) -> None:
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
        if metrics_data is None or not metrics_data.resource_metrics:
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
    def __init__(self, prefix: str = "tomodachi", registry: CollectorRegistry = REGISTRY_) -> None:
        self._prometheus_server_started = False
        self._prometheus_registry = registry

        resource = _create_resource()
        reader = TomodachiPrometheusMetricReader(prefix, registry)
        super().__init__(metric_readers=[reader], resource=resource)

    def _start_prometheus_http_server(self) -> None:
        if self._prometheus_server_started:
            return

        from prometheus_client import start_http_server

        addr = str(
            os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS)
            or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS")
            or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_HOST")
            or os.environ.get("OTEL_EXPORTER_PROMETHEUS_HOST")
            or "localhost"
        )
        port = int(
            os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_PORT)
            or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_METER_PROVIDER_PORT")
            or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_HOST")
            or os.environ.get("OTEL_EXPORTER_PROMETHEUS_PORT")
            or 9464
        )

        # start prometheus client
        try:
            start_http_server(port=port, addr=addr, registry=self._prometheus_registry)
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
            "prometheus http server started",
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
