tomodachi
===========

Python 3 microservice framework using asyncio with HTTP, RabbitMQ / AMQP and AWS SNS+SQS support for event bus based communication.


Install
-------
::

    $ pip install tomodachi


Basic HTTP based service
-------------
.. code:: python

    from tomodachi.transport.http import http, http_error


    class HttpService(object):
        name = 'http_service'

        # Request paths are specified as regex for full flexibility
        @http('GET', r'/resource/(?P<id>[^/]+?)/?')
        async def resource(self, request, id):
            # Return can also be a tuple / dict for more complex responses
            # String return value = 200 OK
            return 'id = {}'.format(id)

        # Specify custom 404 response
        @http_error(status_code=404)
        async def error_404(self, request):
            return 'error 404'


Run Service
-----------
::

    $ tomodachi run service.py
    # service will spin up

Requirements
------------
* Python_ 3.5+
* aiohttp_
* aiobotocore_
* ujson_
* uvloop_

.. _Python: https://www.python.org
.. _asyncio: http://docs.python.org/3.5/library/asyncio.html
.. _aiobotocore: https://github.com/aio-libs/aiobotocore
.. _aiohttp: https://github.com/aio-libs/aiohttp
.. _ujson: https://github.com/esnme/ultrajson
.. _uvloop: https://github.com/MagicStack/uvloop
