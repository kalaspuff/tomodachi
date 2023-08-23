import logging
import os
from typing import Any

from opentelemetry.environment_variables import OTEL_METRICS_EXPORTER, OTEL_TRACES_EXPORTER
from opentelemetry.instrumentation.distro import BaseDistro
from opentelemetry.sdk._configuration import _OTelSDKConfigurator


class OpenTelemetryConfigurator(_OTelSDKConfigurator):
    pass


class OpenTelemetryDistro(BaseDistro):
    """
    The OpenTelemetry provided Distro configures a default set of
    configuration out of the box.
    """

    def _configure(self, **kwargs: Any) -> None:
        from pkg_resources import working_set

        for item in working_set.entries:
            entry_keys = working_set.entry_keys[item]
            if "tomodachi" in entry_keys:
                entry_keys.remove("tomodachi")
                entry_keys.insert(0, "tomodachi")

        logging.getLogger("opentelemetry.instrumentation.auto_instrumentation._load").setLevel(logging.ERROR)
        os.environ.setdefault(OTEL_TRACES_EXPORTER, "console")
        os.environ.setdefault(OTEL_METRICS_EXPORTER, "console")
