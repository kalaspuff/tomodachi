import os
import sys

if sys.argv and sys.argv[0].rsplit(os.sep, 1)[-1] == "opentelemetry-instrument":
    # this is a hacky way of setting the default distro and configurator used during auto instrumentation.
    # see ".../site-packages/opentelemetry/instrumentation/auto_instrumentation/__init__.py"
    for key in ("OTEL_PYTHON_DISTRO", "OTEL_PYTHON_CONFIGURATOR"):
        if not os.environ.get(key):
            os.environ.setdefault(key, "tomodachi")


OTEL_PYTHON_TOMODACHI_EXCLUDED_URLS = "OTEL_PYTHON_TOMODACHI_EXCLUDED_URLS"
"""
.. envvar:: OTEL_PYTHON_TOMODACHI_EXCLUDED_URLS

The :envvar:`OTEL_PYTHON_TOMODACHI_EXCLUDED_URLS` is used to define regex patterns of HTTP URLs that should be
excluded from instrumentation.
Default: ""
"""

OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS = "OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS"
"""
.. envvar:: OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS

The :envvar:`OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_ADDRESS` specifies the address on which the
"tomodachi_prometheus" meter provider will listen on.
Default: "localhost"
"""

OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_PORT = "OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_PORT"
"""
.. envvar:: OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_PORT

The :envvar:`OTEL_PYTHON_TOMODACHI_PROMETHEUS_METER_PROVIDER_PORT` specifies the port on which the
"tomodachi_prometheus" meter provider will listen on.
Default: 9464
"""

OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO = "OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO"
"""
.. envvar:: OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO

The :envvar:`OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO` if set to True will export a Prometheus
info metric "otel_scope_info" with labels "otel_scope_name" and "otel_scope_version", as well as the labels
are also added to all metric points. Additional details are available `in the specification
<https://opentelemetry.io/docs/specs/otel/compatibility/prometheus_and_openmetrics/#instrumentation-scope-1`__.
Default: False
"""

OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_TARGET_INFO = "OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_TARGET_INFO"
"""
.. envvar:: OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_TARGET_INFO

The :envvar:`OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_TARGET_INFO` if set to True will export a Prometheus
info metric "target_info" which includes the labels "job" and "instance", describing the service.namespace,
service.name and service.instance.id resource attributes. These labels will also be added to all metric points.
Additional details are available `in the specification
<https://opentelemetry.io/docs/specs/otel/compatibility/prometheus_and_openmetrics/#resource-attributes-1`__.
Default: True
"""
