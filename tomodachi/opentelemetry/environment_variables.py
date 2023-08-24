import os

from opentelemetry.instrumentation.environment_variables import OTEL_PYTHON_CONFIGURATOR as _OTEL_PYTHON_CONFIGURATOR
from opentelemetry.instrumentation.environment_variables import OTEL_PYTHON_DISTRO as _OTEL_PYTHON_DISTRO

if os.environ.get(_OTEL_PYTHON_DISTRO) is None:
    os.environ.setdefault(_OTEL_PYTHON_DISTRO, "tomodachi")

if os.environ.get(_OTEL_PYTHON_CONFIGURATOR) is None:
    os.environ.setdefault(_OTEL_PYTHON_CONFIGURATOR, "tomodachi")

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
