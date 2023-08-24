import logging
import os
from os import environ
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, cast

from opentelemetry import trace
from opentelemetry._logs import _internal as logs_internal
from opentelemetry._logs import set_logger_provider
from opentelemetry.environment_variables import _OTEL_PYTHON_LOGGER_PROVIDER as OTEL_PYTHON_LOGGER_PROVIDER
from opentelemetry.environment_variables import (
    OTEL_LOGS_EXPORTER,
    OTEL_METRICS_EXPORTER,
    OTEL_PYTHON_METER_PROVIDER,
    OTEL_PYTHON_TRACER_PROVIDER,
    OTEL_TRACES_EXPORTER,
)
from opentelemetry.instrumentation.distro import BaseDistro  # type: ignore
from opentelemetry.metrics import _internal as metrics_internal
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk._configuration import (
    _BaseConfigurator,
    _get_exporter_names,
    _get_id_generator,
    _get_sampler,
    _import_config_components,
    _import_exporters,
    _import_id_generator,
    _import_sampler,
)
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs._internal import LogRecordProcessor
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics._internal.aggregation import ExplicitBucketHistogramAggregation
from opentelemetry.sdk.metrics.export import MetricExporter, MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import OTELResourceDetector, Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.id_generator import IdGenerator
from opentelemetry.sdk.trace.sampling import Sampler
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import set_tracer_provider
from opentelemetry.util._importlib_metadata import entry_points
from opentelemetry.util._providers import _load_provider
from opentelemetry.util.types import AttributeValue


def _get_trace_exporters() -> Dict[str, Type[SpanExporter]]:
    return cast(  # type: ignore
        Dict[str, Type[SpanExporter]],
        _import_exporters(
            _get_exporter_names("traces"),
            [],
            [],
        )[0],
    )


def _get_metric_exporters() -> Dict[str, Type[MetricExporter]]:
    return cast(  # type: ignore
        Dict[str, Type[MetricExporter]],
        _import_exporters(
            [],
            _get_exporter_names("metrics"),
            [],
        )[1],
    )


def _get_log_exporters() -> Dict[str, Type[LogExporter]]:
    return cast(  # type: ignore
        Dict[str, Type[LogExporter]],
        _import_exporters(
            [],
            [],
            _get_exporter_names("logs"),
        )[2],
    )


def _get_metric_readers() -> List[Tuple[str, Type[MetricReader]]]:
    names = environ.get("OTEL_PYTHON_METRIC_READER", environ.get("OTEL_METRIC_READER", ""))
    if not names or names.lower().strip() == "none":
        return []

    return cast(
        List[Tuple[str, Type[MetricReader]]],
        _import_config_components([name.strip() for name in names.split(",")], "opentelemetry_metric_reader"),
    )


def _get_tracer_provider() -> Optional[TracerProvider]:
    if trace._TRACER_PROVIDER:
        tracer_provider = cast(TracerProvider, trace.get_tracer_provider())
        if tracer_provider:
            return tracer_provider

    env_value = environ.get(OTEL_PYTHON_TRACER_PROVIDER, environ.get("OTEL_TRACER_PROVIDER", ""))
    if not env_value:
        return None

    if not entry_points(
        group="opentelemetry_tracer_provider",
        name=env_value,
    ):
        raise Exception(f"tracer provider '{env_value}' not found")

    environ[OTEL_PYTHON_TRACER_PROVIDER] = env_value
    tracer_provider = cast(TracerProvider, _load_provider(OTEL_PYTHON_TRACER_PROVIDER, "tracer_provider"))
    set_tracer_provider(tracer_provider)
    return tracer_provider


def _get_meter_provider() -> Optional[MeterProvider]:
    if metrics_internal._METER_PROVIDER:
        meter_provider = cast(MeterProvider, metrics_internal.get_meter_provider())
        if meter_provider:
            return meter_provider

    env_value = environ.get(OTEL_PYTHON_METER_PROVIDER, environ.get("OTEL_METER_PROVIDER", ""))
    if not env_value:
        return None

    if not entry_points(
        group="opentelemetry_meter_provider",
        name=env_value,
    ):
        raise Exception(f"meter provider '{env_value}' not found")

    environ[OTEL_PYTHON_METER_PROVIDER] = env_value
    meter_provider = cast(MeterProvider, _load_provider(OTEL_PYTHON_METER_PROVIDER, "meter_provider"))
    set_meter_provider(meter_provider)
    return meter_provider


def _get_logger_provider() -> Optional[LoggerProvider]:
    if logs_internal._LOGGER_PROVIDER:
        logger_provider = cast(LoggerProvider, logs_internal.get_logger_provider())
        if logger_provider:
            return logger_provider

    env_value = environ.get(OTEL_PYTHON_LOGGER_PROVIDER, environ.get("OTEL_LOGGER_PROVIDER", ""))
    if not env_value:
        return None

    if not entry_points(
        group="opentelemetry_logger_provider",
        name=env_value,
    ):
        raise Exception(f"logger provider '{env_value}' not found")

    environ[OTEL_PYTHON_LOGGER_PROVIDER] = env_value
    logger_provider = cast(LoggerProvider, _load_provider(OTEL_PYTHON_LOGGER_PROVIDER, "logger_provider"))
    set_logger_provider(logger_provider)
    return logger_provider


def _create_tracer_provider(resource: Optional[Resource] = None) -> TracerProvider:
    sampler_name = _get_sampler() or ""
    sampler = _import_sampler(sampler_name)

    id_generator_name = _get_id_generator()
    id_generator = _import_id_generator(id_generator_name)

    exporters = _get_trace_exporters()

    if not resource:
        resource = _create_resource()

    return _init_tracing(exporters=exporters, id_generator=id_generator, sampler=sampler, resource=resource)


def _create_meter_provider(resource: Optional[Resource] = None) -> MeterProvider:
    exporters = _get_metric_exporters()
    metric_readers = [metric_reader() for _, metric_reader in _get_metric_readers()]

    if not resource:
        resource = _create_resource()

    return _init_metrics(exporters=exporters, metric_readers=metric_readers, resource=resource)


def _create_logger_provider(resource: Optional[Resource] = None) -> LoggerProvider:
    exporters = _get_log_exporters()

    if not resource:
        resource = _create_resource()

    return _init_logging(exporters=exporters, resource=resource)


def _init_tracing(
    exporters: Optional[Dict[str, Type[SpanExporter]]] = None,
    span_processors: Optional[List[SpanProcessor]] = None,
    id_generator: Optional[IdGenerator] = None,
    sampler: Optional[Sampler] = None,
    resource: Optional[Resource] = None,
) -> TracerProvider:
    factory_args: Dict[str, Any] = {}
    if id_generator:
        factory_args["id_generator"] = id_generator
    if sampler:
        factory_args["sampler"] = sampler
    if resource:
        factory_args["resource"] = resource

    tracer_provider = TracerProvider(**factory_args)

    if span_processors:
        for span_processor in span_processors:
            tracer_provider.add_span_processor(span_processor)

    if exporters:
        for _, exporter_class in exporters.items():
            exporter_args: Dict[str, Any] = {}
            tracer_provider.add_span_processor(BatchSpanProcessor(exporter_class(**exporter_args)))

    set_tracer_provider(tracer_provider)
    return tracer_provider


def _init_metrics(
    exporters: Optional[Dict[str, Type[MetricExporter]]] = None,
    metric_readers: Optional[List[MetricReader]] = None,
    resource: Optional[Resource] = None,
    view: Optional[Sequence[View]] = None,
) -> MeterProvider:
    if not metric_readers:
        metric_readers = []

    if exporters:
        for _, exporter_class in exporters.items():
            exporter_args: Dict[str, Any] = {}
            metric_readers.append(PeriodicExportingMetricReader(exporter_class(**exporter_args)))

    factory_args: Dict[str, Any] = {"metric_readers": metric_readers}
    if resource:
        factory_args["resource"] = resource
    if view:
        factory_args["view"] = view

    meter_provider = MeterProvider(**factory_args)
    set_meter_provider(meter_provider)
    return meter_provider


def _init_logging(
    exporters: Optional[Dict[str, Type[LogExporter]]] = None,
    log_record_processors: Optional[List[LogRecordProcessor]] = None,
    resource: Optional[Resource] = None,
) -> LoggerProvider:
    factory_args: Dict[str, Any] = {}
    if resource:
        factory_args["resource"] = resource

    logger_provider = LoggerProvider(**factory_args)

    if log_record_processors:
        for log_record_processor in log_record_processors:
            logger_provider.add_log_record_processor(log_record_processor)

    if exporters:
        for _, exporter_class in exporters.items():
            exporter_args: Dict[str, Any] = {}
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter_class(**exporter_args)))

    set_logger_provider(logger_provider)
    return logger_provider


def _create_resource(attributes: Optional[Dict[str, AttributeValue]] = None) -> Resource:
    if attributes is None:
        attributes = {}

    return Resource.create(attributes).merge(OTELResourceDetector().detect())


def _add_meter_provider_views(meter_provider: MeterProvider) -> None:
    if not [v for v in meter_provider._sdk_config.views if v._meter_name == "tomodachi.opentelemetry"]:
        aggregation = ExplicitBucketHistogramAggregation(
            boundaries=(0, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10)
        )
        views = (
            View(
                instrument_name="http.server.duration",
                aggregation=aggregation,
                meter_name="tomodachi.opentelemetry",
            ),
            View(
                instrument_name="messaging.amazonsqs.duration",
                aggregation=aggregation,
                meter_name="tomodachi.opentelemetry",
            ),
            View(
                instrument_name="messaging.rabbitmq.duration",
                aggregation=aggregation,
                meter_name="tomodachi.opentelemetry",
            ),
            View(
                instrument_name="function.duration",
                aggregation=aggregation,
                meter_name="tomodachi.opentelemetry",
            ),
        )
        meter_provider._sdk_config.views = (*meter_provider._sdk_config.views, *views)


def _initialize_components(auto_instrumentation_version: Optional[str] = None) -> None:
    resource_attributes: Dict[str, AttributeValue] = {}
    if auto_instrumentation_version:
        resource_attributes[ResourceAttributes.TELEMETRY_AUTO_VERSION] = auto_instrumentation_version

    resource = _create_resource(resource_attributes)

    tracer_provider = _get_tracer_provider() or _create_tracer_provider(resource)  # noqa
    meter_provider = _get_meter_provider() or _create_meter_provider(resource)  # noqa
    logger_provider = _get_logger_provider() or _create_logger_provider(resource)  # noqa
    _add_meter_provider_views(meter_provider)


class OpenTelemetryConfigurator(_BaseConfigurator):
    def _configure(self, **kwargs: Any) -> None:
        try:
            _initialize_components(str(kwargs.get("auto_instrumentation_version") or ""))
        except Exception as e:

            def wrapper(exc: Exception) -> Callable:
                def __post_init_hook(*_: Any) -> None:
                    raise exc

                return __post_init_hook

            import tomodachi

            setattr(tomodachi.Service, "__post_init_hook", wrapper(e))
            raise


class OpenTelemetryDistro(BaseDistro):
    def _set_entry_keys_precedence(self) -> None:
        from pkg_resources import working_set  # type: ignore

        for item in working_set.entries:
            entry_keys = working_set.entry_keys[item]
            if "tomodachi" in entry_keys:
                entry_keys.remove("tomodachi")
                entry_keys.insert(0, "tomodachi")

    def _configure(self, **kwargs: Any) -> None:
        self._set_entry_keys_precedence()

        logging.getLogger("opentelemetry.instrumentation.auto_instrumentation._load").setLevel(logging.ERROR)

        os.environ.setdefault(OTEL_TRACES_EXPORTER, "none")
        os.environ.setdefault(OTEL_METRICS_EXPORTER, "none")
        os.environ.setdefault(OTEL_LOGS_EXPORTER, "none")
