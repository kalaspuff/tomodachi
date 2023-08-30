import os
from typing import Any, List

from opentelemetry.instrumentation.auto_instrumentation._load import _load_configurators, _load_distro
from opentelemetry.util._once import Once
from pkg_resources import iter_entry_points

# todo: these tests should use fixtures instead
from tomodachi.opentelemetry.distro import (
    OpenTelemetryConfigurator,
    OpenTelemetryDistro,
    _get_logger_provider,
    _get_meter_provider,
    _get_tracer_provider,
)


def test_opentelemetry_auto_configure() -> None:
    from opentelemetry import trace
    from opentelemetry._logs import _internal as logs_internal
    from opentelemetry.metrics import _internal as metrics_internal

    trace._TRACER_PROVIDER = None
    metrics_internal._METER_PROVIDER = None
    logs_internal._LOGGER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    metrics_internal._METER_PROVIDER_SET_ONCE = Once()
    logs_internal._LOGGER_PROVIDER_SET_ONCE = Once()

    environ = {k: v for k, v in os.environ.items()}
    try:
        os.environ.pop("OTEL_PYTHON_CONFIGURATOR", None)
        os.environ["OTEL_PYTHON_DISTRO"] = "tomodachi"

        distro = _load_distro()
        assert isinstance(distro, OpenTelemetryDistro)

        distro.configure()

        configurator_name = os.environ.get("OTEL_PYTHON_CONFIGURATOR", None)
        assert configurator_name == "tomodachi"

        configurator = [
            entry_point
            for entry_point in iter_entry_points("opentelemetry_configurator")
            if configurator_name == entry_point.name
        ][0]
        assert isinstance(configurator.load()(), OpenTelemetryConfigurator)

        assert _get_tracer_provider() is None
        assert _get_meter_provider() is None
        assert _get_logger_provider() is None

        _load_configurators()

        tracer_provider = _get_tracer_provider()
        meter_provider = _get_meter_provider()
        logger_provider = _get_logger_provider()

        assert tracer_provider is not None
        assert meter_provider is not None
        assert logger_provider is not None

        assert tracer_provider.resource.attributes["telemetry.auto.version"]
        assert meter_provider._sdk_config.resource.attributes["telemetry.auto.version"]
        assert logger_provider.resource.attributes["telemetry.auto.version"]

        assert meter_provider is not None
        assert len(meter_provider._sdk_config.views) == 2
    finally:
        os.environ.clear()
        for k, v in environ.items():
            os.environ[k] = v


def test_opentelemetry_load_tomodachi_prometheus_meter_provider() -> None:
    import prometheus_client
    from opentelemetry import trace
    from opentelemetry._logs import _internal as logs_internal
    from opentelemetry.metrics import _internal as metrics_internal

    trace._TRACER_PROVIDER = None
    metrics_internal._METER_PROVIDER = None
    logs_internal._LOGGER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    metrics_internal._METER_PROVIDER_SET_ONCE = Once()
    logs_internal._LOGGER_PROVIDER_SET_ONCE = Once()

    environ = {k: v for k, v in os.environ.items()}
    start_http_server = prometheus_client.start_http_server
    try:
        os.environ["OTEL_PYTHON_METER_PROVIDER"] = "tomodachi_prometheus"
        os.environ["OTEL_PYTHON_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED"] = "true"

        configurator = OpenTelemetryConfigurator()
        configurator.configure()

        meter_provider = _get_meter_provider()
        assert meter_provider is not None
        assert len(meter_provider._sdk_config.views) == 3
        assert getattr(meter_provider, "_prometheus_server_started", None) is False
        assert getattr(meter_provider, "_prometheus_registry", None) is not None
        assert type(meter_provider).__name__ == "TomodachiPrometheusMeterProvider"

        import prometheus_client

        catched_values: List = []

        def _start_http_server(*a: Any, **kw: Any) -> None:
            catched_values.append(a)
            catched_values.append(kw)

        setattr(prometheus_client, "start_http_server", _start_http_server)

        meter_provider.get_meter("tomodachi.opentelemetry")
        assert getattr(meter_provider, "_prometheus_server_started", None) is True
        assert catched_values == [
            (),
            {"port": 9464, "addr": "localhost", "registry": getattr(meter_provider, "_prometheus_registry", None)},
        ]
    finally:
        os.environ.clear()
        for k, v in environ.items():
            os.environ[k] = v
        setattr(prometheus_client, "start_http_server", start_http_server)
