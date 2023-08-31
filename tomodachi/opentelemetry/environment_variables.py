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

OTEL_PYTHON_TOMODACHI_PROMETHEUS_ADDRESS = "OTEL_PYTHON_TOMODACHI_PROMETHEUS_ADDRESS"
"""
.. envvar:: OTEL_PYTHON_TOMODACHI_PROMETHEUS_ADDRESS

The :envvar:`OTEL_PYTHON_TOMODACHI_PROMETHEUS_ADDRESS` specifies the address on which the
"tomodachi_prometheus" meter provider will listen on.
Default: "localhost"
"""

OTEL_PYTHON_TOMODACHI_PROMETHEUS_PORT = "OTEL_PYTHON_TOMODACHI_PROMETHEUS_PORT"
"""
.. envvar:: OTEL_PYTHON_TOMODACHI_PROMETHEUS_PORT

The :envvar:`OTEL_PYTHON_TOMODACHI_PROMETHEUS_PORT` specifies the port on which the
"tomodachi_prometheus" meter provider will listen on.
Default: 9464
"""

OTEL_PYTHON_TOMODACHI_PROMETHEUS_NAMESPACE_PREFIX = "OTEL_PYTHON_TOMODACHI_PROMETHEUS_NAMESPACE_PREFIX"
"""
.. envvar:: OTEL_PYTHON_TOMODACHI_PROMETHEUS_NAMESPACE_PREFIX

The :envvar:`OTEL_PYTHON_TOMODACHI_PROMETHEUS_NAMESPACE_PREFIX` configures the exporter to prefix metrics
with the given namespace. Metadata metrics such as target_info and otel_scope_info are not prefixed since
these have special behavior based on their name.
Default: ""
"""

OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO = "OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO"
"""
.. envvar:: OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO

The :envvar:`OTEL_PYTHON_TOMODACHI_PROMETHEUS_INCLUDE_SCOPE_INFO` if set to True will export a Prometheus
info metric "otel_scope_info" with labels "otel_scope_name" and "otel_scope_version", as well as the labels
are also added to all metric points. Additional details are available `in the specification
<https://opentelemetry.io/docs/specs/otel/compatibility/prometheus_and_openmetrics/#instrumentation-scope-1`__.
Default: True
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

OTEL_PYTHON_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED = "OTEL_PYTHON_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED"
"""
.. envvar:: OTEL_PYTHON_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED

The :envvar:`OTEL_PYTHON_TOMODACHI_PROMETHEUS_EXEMPLARS_ENABLED` if set to True will include exemplars in
the Prometheus output when queried with the OpenMetrics accept header. Use of these exemplars with the
Prometheus meter provider are currently experimental.
Default: False
"""
