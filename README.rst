.. image:: https://travis-ci.org/kalaspuff/tomodachi.svg?branch=master
    :target: https://travis-ci.org/kalaspuff/tomodachi
.. image:: https://img.shields.io/pypi/v/tomodachi.svg
    :target: https://pypi.python.org/pypi/tomodachi
.. image:: https://img.shields.io/pypi/pyversions/tomodachi.svg
    :target: https://pypi.python.org/pypi/tomodachi


tomodachi
=========

Python 3 microservice framework using asyncio (async / await) with HTTP,
RabbitMQ / AMQP and AWS SNS+SQS support for event bus based communication.

Tomodachi is a tiny framework designed to build fast microservices listening on
HTTP or communicating over event driven message buses like RabbitMQ, AMQP,
AWS (Amazon Web Services) SNS+SQS, etc. It's designed to be extendable to make
use of any type of transport layer available.

Tomodachi (友達) means friends - microservices wouldn't make sense on their own
and need to have a friend to communicate. 😍 👬 👭 👫


Installation via pip
--------------------
::

    $ pip install tomodachi


Basic HTTP based service
------------------------
.. code:: python

    from tomodachi.transport.http import http, http_error


    class HttpService(object):
        name = 'http_service'

        # Request paths are specified as regex for full flexibility
        @http('GET', r'/resource/(?P<id>[^/]+?)/?')
        async def resource(self, request, id):
            # Returning a string value normally means 200 OK
            return 'id = {}'.format(id)

        @http('GET', r'/health')
        async def health_check(self, request):
            # Return can also be a tuple / dict for more complex responses
            # For example if you need to set your own status code or headers
            return {
                'body': 'Healthy',
                'status': 200
            }

        # Specify custom 404 catch-all response
        @http_error(status_code=404)
        async def error_404(self, request):
            return 'error 404'


Run service
-----------
::

    $ tomodachi run service.py


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


License
-------
Offered under the `MIT license <https://github.com/kalaspuff/tomodachi/blob/master/LICENSE>`_


Source code
-----------
The latest developer version of tomodachi is available at the GitHub repo https://github.com/kalaspuff/tomodachi
