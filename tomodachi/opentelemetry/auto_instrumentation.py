from os import environ
from typing import List, Union

from opentelemetry.instrumentation.auto_instrumentation._load import (
    _load_configurators,
    _load_distro,
    _load_instrumentors,
)
from opentelemetry.instrumentation.environment_variables import (
    OTEL_PYTHON_CONFIGURATOR,
    OTEL_PYTHON_DISABLED_INSTRUMENTATIONS,
    OTEL_PYTHON_DISTRO,
)
from pkg_resources import Distribution, EntryPoint, iter_entry_points

from tomodachi.opentelemetry.distro import OpenTelemetryConfigurator, OpenTelemetryDistro


def initialize() -> None:
    # use default "tomodachi" distro and configurator unless otherwise specified
    if environ.get(OTEL_PYTHON_DISTRO) is None:
        environ.setdefault(OTEL_PYTHON_DISTRO, "tomodachi")
    if environ.get(OTEL_PYTHON_CONFIGURATOR) is None:
        environ.setdefault(OTEL_PYTHON_CONFIGURATOR, "tomodachi")
    distro_value = environ.get(OTEL_PYTHON_DISTRO) or "tomodachi"
    configurator_value = environ.get(OTEL_PYTHON_CONFIGURATOR) or "tomodachi"

    # load "tomodachi" distro directly unless otherwise specified (then use standard OTEL auto loader)
    if distro_value != "tomodachi":
        distro = _load_distro()
    else:
        distro = OpenTelemetryDistro()
    distro.configure()

    # load "tomodachi" configurator directly unless otherwise specified (then use standard OTEL auto loader)
    if configurator_value != "tomodachi":
        _load_configurators()
    else:
        OpenTelemetryConfigurator().configure()

    # loads instrumentors from entry points using selected distro
    _load_instrumentors(distro)

    # auto instrument also in case "tomodachi" instrumentor plugin is missing (or tomodachi dist is not installed)
    if "tomodachi" not in [ep.name for ep in iter_entry_points("opentelemetry_instrumentor")]:
        package_to_exclude: Union[str, List[str]] = environ.get(OTEL_PYTHON_DISABLED_INSTRUMENTATIONS, [])
        if isinstance(package_to_exclude, str):
            package_to_exclude = [x.strip() for x in package_to_exclude.split(",")]

        if "tomodachi" not in package_to_exclude:
            if isinstance(distro, OpenTelemetryDistro):
                from tomodachi.opentelemetry import TomodachiInstrumentor

                if TomodachiInstrumentor not in distro._instrumentors:
                    TomodachiInstrumentor().instrument(skip_dep_check=True)
                    distro._instrumentors.add(TomodachiInstrumentor)
            else:
                distro.load_instrumentor(
                    EntryPoint("tomodachi", "tomodachi.opentelemetry", ("TomodachiInstrumentor",), dist=Distribution()),
                    skip_dep_check=True,
                )
