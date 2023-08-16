from tomodachi.telemetry.instrumentation import TomodachiInstrumentor
from tomodachi.telemetry.package import _instruments

"""
Usage
-----

.. code-block:: python

    import tomodachi
    from tomodachi.telemetry import TomodachiInstrumentor

    TomodachiInstrumentor().instrument()

    class Service(tomodachi.Service):
        name = "example"

        @tomodachi.http(GET, r"/example")
        async def example(self, request):
            return 200, "hello world"

"""

__all__ = [
    "TomodachiInstrumentor",
    "_instruments",
]
