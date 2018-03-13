``tomodachi`` - a lightweight microservices framework with asyncio
==================================================================
  A Python 3 microservice framework using asyncio (async / await) with HTTP,
  websockets, RabbitMQ / AMQP and AWS SNS+SQS built-in support for event based
  messaging and intra-service communication.

.. image:: https://travis-ci.org/kalaspuff/tomodachi.svg?branch=master
    :target: https://travis-ci.org/kalaspuff/tomodachi
.. image:: https://img.shields.io/pypi/v/tomodachi.svg
    :target: https://pypi.python.org/pypi/tomodachi
.. image:: https://codecov.io/gh/kalaspuff/tomodachi/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/kalaspuff/tomodachi
.. image:: https://img.shields.io/pypi/pyversions/tomodachi.svg
    :target: https://pypi.python.org/pypi/tomodachi

Tomodachi is a tiny framework designed to build fast microservices listening on
HTTP or communicating over event driven message buses like RabbitMQ, AMQP,
AWS (Amazon Web Services) SNS+SQS, etc. It's designed to be extendable to make
use of any type of transport layer available.

*Tomodachi* (**友達**) *means friends – a suitable name for microservices working
together.* 😻 👬 👭 👫 😻


| **Please note: this is a work in progress.**
``tomodachi`` is still a highly experimental project with an unregular release
schedule.


Usage
-----
``tomodachi`` is invoked via command line interface.

.. code::

    Usage: tomodachi <subcommand> [options] [args]

    Options:
      -h, --help             show this help message and exit
      -v, --version          print tomodachi version
      --dependency-versions  print versions of dependencies

    Available subcommands:
      run <service ...> [-c <config-file ...>] [--production]
      -c, --config <files>   use json configuration files
      -l, --log <level>      specify log level
      --production           disable restart on file changes


How do I use this?
------------------
Preferrably installation should be done via ``pip`` to get the cli alias set
up automatically. Locally it is recommended to install ``tomodachi`` into a
virtualenv to avoid random packages into your base site-packages.

.. code:: bash

    local ~$ pip install tomodachi


Basic HTTP based service 🌟
^^^^^^^^^^^^^^^^^^^^^^^^^^^
*Code for a simple service which would service data over HTTP.*

.. code:: python

    import tomodachi

    @tomodachi.service
    class Service(object):
        name = 'example'

        # Request paths are specified as regex for full flexibility
        @tomodachi.http('GET', r'/resource/(?P<id>[^/]+?)/?')
        async def resource(self, request, id):
            # Returning a string value normally means 200 OK
            return 'id = {}'.format(id)

        @tomodachi.http('GET', r'/health')
        async def health_check(self, request):
            # Return can also be a tuple, dict or even an aiohttp.web.Response
            # object for more complex responses - for example if you need to
            # send byte data, set your own status code or define own headers
            return {
                'body': 'Healthy',
                'status': 200
            }

        # Specify custom 404 catch-all response
        @tomodachi.http_error(status_code=404)
        async def error_404(self, request):
            return 'error 404'


RabbitMQ or AWS SNS/SQS event based messaging service 📡
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
*Example of a service that would invoke a function when messages are published on a topic exchange.*

.. code:: python

    import tomodachi

    @tomodachi.service
    class Service(object):
        name = 'example'

        # A route / topic on which the service will subscribe to via AMQP (or AWS SNS/SQS)
        @tomodachi.amqp('example.topic')
        async def example_topic_func(self, message):
            # Received message, sending same message as response on another route / topic
            await tomodachi.amqp_publish(self, message, routing_key='example.response')


Run the service 😎
------------------
.. code:: bash

    # if installed via pip
    $ tomodachi run service.py

    # if cloned from repo
    $ python tomodachi.py run service.py


.. code:: bash

    tomodachi/X.X.XX
    October 02, 2017 - 13:38:00,481516
    Quit services with <ctrl+c>.
    2017-10-02 13:38:01,234 (services.service): Initializing service "example" [id: <uuid>]
    2017-10-02 13:38:01,248 (transport.http): Listening [http] on http://127.0.0.1:9700/
    2017-10-02 13:38:01,248 (services.service): Started service "example" [id: <uuid>]


*HTTP service acts like a normal web server.*

.. code:: bash

    $ curl -v "http://127.0.0.1:9700/resource/1234"
    < HTTP/1.1 200 OK
    < Content-Type: text/plain; charset=utf-8
    < Server: tomodachi
    < Content-Length: 9
    < Date: Mon, 02 Oct 2017 13:38:02 GMT
    id = 1234


Requirements 👍
---------------
* Python_ 3.5.3+, 3.6+, 3.7+
* aiohttp_
* aiobotocore_
* aioamqp_
* ujson_
* uvloop_

.. _Python: https://www.python.org
.. _asyncio: http://docs.python.org/3.5/library/asyncio.html
.. _aiohttp: https://github.com/aio-libs/aiohttp
.. _aiobotocore: https://github.com/aio-libs/aiobotocore
.. _aioamqp: https://github.com/Polyconseil/aioamqp
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
