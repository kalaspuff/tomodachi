tomodachi - a lightweight microservices framework with asyncio
==============================================================
.. image:: https://travis-ci.org/kalaspuff/tomodachi.svg?branch=master
    :target: https://travis-ci.org/kalaspuff/tomodachi
.. image:: https://img.shields.io/pypi/v/tomodachi.svg
    :target: https://pypi.python.org/pypi/tomodachi
.. image:: https://codecov.io/gh/kalaspuff/tomodachi/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/kalaspuff/tomodachi
.. image:: https://img.shields.io/pypi/pyversions/tomodachi.svg
    :target: https://pypi.python.org/pypi/tomodachi

Python 3 microservice framework using asyncio (async / await) with HTTP,
RabbitMQ / AMQP and AWS SNS+SQS support for event bus based communication.

Tomodachi is a tiny framework designed to build fast microservices listening on
HTTP or communicating over event driven message buses like RabbitMQ, AMQP,
AWS (Amazon Web Services) SNS+SQS, etc. It's designed to be extendable to make
use of any type of transport layer available.

*Tomodachi* (**友達**) *means friends – and since microservices wouldn't make
sense on their own I think they need to be friends with each other.* 😍 👬 👭 👫


How do I use this?
==================

Installation via pip 🌮
-----------------------
::

    $ pip install tomodachi


Basic HTTP based service 🌟
---------------------------
.. code:: python

    import tomodachi
    from tomodachi.transport.http import http, http_error


    @tomodachi.service
    class HttpService(object):
        name = 'http_service'

        # Request paths are specified as regex for full flexibility
        @http('GET', r'/resource/(?P<id>[^/]+?)/?')
        async def resource(self, request, id):
            # Returning a string value normally means 200 OK
            return 'id = {}'.format(id)

        @http('GET', r'/health')
        async def health_check(self, request):
            # Return can also be a tuple, dict or even an aiohttp.web.Response
            # object for more complex responses - for example if you need to
            # send byte data, set your own status code or define own headers
            return {
                'body': 'Healthy',
                'status': 200
            }

        # Specify custom 404 catch-all response
        @http_error(status_code=404)
        async def error_404(self, request):
            return 'error 404'


Run service 😎
--------------
::

    $ tomodachi run service.py


Requirements 👍
---------------
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


License 🙋
----------
Offered under the `MIT license <https://github.com/kalaspuff/tomodachi/blob/master/LICENSE>`_


Source code 🦄
--------------
The latest developer version of tomodachi is available at the GitHub repo https://github.com/kalaspuff/tomodachi


Any questions?
==============
What is the best way to run a tomodachi service?
  There is no way to tell you how to orchestrate your infrastructure. Some people may run it containerized in a Docker environment, deployed via Terraform and some may run several services on the same environment, on the same machine. There are no standards and we're not here to tell you about your best practices.

Are there any more example services?
  There are a few examples in the `examples <https://github.com/kalaspuff/tomodachi/blob/master/examples>`_ folder, including examples to publish events/messages to an AWS SNS topic and subscribe to an AWS SQS queue. There's also a similar example of how to work with pub-sub for RabbitMQ via AMQP transport protocol.

Why should I use this?
  I'm not saying you should, but I'm not saying you shouldn't. ``tomodachi`` is a perfect place to start when experimenting with your architecture or trying out a concept for a new service. It may not have all the features you desire and it may never do.

Should I run this in production?
  It's all still highly experimental and it depends on other experimental projects, so you have to be in charge here and decide for yourself. Let me know if you do however!

Who built this and why?
  My name is **Carl Oscar Aaro** and I'm a coder from Sweden. I simply wanted to learn more about asyncio and needed a constructive off-work project to experiment with – and here we are. 🎉
