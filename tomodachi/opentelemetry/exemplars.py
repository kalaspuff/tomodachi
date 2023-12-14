from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from random import randint
from time import time_ns
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from opentelemetry.metrics import Instrument
from opentelemetry.sdk.metrics._internal.aggregation import (
    Aggregation,
    _Aggregation,
    _DropAggregation,
    _ExplicitBucketHistogramAggregation,
)
from opentelemetry.sdk.metrics._internal.instrument import Histogram
from opentelemetry.sdk.metrics._internal.measurement import Measurement
from opentelemetry.sdk.util.instrumentation import InstrumentationScope
from opentelemetry.trace import format_span_id, format_trace_id, get_current_span
from opentelemetry.util.types import Attributes, AttributeValue

from tomodachi.opentelemetry.environment_variables import OTEL_PYTHON_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED

# currently experimental workaround to provide exemplars to metrics in Prometheus OpenMetrics format.
# exemplar spec: https://opentelemetry.io/docs/specs/otel/metrics/sdk/#exemplar

# status of exemplars support for Python OTEL: https://github.com/open-telemetry/opentelemetry-python/issues/2407


def IS_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED() -> bool:
    return str(
        os.environ.get(OTEL_PYTHON_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED)
        or os.environ.get("OTEL_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED")
        or os.environ.get("OTEL_PYTHON_EXPORTER_PROMETHEUS_EXEMPLARS_ENABLED")
        or os.environ.get("OTEL_EXPORTER_PROMETHEUS_EXEMPLARS_ENABLED")
        or os.environ.get("IS_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED")
        or os.environ.get("TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED")
        or 0
    ).lower().strip() in ("1", "true")


@dataclass(frozen=True)
class Exemplar:
    value: Union[int, float]
    attributes: Attributes
    time_unix_nano: int
    _trace_id: int
    _span_id: int

    @property
    def trace_id(self) -> str:
        return format_trace_id(self._trace_id) or ""

    @property
    def span_id(self) -> str:
        return format_span_id(self._span_id) or ""


T = TypeVar("T", bound="BaseExemplarReservoir")


class BaseExemplarReservoir(ABC):
    _instances: Optional[
        Dict[
            Tuple[InstrumentationScope, str, frozenset[Tuple[str, AttributeValue]]],
            Union[SimpleFixedSizeExemplarReservoir, AlignedHistogramBucketExemplarReservoir],
        ]
    ] = None

    def __new__(
        cls: Type[BaseExemplarReservoir],
        *,
        measurement: Optional[Measurement] = None,
        instrument: Optional[Instrument] = None,
        instrumentation_scope: Optional[InstrumentationScope] = None,
        instrument_name: Optional[str] = None,
        aggregation: Optional[_Aggregation] = None,
        attributes: Optional[Attributes] = None,
    ) -> ExemplarReservoir:
        if cls._instances is None:
            cls._instances = {}

        if measurement:
            instrument = measurement.instrument
            attributes = measurement.attributes
        elif aggregation:
            attributes = aggregation._attributes

        if instrument and not instrumentation_scope:
            instrumentation_scope = getattr(instrument, "instrumentation_scope", None)

        if instrument and not instrument_name:
            instrument_name = getattr(instrument, "name", None) or ""

        if not instrument_name or instrumentation_scope is None:
            raise Exception("instrument or instrument_name + instrumentation_scope is required to load a reservoir")

        aggr_key = frozenset(attributes.items() if attributes is not None else {})
        key = (instrumentation_scope, instrument_name, aggr_key)

        instance: Optional[Union[SimpleFixedSizeExemplarReservoir, AlignedHistogramBucketExemplarReservoir]]
        instance = cls._instances.get(key)

        if not instance:
            if not instrument or not aggregation:
                raise Exception("instrument and aggregation is required to initialize a new reservoir")

            if isinstance(instrument, Histogram):
                instance = object.__new__(AlignedHistogramBucketExemplarReservoir)
            else:
                instance = object.__new__(SimpleFixedSizeExemplarReservoir)

            cls._instances[key] = instance
            instance._initialize(instrument, aggregation, attributes)

        return instance

    @abstractmethod
    def _initialize(self, instrument: Instrument, aggregation: _Aggregation, attributes: Attributes) -> None:
        pass


class ExemplarPool:
    max_exemplars_in_pool: int = 30
    _exemplars: List[Exemplar]

    def __init__(self) -> None:
        self._exemplars = []

    def add_exemplar(self, exemplar: Exemplar) -> None:
        if len(self._exemplars) >= self.max_exemplars_in_pool:
            self._exemplars.pop(0)
        self._exemplars.append(exemplar)

    def clear(self) -> None:
        self._exemplars.clear()


class ExemplarReservoir(BaseExemplarReservoir):
    instrument: Instrument
    aggregation: _Aggregation
    attributes: Mapping[str, AttributeValue]
    _attributes: frozenset[Tuple[str, AttributeValue]]
    _buckets: Tuple[ExemplarPool, ...]

    def _initialize(self, instrument: Instrument, aggregation: _Aggregation, attributes: Attributes) -> None:
        self.instrument = instrument
        self.aggregation = aggregation
        self.attributes = attributes or {}
        self._attributes_set = frozenset(self.attributes.items())
        self._buckets = tuple(ExemplarPool() for _ in range(self.num_buckets))

    def _offer(self, measurement: Measurement) -> Tuple[bool, int]:
        return False, 0

    def _exemplars_from_buckets(self, buckets: Iterable[ExemplarPool]) -> List[Exemplar]:
        exemplars: List[Exemplar] = []
        for bucket in buckets:
            exemplars = exemplars + bucket._exemplars
        return exemplars

    def offer(self, measurement: Measurement, time_unix_nano: int) -> None:
        span_context = get_current_span().get_span_context()

        if span_context.is_valid and span_context.trace_flags.sampled:
            may_sample_exemplar, bucket = self._offer(measurement)
            if may_sample_exemplar and bucket < self.num_buckets:
                self._buckets[bucket].add_exemplar(
                    Exemplar(
                        value=measurement.value,
                        attributes=dict((measurement.attributes or {}).items() - self._attributes_set),
                        time_unix_nano=time_unix_nano,
                        _trace_id=span_context.trace_id,
                        _span_id=span_context.span_id,
                    )
                )

    def collect(
        self,
        filter_key: Callable[[Exemplar], bool],
        sort_key: Callable[[Exemplar], Any],
        bucket: Optional[int] = None,
        limit: int = 1,
    ) -> Iterator[Exemplar]:
        return (
            exemplar
            for exemplar, _ in zip(
                sorted(
                    filter(
                        filter_key,
                        (
                            self._buckets[bucket]._exemplars
                            if bucket is not None
                            else self._exemplars_from_buckets(self._buckets)
                        ),
                    ),
                    key=sort_key,
                ),
                range(limit),
            )
        )

    def reset(self) -> None:
        pass

    @property
    def num_buckets(self) -> int:
        return 0


class SimpleFixedSizeExemplarReservoir(ExemplarReservoir):
    _num_measurements_seen: int

    def _initialize(self, instrument: Instrument, aggregation: _Aggregation, attributes: Attributes) -> None:
        self._num_measurements_seen = 0
        self._num_buckets = 1
        super()._initialize(instrument, aggregation, attributes)

    def _offer(self, measurement: Measurement) -> Tuple[bool, int]:
        self._num_measurements_seen += 1
        return (randint(0, self._num_measurements_seen - 1) == 0, 0)

    def reset(self) -> None:
        self._num_measurements_seen = 0
        self._buckets[0].clear()

    @property
    def num_buckets(self) -> int:
        return 1


class AlignedHistogramBucketExemplarReservoir(ExemplarReservoir):
    _bucket_boundaries: Sequence[float]
    _num_buckets: int

    def _initialize(self, instrument: Instrument, aggregation: _Aggregation, attributes: Attributes) -> None:
        if isinstance(aggregation, _ExplicitBucketHistogramAggregation):
            self._bucket_boundaries = aggregation._boundaries
        else:
            self._bucket_boundaries = getattr(aggregation, "_boundaries", [])
        self._num_buckets = len(self._bucket_boundaries) + 1
        super()._initialize(instrument, aggregation, attributes)

    def _offer(self, measurement: Measurement) -> Tuple[bool, int]:
        return True, self.find_histogram_bucket(measurement)

    def find_histogram_bucket(self, measurement: Measurement) -> int:
        for idx, boundary in enumerate(self._bucket_boundaries):
            if measurement.value <= boundary:
                return idx
        return len(self._bucket_boundaries)

    def reset(self) -> None:
        for bucket in self._buckets:
            if bucket._exemplars:
                exemplar = bucket._exemplars.pop()
                bucket.clear()
                bucket.add_exemplar(exemplar)

    @property
    def num_buckets(self) -> int:
        return self._num_buckets


class _ExemplarAggregation(_DropAggregation):
    def aggregate(self, measurement: Measurement) -> None:
        reservoir = ExemplarReservoir(measurement=measurement)
        reservoir.offer(measurement, time_ns())


class ExemplarAggregation(Aggregation):
    def _create_aggregation(
        self,
        instrument: Instrument,
        attributes: Attributes,
        start_time_unix_nano: int,
    ) -> _Aggregation:
        return _ExemplarAggregation(attributes)
