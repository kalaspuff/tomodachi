from tomodachi.opentelemetry.instrumentation import TomodachiInstrumentor

"""
Usage
-----

.. code-block:: python

    import tomodachi
    from tomodachi.opentelemetry import TomodachiInstrumentor

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
