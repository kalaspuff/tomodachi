``tomodachi`` - a lightweight microservices library with asyncio
================================================================
  A Python 3 microservice library / framework using asyncio (async / await) with
  HTTP, websockets, RabbitMQ / AMQP and AWS SNS+SQS built-in support for event based
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

*Tomodachi* [**友達**] *means friends – a suitable name for microservices working
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


.. image:: https://raw.githubusercontent.com/kalaspuff/tomodachi/master/docs/assets/microservice-in-30-seconds-white.gif


How do I use this? (simple install using ``pip``)
-------------------------------------------------
Preferrably installation should be done via ``pip`` to get the cli alias set
up automatically. Locally it is recommended to install ``tomodachi`` into a
virtualenv to avoid random packages into your base site-packages.

.. code:: bash

    local ~$ pip install tomodachi


Getting started 🏃
^^^^^^^^^^^^^^^^^^
*Start off with* ``import tomodachi`` *and add a class decorated with*
``@tomodachi.service`` *and/or extended from the* ``tomodachi.Service`` *class.
Name your service class and then just add functions and triggers for how to
invoke  them, either by HTTP requests, event messages or by timestamps /
intervals.*



Basic HTTP based service 🌟
^^^^^^^^^^^^^^^^^^^^^^^^^^^
*Code for a simple service which would service data over HTTP.*

.. code:: python

    import tomodachi


    @tomodachi.service
    class Service(tomodachi.Service):
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
    class Service(tomodachi.Service):
        name = 'example'

        # A route / topic on which the service will subscribe to via AMQP (or AWS SNS/SQS)
        @tomodachi.amqp('example.topic')
        async def example_topic_func(self, message):
            # Received message, sending same message as response on another route / topic
            await tomodachi.amqp_publish(self, message, routing_key='example.response')


Scheduling, inter-communication between services, etc. ⚡️
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
There are other examples available with examples of how to use services with self-invoking
methods called on a specified interval or at specific times / days. Inter-communication
between different services may be established using a pub-sub type with messages over AMQP
or AWS SNS+SQS which is natively supported.


Run the service 😎
------------------
.. code:: bash

    # cli alias is set up if installed via pip
    local ~/code/service$ tomodachi run service.py

    # example if cloned from repo
    local ~/code/tomodachi$ python tomodachi.py run example/http_simple_service.py


*Defaults to output information on stdout.*

.. code:: bash

    local ~/code/service$ tomodachi run service.py

    tomodachi/X.X.XX
    October 02, 2017 - 13:38:00,481516
    Quit services with <ctrl+c>.
    2017-10-02 13:38:01,234 (services.service): Initializing service "example" [id: <uuid>]
    2017-10-02 13:38:01,248 (transport.http): Listening [http] on http://127.0.0.1:9700/
    2017-10-02 13:38:01,248 (services.service): Started service "example" [id: <uuid>]


*HTTP service acts like a normal web server.*

.. code:: bash

    local ~$ curl -v "http://127.0.0.1:9700/resource/1234"

    < HTTP/1.1 200 OK
    < Content-Type: text/plain; charset=utf-8
    < Server: tomodachi
    < Content-Length: 9
    < Date: Mon, 02 Oct 2017 13:38:02 GMT
    id = 1234


Example of ``tomodachi`` service containerized in Docker 🐳
-----------------------------------------------------------
Great ways to run microservices are either to run them in Docker or running them serverless.
Here's an example of getting a tomodachi service up and running in Docker in no-time. The
base-image (``kalaspuff/python-nginx-proxy``) also sets up ``nginx`` and proxies requests from
port 80 to the service backend on 8080.

We're building a container using just two small files, the ``Dockerfile`` and the actual code
for the microservice, ``service.py``.

**Dockerfile**

.. code:: dockerfile

    FROM kalaspuff/python-nginx-proxy:1.1.0
    WORKDIR /
    RUN apt-get -y update \
        && apt-get install -y build-essential=12.3 \
        && pip install tomodachi \
        && apt-get purge -y --auto-remove build-essential \
        && apt-get clean autoclean \
        && apt-get autoremove -y \
        && rm -rf /var/lib/{apt,dpkg,cache,log}/
    RUN mkdir /app
    WORKDIR /app
    ADD service.py .
    CMD tomodachi run service.py --production

**service.py**

.. code:: python

    import tomodachi


    @tomodachi.service
    class Service(tomodachi.Service):
        name = 'example'
        options = {
            'http': {
                'port': 8080
            }
        }

        @tomodachi.http('GET', r'/')
        async def index_endpoint(self, request):
            return 'friends forever!'

*Building and running the container, forwarding host's port 31337 to port 80.*

.. code:: bash

    local ~/code/service$ docker build . -t tomodachi-microservice

.. code:: bash

    local ~/code/service$ docker run -ti -p 31337:80 tomodachi-microservice
    2017-10-02 13:38:01,234 (services.service): Initializing service "example" [id: <uuid>]
    2017-10-02 13:38:01,248 (transport.http): Listening [http] on http://127.0.0.1:8080/
    2017-10-02 13:38:01,248 (services.service): Started service "example" [id: <uuid>]

*Making requests to the running container.*

.. code:: bash

    local ~$ curl http://127.0.0.1:31337/
    friends forever!


Nothing more nothing less. It's actually as easy as that.


Requirements 👍
---------------
* Python_ 3.5.3+, 3.6+
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
The latest developer version of ``tomodachi`` is available at the GitHub repo https://github.com/kalaspuff/tomodachi


Any questions?
==============
What is the best way to run a ``tomodachi`` service?
  There is no way to tell you how to orchestrate your infrastructure. Some people may run it containerized in a Docker environment, deployed via Terraform / Nomad / Kubernetes and some may run several services on the same environment, on the same machine. There may be best practices but theres no way telling you how to orchestrate your application environment.

  Personally I would currently go for a Dockerized environment with nginx proxy in front of the service to handle all the weirdness of the web, TLS, black magic and improved upgrades for WebSockets. Take a look at my `kalaspuff/docker-python-nginx-proxy <https://github.com/kalaspuff/docker-python-nginx-proxy>`_ base-image to get your code up and running within minutes.

Are there any more example services?
  There are a few examples in the `examples <https://github.com/kalaspuff/tomodachi/blob/master/examples>`_ folder, including using ``tomodachi`` in an `example Docker environment <https://github.com/kalaspuff/tomodachi/tree/master/examples/docker_examples/http_service>`_ with or without docker-compose, there are examples to publish events/messages to an AWS SNS topic and subscribe to an AWS SQS queue. There's also a similar example of how to work with pub-sub for RabbitMQ via AMQP transport protocol.

Why should I use this?
  ``tomodachi`` is a perfect place to start when experimenting with your architecture or trying out a concept for a new service. It may not have all the features you desire and it may never do, but I believe it's great for bootstrapping microservices in async Python.

Should I run this in production?
  Yes? No? There are some projects that already have live versions in production. The library is provided as is with an unregular release schedule. It's all still highly experimental and it depends on other experimental projects, so you have to be in charge here and decide for yourself. Let me know if you do however!

  Another good idea is to drop in Sentry or other exception debugging solutions, for if your invoked functions would raise unhandled exceptions.

Who built this and why?
  My name is **Carl Oscar Aaro** [`@kalaspuff <https://github.com/kalaspuff>`_] and I'm a coder from Sweden. I simply wanted to learn more about asyncio and needed a constructive off-work project to experiment with – and here we are. Nowadays I use ``tomodachi`` as a base for many smaller projects where I just want to be able to focus on the application itself, while still having the power of building distributed systems. 🎉


* https://github.com/kalaspuff
* https://www.linkedin.com/in/carloscaraaro/
