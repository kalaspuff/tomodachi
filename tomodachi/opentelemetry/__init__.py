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

Configuration
-------------

Exclude lists
*************
To exclude certain URLs from tracking, set the environment variable ``OTEL_PYTHON_TOMODACHI_EXCLUDED_URLS``
(or ``OTEL_PYTHON_EXCLUDED_URLS`` to cover all instrumentations) to a string of comma delimited regexes that match the
URLs.

Also values from the ``OTEL_PYTHON_AIOHTTP_EXCLUDED_URLS`` environment variable will be excluded.

For example,

::

    export OTEL_PYTHON_TOMODACHI_EXCLUDED_URLS="client/.*/info,healthcheck"

will exclude requests such as ``https://site/client/123/info`` and ``https://site/xyz/healthcheck``.

You can also pass comma delimited regexes directly to the ``instrument`` method:

.. code-block:: python

    TomodachiInstrumentor().instrument(excluded_urls="client/.*/info,healthcheck")

"""

__all__ = [
    "TomodachiInstrumentor",
]
