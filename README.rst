``tomodachi`` - a lightweight microservices library on Python asyncio
=====================================================================
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


Usage
-----
``tomodachi`` is invoked via command line interface.

.. code::

    Usage: tomodachi <command> [options] [arguments]

    Options:
      -h, --help                                Show this help message and exit
      -v, --version                             Print tomodachi version
      --dependency-versions                     Print versions of dependencies

    Available commands:
      ---
      Command: run
      Starts service(s) defined in the .py files specified as <service> argument(s)

      $ tomodachi run <service ...> [-c <config-file ...>] [--production]
      | --loop [auto|asyncio|uvloop]            Event loop implementation [asyncio]
      | --production                            Disable restart on file changes
      | -c, --config <files>                    Use configuration from JSON files
      | -l, --log <level>, --log-level <level>  Specify log level


.. image:: https://raw.githubusercontent.com/kalaspuff/tomodachi/master/docs/assets/microservice-in-30-seconds-white.gif

- `Installation <#how-do-i-use-this-simple-install-using-pip>`_

- `Getting started / example services <#getting-started->`_

- `Running microservices in Docker <#example-of-tomodachi-service-containerized-in-docker->`_

- `Defining endpoints <#available-built-ins-used-as-endpoints->`_

  - `HTTP endpoints <#http-endpoints>`_

  - `AWS SNS+SQS messaging <#aws-snssqs-messaging>`_

  - `AMQP / RabbitMQ messaging <#amqp-messaging-rabbitmq>`_

  - `Scheduled functions <#scheduled-functions--cron>`_

- `Additional configuration options <#additional-configuration-options->`_

- `Requirements <#requirements->`_

- `Questions <#any-questions>`_

- `Contributions <#contributions>`_


| **Please note: this library is a work in progress.**

``tomodachi`` is still an experimental project with an unregular release
schedule. Before the package is available as a 1.0.0 release, note that there
may be breaking changes between 0.x versions.


How do I use this? (simple install using ``pip``)
-------------------------------------------------
Installation could as always be done via ``pip`` to get the cli alias set
up automatically. Unless running development code within Docker, install
``tomodachi`` into a virtualenv to avoid cluttering. When developing
microservices for real it's however highly recommended to use
containerization such as Docker.

.. code:: bash

    local ~$ pip install tomodachi


Getting started 🏃
^^^^^^^^^^^^^^^^^^
*Start off with* ``import tomodachi`` *and add a service class extended from
the* ``tomodachi.Service`` *class. Name your service class and then just add
functions and triggers for how to invoke them, either by HTTP requests,
pub/sub event messages or by timestamps / intervals.*



Basic HTTP based service 🌟
^^^^^^^^^^^^^^^^^^^^^^^^^^^
*Code for a simple service which would service data over HTTP.*

.. code:: python

    import tomodachi


    class Service(tomodachi.Service):
        name = "example"

        # Request paths are specified as regex for full flexibility
        @tomodachi.http("GET", r"/resource/(?P<id>[^/]+?)/?")
        async def resource(self, request, id):
            # Returning a string value normally means 200 OK
            return f"id = {id}"

        @tomodachi.http("GET", r"/health")
        async def health_check(self, request):
            # Return can also be a tuple, dict or even an aiohttp.web.Response
            # object for more complex responses - for example if you need to
            # send byte data, set your own status code or define own headers
            return {
                "body": "Healthy",
                "status": 200,
            }

        # Specify custom 404 catch-all response
        @tomodachi.http_error(status_code=404)
        async def error_404(self, request):
            return "error 404"


RabbitMQ or AWS SNS+SQS event based messaging service 📡
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
*Example of a service that would invoke a function when messages are published on an AMQP topic exchange.*

.. code:: python

    import tomodachi


    class Service(tomodachi.Service):
        name = "amqp-example"

        # A route / topic on which the service will subscribe to via RabbitMQ / AMQP
        @tomodachi.amqp("example.topic")
        async def example_func(self, message):
            # Received message, fordarding the same message as response on another route / topic
            await tomodachi.amqp_publish(self, message, routing_key="example.response")

*Example of a service using AWS SNS+SQS managed pub/sub messaging. AWS SNS and AWS SQS together features
managed message queues for microservices, distributed systems, and serverless applications. This makes
it great to use for ``tomodachi`` powered Python microservices in a distributed architecture hosted on AWS,
for example in Docker on AWS ECS or AWS EKS using Kubernetes.*

.. code:: python

    import tomodachi


    class Service(tomodachi.Service):
        name = "aws-example"

        # Using the @tomodachi.aws_sns_sqs decorator to make the service create an AWS SNS topic,
        # an AWS SQS queue and to make a subscription from the topic to the queue as well as start
        # receive messages from the queue using SQS.ReceiveMessages.
        @tomodachi.aws_sns_sqs("example-topic", queue_name="example-queue")
        async def example_func(self, message):
            # Received message, forwarding the same message as response on another topic
            await tomodachi.aws_sns_sqs_publish(self, message, topic="another-example-topic")



Scheduling, inter-communication between services, etc. ⚡️
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
There are other examples available with code of how to use services with self-invoking
methods called on a specified interval or at specific times / days, as well as additional examples
for inter-communication pub/sub between different services on both AMQP or AWS SNS+SQS as shown
above. See more at the `examples folder <https://github.com/kalaspuff/tomodachi/blob/master/examples/>`_.


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

    ---
    Starting tomodachi services (pid: 1) ...
    * service.py

    Current version: tomodachi x.x.xx on Python 3.x.x
    Event loop implementation: asyncio
    Local time: October 04, 2020 - 13:38:01,201509 UTC
    Timestamp in UTC: 2020-10-04T13:38:01.201509Z

    File watcher is active - code changes will automatically restart services
    Quit running services with <ctrl+c>

    2020-10-04 13:38:01,234 (services.service): Initializing service "example" [id: <uuid>]
    2020-10-04 13:38:01,248 (transport.http): Listening [http] on http://127.0.0.1:9700/
    2020-10-04 13:38:01,248 (services.service): Started service "example" [id: <uuid>]


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
Great ways to run microservices are usually to run them in containers like Docker, for example
in a Kubernetes cluster or running them completely serverless. Here's an example of getting a
``tomodachi`` service up and running in Docker in no-time.

We're building a Docker image using just two small files, the ``Dockerfile`` and the actual code
for the microservice, ``service.py``. In reality a service is probably not quite this small,
but to just get started and show how simple it could be.

**Dockerfile**

.. code:: dockerfile

    FROM python:3.8-slim
    RUN pip install tomodachi
    RUN mkdir /app
    WORKDIR /app
    COPY service.py .
    ENV PYTHONUNBUFFERED=1
    CMD ["tomodachi", "run", "service.py", "--production"]

**service.py**

.. code:: python

    import json

    import tomodachi


    class Service(tomodachi.Service):
        name = "example"
        options = {
            "http": {
                "port": 80,
                "content_type": "application/json; charset=utf-8"
            }
        }

        _healthy = True

        @tomodachi.http("GET", r"/")
        async def index_endpoint(self, request):
            return json.dumps({
                "data": "hello world!",
                "execution_context": tomodachi.get_execution_context(),
            })

        @tomodachi.http("GET", r"/health/?", ignore_logging=True)
        async def health_check(self, request):
            if self._healthy:
                return 200, json.dumps({"status": "healthy"})
            else:
                return 503, json.dumps({"status": "not healthy"})

        @tomodachi.http_error(status_code=400)
        async def error_400(self, request):
            return json.dumps({"error": "bad-request"})

        @tomodachi.http_error(status_code=404)
        async def error_404(self, request):
            return json.dumps({"error": "not-found"})

        @tomodachi.http_error(status_code=405)
        async def error_405(self, request):
            return json.dumps({"error": "method-not-allowed"})

*Building and running the container, forwarding host's port 31337 to port 80.*

.. code:: bash

    local ~/code/service$ docker build . -t tomodachi-microservice

.. code:: bash

    local ~/code/service$ docker run -ti -p 31337:80 tomodachi-microservice
    2020-10-04 13:38:01,234 (services.service): Initializing service "example" [id: <uuid>]
    2020-10-04 13:38:01,248 (transport.http): Listening [http] on http://127.0.0.1:80/
    2020-10-04 13:38:01,248 (services.service): Started service "example" [id: <uuid>]

*Making requests to the running container.*

.. code:: bash

    local ~$ curl http://127.0.0.1:31337/ | jq
    {
      "data": "hello world!",
      "execution_context": {
        "tomodachi_version": "x.x.xx",
        "python_version": "3.x.x",
        "system_platform": "Linux",
        "process_id": 1,
        "init_timestamp": "2020-10-04T13:38:01.201509Z",
        "event_loop": "asyncio",
        "http_enabled": true,
        "http_current_tasks": 1,
        "http_total_tasks": 1,
        "aiohttp_version": "x.x.xx"
      }
    }

    local ~$ curl http://127.0.0.1:31337/health -i
    HTTP/1.1 200 OK
    Content-Type: application/json; charset=utf-8
    Server: tomodachi
    Content-Length: 21
    Date: Sun, 04 Oct 2020 13:40:44 GMT

    {"status": "healthy"}

    local ~$ curl http://127.0.0.1:31337/no-route -i
    HTTP/1.1 404 Not Found
    Content-Type: application/json; charset=utf-8
    Server: tomodachi
    Content-Length: 22
    Date: Sun, 04 Oct 2020 13:41:18 GMT

    {"error": "not-found"}


It's actually as easy as that.


Available built-ins used as endpoints 🚀
----------------------------------------
There are several built-in ways to invoke your microservice methods in which the most common ones are either directly via HTTP or via event based messaging (for example AMQP or AWS SNS+SQS). Here's a list of the currently available built-ins you may use to decorate your service functions.
Here's a short run-down of the available decorators.

HTTP endpoints:
^^^^^^^^^^^^^^^
``@tomodachi.http(method, url, ignore_logging=[200])``
  Sets up an **HTTP endpoint** for the specified ``method`` (``GET``, ``PUT``, ``POST``, ``DELETE``) on the regexp ``url``.
  Optionally specify ``ignore_logging`` as a dict or tuple containing the status codes you do not wish to log the access of. Can also be set to ``True`` to ignore everything except status code 500.

``@tomodachi.http_static(path, url)``
  Sets up an **HTTP endpoint for static content** available as ``GET`` / ``HEAD`` from the ``path`` on disk on the base regexp ``url``.

``@tomodachi.websocket(url)``
  Sets up a **websocket endpoint** on the regexp ``url``. The invoked function is called upon websocket connection and should return a two value tuple containing callables for a function receiving frames (first callable) and a function called on websocket close (second callable). The passed arguments to the function beside the class object is first the ``websocket`` response connection which can be used to send frames to the client, and optionally also the ``request`` object.

``@tomodachi.http_error(status_code)``
  A function which will be called if the **HTTP request would result in a 4XX** ``status_code``. You may use this for example to set up a custom handler on "404 Not Found" or "403 Forbidden" responses.


AWS SNS+SQS messaging:
^^^^^^^^^^^^^^^^^^^^^^
``@tomodachi.aws_sns_sqs(topic, competing=True, queue_name=None, filter_policy=None, **kwargs)``
  This would set up an **AWS SQS queue**, subscribing to messages on the **AWS SNS topic** ``topic``, whereafter it will start consuming messages from the queue.

  The ``competing`` value is used when the same queue name should be used for several services of the same type and thus "compete" for who should consume the message. Since ``tomodachi`` version 0.19.x this value has a changed default value and will now default to ``True`` as this is the most likely use-case for pub/sub in distributed architectures.

  Unless ``queue_name`` is specified an auto generated queue name will be used. Additional prefixes to both ``topic`` and ``queue_name`` can be assigned by setting the ``options.aws_sns_sqs.topic_prefix`` and ``options.aws_sns_sqs.queue_name_prefix`` dict values.

  The ``filter_policy`` value of specified as a keyword argument will be applied on the SNS subscription (for the specified topic and queue) as the ``"FilterPolicy`` attribute. This will apply a filter on SNS messages using the chosen "message attributes" and/or their values specified in the filter. Example: A filter policy value of ``{"event": ["order_paid"], "currency": ["EUR", "USD"]}`` would set up the SNS subscription to receive messages on the topic only where the message attribute ``"event"`` is ``"order_paid"`` and the ``"currency"`` value is either ``"EUR"`` or ``"USD"``.

  If ``filter_policy`` is not specified as an argument (default), the queue will receive messages on the topic as per already specified if using an existing subscription, or receive all messages on the topic if a new subscription is set up (default). Changing the ``filter_policy`` on an existing subscription may take several minutes to propagate. Read more about the filter policy format on AWS. https://docs.aws.amazon.com/sns/latest/dg/sns-subscription-filter-policies.html

  Related to the above mentioned filter policy, the ``aws_sns_sqs_publish`` function (which is used for publishing messages) can specify "message attributes" using the ``message_attributes`` keyword argument. Values should be specified as a simple ``dict`` with keys and values. Example: ``{"event": "order_paid", "paid_amount": 100, "currency": "EUR"}``.

  Depending on the service ``message_envelope`` (previously named ``message_protocol``) attribute if used, parts of the enveloped data would be distributed to different keyword arguments of the decorated function. It's usually safe to just use ``data`` as an argument. You can also specify a specific ``message_envelope`` value as a keyword argument to the decorator for specifying a specific enveloping method to use instead of the global one set for the service.

  If you're utilizing ``from tomodachi.envelope import ProtobufBase`` and using ``ProtobufBase`` as the specified service ``message_envelope`` you may also pass a keyword argument ``proto_class`` into the decorator, describing the protobuf (Protocol Buffers) generated Python class to use for decoding incoming messages. Custom enveloping classes can be built to fit your existing architecture or for even more control of tracing and shared metadata between services.

AMQP messaging (RabbitMQ):
^^^^^^^^^^^^^^^^^^^^^^^^^^
``@tomodachi.amqp(routing_key, exchange_name="amq.topic", competing=True, queue_name=None, **kwargs)``
  Sets up the method to be called whenever a **AMQP / RabbitMQ message is received** for the specified ``routing_key``. By default the ``'amq.topic'`` topic exchange would be used, it may also be overridden by setting the ``options.amqp.exchange_name`` dict value on the service class.

  The ``competing`` value is used when the same queue name should be used for several services of the same type and thus "compete" for who should consume the message. Since ``tomodachi`` version 0.19.x this value has a changed default value and will now default to ``True`` as this is the most likely use-case for pub/sub in distributed architectures.

  Unless ``queue_name`` is specified an auto generated queue name will be used. Additional prefixes to both ``routing_key`` and ``queue_name`` can be assigned by setting the ``options.amqp.routing_key_prefix`` and ``options.amqp.queue_name_prefix`` dict values.

  Depending on the service ``message_envelope`` (previously named ``message_protocol``) attribute if used, parts of the enveloped data would be distributed to different keyword arguments of the decorated function. It's usually safe to just use ``data`` as an argument. You can also specify a specific ``message_envelope`` value as a keyword argument to the decorator for specifying a specific enveloping method to use instead of the global one set for the service.

  If you're utilizing ``from tomodachi.envelope import ProtobufBase`` and using ``ProtobufBase`` as the specified service ``message_envelope`` you may also pass a keyword argument ``proto_class`` into the decorator, describing the protobuf (Protocol Buffers) generated Python class to use for decoding incoming messages. Custom enveloping classes can be built to fit your existing architecture or for even more control of tracing and shared metadata between services.


Scheduled functions / cron:
^^^^^^^^^^^^^^^^^^^^^^^^^^^
``@tomodachi.schedule(interval=None, timestamp=None, timezone=None, immediately=False)``
  A **scheduled function** invoked on either a specified ``interval`` (you may use the popular cron notation as a str for fine-grained interval or specify an integer value of seconds) or a specific ``timestamp``. The ``timezone`` will default to your local time unless explicitly stated.

  When using an integer ``interval`` you may also specify wether the function should be called ``immediately`` on service start or wait the full ``interval`` seconds before its first invokation.

``@tomodachi.heartbeat``
  A function which will be **invoked every second**.

``@tomodachi.minutely``, ``@tomodachi.hourly``, ``@tomodachi.daily``, ``@tomodachi.monthly``
  A scheduled function which will be invoked once **every minute / hour / day / month**.


*You may also extend the functionality by building your own transports for your endpoints. The invokers themselves should extend the class* ``tomodachi.invoker.Invoker``.


Additional configuration options 🤩
-----------------------------------
A ``tomodachi.Service`` service class may specify a class attribute named ``options`` (as a ``dict``) for additional configuration.

=========================================================  ==================================================================================================================================================================================================================================================================================================================================================================================================================================================================================  ===========================================
⁝⁝ **HTTP server parameters** ⁝⁝ ``options["http"][key]``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      ``_____________________________``
---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -------------------------------------------
**Configuration key**                                      **Description**                                                                                                                                                                                                                                                                                                                                                                                                                                                                     **Default value**
---------------------------------------------------------  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -------------------------------------------
``http.port``                                              TCP port (integer value) to listen for incoming connections.                                                                                                                                                                                                                                                                                                                                                                                                                        ``9700``
``http.host``                                              Network interface to bind TCP server to. ``"0.0.0.0"`` will bind to all IPv4 interfaces. ``None`` or ``""`` will assume all network interfaces.                                                                                                                                                                                                                                                                                                                                     ``"0.0.0.0"``
``http.keepalive_timeout``                                 Enables connections to use keep-alive if set to an integer value over `0`. Number of seconds to keep idle incoming connections open.                                                                                                                                                                                                                                                                                                                                                ``0``
``http.client_max_size``                                   The client’s maximum size in a request, as an integer, in bytes.                                                                                                                                                                                                                                                                                                                                                                                                                    ``(1024 ** 2) * 100``
``http.termination_grace_period_seconds``                  The number of seconds to wait for functions called via HTTP to gracefully finish execution before terminating the service, for example if service received a `SIGINT` or `SIGTERM` signal while requests were still awaiting response results.                                                                                                                                                                                                                                      ``30``
``http.real_ip_header``                                    Header to read the value of the client's real IP address from if service operates behind a reverse proxy. Only used if ``http.real_ip_from`` is set and the proxy's IP correlates with the value from ``http.real_ip_from``.                                                                                                                                                                                                                                                        ``"X-Forwarded-For"``
``http.real_ip_from``                                      IP address(es) or IP subnet(s) / CIDR. Allows the ``http.real_ip_header`` header value to be used as client's IP address if connecting reverse proxy's IP equals a value in the list or is within a specified subnet. For example ``["127.0.0.1/32", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]`` would permit header to be used if closest reverse proxy is ``"127.0.0.1"`` or within the three common private network IP address ranges.                                    ``[]``
``http.content_type``                                      Default content-type header to use if not specified in the response.                                                                                                                                                                                                                                                                                                                                                                                                                ``"text/plain; charset=utf-8"``
``http.access_log``                                        If set to the default value (boolean) ``True`` the HTTP access log will be output to stdout (logger ``transport.http``). If set to a ``str`` value, the access log will additionally also be stored to file using value as filename.                                                                                                                                                                                                                                                ``True``
``http.server_header``                                     ``"Server"`` header value in responses.                                                                                                                                                                                                                                                                                                                                                                                                                                             ``"tomodachi"``
---------------------------------------------------------  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -------------------------------------------
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
⁝⁝ **Credentials and prefixes for AWS SNS+SQS pub/sub** ⁝⁝ ``options["aws_sns_sqs"][key]``
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
**Configuration key**                                      **Description**                                                                                                                                                                                                                                                                                                                                                                                                                                                                     **Default value**
---------------------------------------------------------  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -------------------------------------------
``aws_sns_sqs.topic_prefix``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   ``""``
``aws_sns_sqs.queue_name_prefix``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              ``""``
``aws_sns_sqs.region_name``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    ``None``
``aws_sns_sqs.aws_access_key_id``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              ``None``
``aws_sns_sqs.aws_secret_access_key``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          ``None``
---------------------------------------------------------  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -------------------------------------------
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
⁝⁝ **Configure custom AWS endpoints for development** ⁝⁝ ``options["aws_endpoint_urls"][key]``
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
**Configuration key**                                      **Description**                                                                                                                                                                                                                                                                                                                                                                                                                                                                     **Default value**
---------------------------------------------------------  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -------------------------------------------
``aws_endpoint_urls.sns``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      ``None``
``aws_endpoint_urls.sqs``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      ``None``
---------------------------------------------------------  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -------------------------------------------
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
⁝⁝ **AMQP / RabbitMQ pub/sub settings** ⁝⁝ ``options["amqp"][key]``
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
**Configuration key**                                      **Description**                                                                                                                                                                                                                                                                                                                                                                                                                                                                     **Default value**
---------------------------------------------------------  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -------------------------------------------
``amqp.routing_key_prefix``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    ``""``
``amqp.queue_name_prefix``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     ``""``
``amqp.exchange_name``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         ``"amq_topic"``
``amqp.host``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  ``"127.0.0.1"``
``amqp.port``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  ``5672``
``amqp.login``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 ``"guest"``
``amqp.password``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              ``"guest"``
``amqp.virtualhost``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           ``"/"``
``amqp.ssl``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   ``False``
``amqp.heartbeat``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             ``60``
``amqp.queue_ttl``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             ``86400``
---------------------------------------------------------  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -------------------------------------------
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
⁝⁝ **Options for code auto reload on file changes in development** ⁝⁝ ``options["watcher"][key]``
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
**Configuration key**                                      **Description**                                                                                                                                                                                                                                                                                                                                                                                                                                                                     **Default value**
---------------------------------------------------------  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -------------------------------------------
``watcher.ignored_dirs``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       ``[]``
``watcher.watched_file_endings``                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               ``[]``
=========================================================  ==================================================================================================================================================================================================================================================================================================================================================================================================================================================================================  ===========================================


Decorated functions using ``@tomodachi.decorator`` 🎄
-----------------------------------------------------
Invoker functions can of course be decorated using custom functionality. For ease of use you can then in turn decorate your decorator with the the built-in ``@tomodachi.decorator`` to ease development.
If the decorator would return anything else than ``True`` or ``None`` (or not specifying any return statement) the invoked function will *not* be called and instead the returned value will be used, for example as an HTTP response.

.. code:: python

    import tomodachi


    @tomodachi.decorator
    async def require_csrf(instance, request):
        token = request.headers.get("X-CSRF-Token")
        if not token or token != request.cookies.get("csrftoken"):
            return {
                "body": "Invalid CSRF token",
                "status": 403
            }


    class Service(tomodachi.Service):
        name = "example"

        @tomodachi.http("POST", r"/create")
        @require_csrf
        async def create_data(self, request):
            # Do magic here!
            return "OK"


Requirements 👍
---------------
* Python_ (``3.7+``, ``3.8+``, ``3.9+``)
* aiohttp_ (``aiohttp`` is the currently supported HTTP server implementation for ``tomodachi``)
* aiobotocore_ and botocore_ (used for AWS SNS+SQS pub/sub messaging)
* aioamqp_ (used for RabbitMQ / AMQP pub/sub messaging)
* uvloop_ (optional: event loop implementation)

.. _Python: https://www.python.org
.. _asyncio: http://docs.python.org/3.9/library/asyncio.html
.. _aiohttp: https://github.com/aio-libs/aiohttp
.. _aiobotocore: https://github.com/aio-libs/aiobotocore
.. _botocore: https://github.com/boto/botocore
.. _aioamqp: https://github.com/Polyconseil/aioamqp
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
  There's so many ways to orchestrate your infrastructure. Some people may run it within Docker containers, deployed and orchestrated via Terraform / Nomad / Kubernetes / Helm and some may run several services on the same environment, on the same machine. As with all microservices, remember to gather your output and monitor your instances or clusters.

  Personally I would currently go for a Dockerized environment – preferably with an nginx proxy in front of the service to handle all the weirdness of the web if the service isn't just within your own network, but also to let nginx handle TLS, http2 and WebSocket protocol upgrades.

Are there any more example services?
  There are a few examples in the `examples <https://github.com/kalaspuff/tomodachi/blob/master/examples>`_ folder, including using ``tomodachi`` in an `example Docker environment <https://github.com/kalaspuff/tomodachi/tree/master/examples/docker_examples/http_service>`_ with or without docker-compose. There are examples to publish events / messages to an AWS SNS topic and subscribe to an AWS SQS queue. There's also a similar code available of how to work with pub/sub for RabbitMQ via the AMQP transport protocol.

Why should I use this?
  ``tomodachi`` is a perfect place to start when experimenting with your architecture or trying out a concept for a new service. It may not have all the features you desire and it may never do, but I believe it's great for bootstrapping microservices in async Python.

I have some great additions!
  Sweet! Please send me a PR with your ideas. Get started at the short `contribution guide <https://github.com/kalaspuff/tomodachi/blob/master/CONTRIBUTING.rst>`_.

Should I run this in production?
  There are some projects that already have live versions of services running ``tomodachi`` in production. The library is provided as is with an unregular release schedule. As with most software, there will be bugs or inconsistencies. Consider this as beta software and note that it depends on other libraries which may be experimental. Let me know if you do however!

  Another good idea is to drop in Sentry or other exception debugging solutions, to catch errors within the routing or in your microservice's functions in case there are unhandled exceptions raised.

Who built this and why?
  My name is **Carl Oscar Aaro** [`@kalaspuff <https://github.com/kalaspuff>`_] and I'm a coder from Sweden. When I started writing the first few lines of ``tomodachi`` back in 2016 my original intension was just to learn more about asyncio and needed a constructive off-work project for experimentation. Nowadays I use ``tomodachi`` as a base for many smaller API based projects, to quickly get a PoC up and running and to instead be able to put more focus on the application itself, while still having the power of pub/sub events, health checks, GraphQL, HTTP or other ways of interfacing with a service, among other things. 🎉


* https://github.com/kalaspuff
* https://www.linkedin.com/in/carloscaraaro/


Contributions
=============
Please help out to add features that you deem are missing and/or fix
bugs in the repo.

To add a PR, for the repository, commit your changes to your own clone
and make a PR on GitHub for your clone against master branch.

Read more in the `contribution guide <https://github.com/kalaspuff/tomodachi/blob/master/CONTRIBUTING.rst>`_.
