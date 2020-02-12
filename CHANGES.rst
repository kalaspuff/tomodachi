Changes
=======

0.16.5 (2020-02-12)
-------------------
- Bugfix for context reference mismatch when using custom
  invocation decorators which could cause the provided
  context variable to not include the correct information.


0.16.4 (2019-08-28)
-------------------
- Fix for the the race condition causing ``delete_message`` to
  raise an exception, when draining the SQS receive messages call,
  while stopping the service.


0.16.3 (2019-08-23)
-------------------
- It's now possible to get the request object for websocket
  handlers by adding a third argument to the invoker function.
  ``(self, websocket, request)`` or by specifying ``request`` as
  a keyword argument in the function signature. Using the request
  object it's now possible to parse browser headers and other data
  sent when first opening the websocket connction.

- Updated packages for automated tests to verify that newer
  dependencies still works correctly.

- Updated the dependency on ``aioamqp`` to allow ``aioamqp==0.13.x``.


0.16.2 (2019-03-27)
-------------------
- Added keyword arguments for overriding the ``topic_prefix`` and
  ``routing_key_prefix`` when publishing messages. Useful by for
  example intermediaries that needs to publishing messages to
  external services running on other environments, or services
  that are otherwise confined to a prefix / environment but needs
  to contact a core service, i.e. data collection, emails, etc.


0.16.1 (2019-03-21)
-------------------
- Bug fix for websocket handler functions signature inspection in
  middlewares, which caused the function signature to return a
  non-wrapped internal function.


0.16.0 (2019-03-07)
-------------------
- Refactored all internal middleware functionality to use the same base
  function for executing middlewares.

- A middleware context will be passed into the middlewares as
  the optional fifth argument, a ``dict`` that will live within the
  middleware excecution and may pass data along from middleware to
  middleware.


0.15.1 (2019-03-07)
-------------------
- Middlewares first argument ``func: Callable`` will now be wrapped with
  the endpoint function, using ``@functools.wraps``, so that signatures
  and keywords may be inspected and applied accordingly.
  (github: **0x1EE7**)


0.15.0 (2019-02-27)
-------------------
- ``message_middleware`` will now receive four arguments instead of the
  earlier three.
  ``func: Callable, service: Any, message: Any, topic: str`` for SNS and
  ``func: Callable, service: Any, message: Any, route_key: str`` for
  AMQP. If you are using middlewares for messaging you will most likely
  need to update these.

- Additional kwargs may be passed into the ``aws_sns_sqs_publish`` and
  ``amqp_publish`` functions and will be forwarded to the
  ``message_protocol`` ``build_message`` function.


0.14.8 (2019-01-28)
-------------------
- Fixes an issue when websockets were initiated together with an HTTP
  middleware applying additional arguments and keywords.

- Sets the ``request._cache['is_websocket']`` value before handing the
  processing off to the middleware.

- Fixes a bug causing ``aiohttp.web.FileResponse`` return values to not
  show any content.


0.14.7 (2019-01-21)
-------------------
- Added helper functions to be able to get the status code of
  a HTTP response or on a raised exception during a HTTP request.
  ``await tomodachi.get_http_response_status(value, request=request)`` or
  ``await tomodachi.get_http_response_status(exception, request=request)``


0.14.6 (2019-01-14)
-------------------
- Extended middleware functionality to also be available for
  event based messaging (AMQP and SNS+SQS) as
  ``message_middleware``.


0.14.5 (2019-01-09)
-------------------
- Added the support of middlewares to inject additional arguments
  and keywords arguments or overriding existing keyword arguments
  of the invoked function.


0.14.4 (2019-01-06)
-------------------
- Service classes may now use ``http_middleware`` which is a list
  of functions to be run on all HTTP calls and may change the
  behaviour before or after the invoked function is called, either
  preventing the function from being called or modifying the
  response values. An example has been added to the examples
  directory.

- The auto-reloader on code changes will now only reload if a
  the files content has actually changed and not when the file
  was written to disk without changes.


0.14.3 (2018-12-26)
-------------------
- Added support for ``aiohttp`` 3.5.x.


0.14.2 (2018-12-19)
-------------------
- Solves an issue which caused SNS / SQS invoked functions to
  never resume the ReceiveMessage API calls on connection failure,
  resulting in log output saying "Session closed" and requiring
  the service to be restarted.

- Added support for ``aiobotocore`` 0.10.x.


0.14.1 (2018-12-04)
-------------------
- Fixes an issue which caused scheduled functions to spam output
  on computer sleep when developing locally.


0.14.0 (2018-12-04)
-------------------
- Added the possibility of specifying ``message_protocol`` for
  AMQP / SNS+SQS enveloping per function, so that it's possible to
  use both (for example) raw data and enveloped data within the
  same function without having to build fallback enveloping
  functionality.

- Added documentation for ``@tomodachi.decorator``, describing
  how to easily write decorators to use with service invoker
  functions.

- Added ``ignore_logging`` keyword argument to HTTP invoker
  decorator, which may ignore access logging for either specific
  status codes or everything (except ``500`` statuses).
  (github: **justcallmelarry**)

- New function ``tomodachi.get_service()`` or
  ``tomodachi.get_service(service_name)`` available to get the
  service instance object from wherever in the running service,
  much like ``asyncio.get_event_loop()``.

- Updated examples.

- Fixes issue which caused ``aiohttp`` ``FileResponse``
  responses to raise an internal exception.

- Added support for ``aiohttp`` 3.4.x.


0.13.7 (2018-08-10)
-------------------
- Correction for non-defined exception in Python 3.5.


0.13.6 (2018-08-10)
-------------------
- Improved error handling if strict tomodachi dependencies fail to
  load, for example if an installed dependency is corrupt or missing.

- Added additional examples to repository with a demo of pub-sub
  communication.


0.13.5 (2018-08-08)
-------------------
- Fixes an issue which caused HTTP invoker functions to be accessible
  before the bootstrapper function ``_start_service()`` had been
  completed. Now ``_start_service()`` is called first, followed by
  activation of the invoker functions (``@http``, ``@schedule``,
  ``@aws_sns_sqs``, ``@amqp``, etc.) and then lastly the
  ``_started_service()`` function will be called, announcing that the
  service is now up and running.


0.13.4 (2018-08-06)
-------------------
- Added type hinting stubs for ProtoBuf ``_pb2.py`` file to allow
  ``mypy`` to validate functions utilizing the generated protobuf
  files.


0.13.3 (2018-08-03)
-------------------
- RST correction from last release.


0.13.2 (2018-08-03)
-------------------
- Correction regarding type hinting as to where a ``bytes`` value
  could be used as the HTTP body in ``Response`` objects.


0.13.1 (2018-08-01)
-------------------
- Fixes bug with type hinting reporting 'error: Module has no
  attribute "decorator"' when applying a ``@tomodachi.decorator``
  decorator.


0.13.0 (2018-07-25)
-------------------
- Restructured base message protocols for both JSON and ProtoBuf. JSON
  protocol is now called ``tomodachi-json-base--1.0.0`` (earlier
  ``json_base-wip``) and the ProtoBuf protocol is now referred to as
  ``tomodachi-protobuf-base--1.0.0``. Updated proto files are not
  compatible with earlier protocol ``protobuf_base-wip``.


0.12.7 (2018-07-04)
-------------------
- Fixed an issue for using ProtoBuf in development as hot-reloading didn't
  work as expected. (github: **smaaland**)


0.12.6 (2018-07-02)
-------------------
- Additional compatibility for Python 3.7 support including CI testing for
  Python 3.7.

- Improved linting for type hinted functions.


0.12.5 (2018-06-27)
-------------------
- Messages via SNS+SQS or AMQP over 60000 bytes as ProtoBuf will now be sent
  in a gzipped base64 encoded format to allow for larger limits and lower
  potential SNS costs due to multiplexed messaging. (github: **smaaland**)


0.12.4 (2018-06-24)
-------------------
- Updated ``aioamqp`` to the latest version with support for Python 3.7.

- Updated service imports for improved Python 3.7 compatibility.


0.12.3 (2018-06-12)
-------------------
- Improved type hinting support.


0.12.2 (2018-06-12)
-------------------
- Added stubs for type hinting via tools like ``mypy``.


0.12.1 (2018-06-07)
-------------------
- Added complete support for ``aiohttp`` 3.3.x release and
  ``aiobotocore`` 0.9.x releases.


0.12.0 (2018-05-31)
-------------------
- Improved handling of imports to allow relative imports in
  services and to use better error messages if the parent
  package is using a reserved name.

- Preparations for ``aiohttp`` 3.3.x release which deprecates
  some uses for custom router.

- Preparations for upcoming Python 3.7 release.


0.11.3 (2018-05-25)
-------------------
- Added additional function for message validation functionality.
  (github: **smaaland**)

- Updated documentation and examples.


0.11.2 (2018-05-19)
-------------------
- Improved base documentation.

- Improved and updated examples.

- Type hinting corrections for examples.


0.11.1 (2018-05-18)
-------------------
- Decorators for invoker functions already decorated with for example
  ``@tomodachi.http`` or ``@tomodachi.aws_sns_sqs`` is now easier to
  implement using the ``@tomodachi.decorator`` decorator.

- Added improved exception logging from HTTP and schedule invokers also
  to the AWS SNS+SQS and AMQP endpoints. Unhandled exceptions are now
  logged as ``logging.exception()`` to the ``'exception'`` logger.


0.11.0 (2018-05-15)
-------------------
- Propagation of exceptions in invoked functions to be able to hook in
  exception handlers into logging. (github: **0x1EE7**)


0.10.2 (2018-05-15)
-------------------
- Encoding issue for Protocol Buffers messages solved.
  (github: **smaaland**).

- Support for ``aiobotocore`` 0.8.X+.


0.10.1 (2018-04-26)
-------------------
- Fixes a bug for optional dependency ``protobuf``. ``message_protocol``
  imports would break unless the ``google.protobuf`` package was installed.


0.10.0 (2018-04-20)
-------------------
- Base example message protocol class for using Protocol Buffers over AMQP
  or AWS SNS+SQS. (github: **smaaland**).

- Validation of event based messages via validation function specified
  during decoration. (github: **smaaland**)

- Updates to work with ``aiohttp`` 3.1.X+.

- Improved logging functionality.

- Better type hinting and linting.


0.9.5 (2018-03-16)
------------------
- More robust handling of invoking service files that aren't a part of a
  Python package.


0.9.4 (2018-03-06)
------------------
- Fixes an issue affecting websocket connections where the receive function
  was invalidly called twice of which one time were without error handling.


0.9.3 (2018-03-06)
------------------
- Solves an error with functions for AMQP / AWS SNS+SQS functions that are used
  without a message_protocol class.

- Improved disconnect and reconnect to AWS SNS+SQS via aiobotocore on hot-reload
  and during testing.

- Improved README with event based messaging example using AMQP.

- Added the option of running ``schedule`` tasks immediately on service start.
  For example a function decorated by
  ``@schedule(interval=20, immediately=True)`` would be run immediately on
  service start and then every 20 seconds.


0.9.2 (2018-03-05)
------------------
- Improved error handling for bad requests (error 400) on HTTP calls.

- File watcher for hot-reload now excludes ignored directories in a more
  effective way to ease CPU load and for faster boot time for projects
  with thousands of files which should've been ignored.


0.9.1 (2018-03-05)
------------------
- ``schedule`` functions limits to 20 running tasks of the same function to
  prevent overflows in development.

- Fixes an issue where ``schedule`` tasks stopped executing if a service was
  hot-reloaded on code change.

- Handles websocket cancellations better if the client would close the
  connection before the request had been upgraded.


0.9.0 (2018-03-04)
------------------
- Updated to use ``aiohttp`` 3.X.X+ and ``aiobotocore`` 0.6.X+.

- Dropped support for Python versions below 3.5.3 as new ``aiohttp`` requires
  at least Python 3.5.3. Last version with support for Python 3.5.0, 3.5.1 and
  3.5.2 is ``tomodachi`` ``0.8.X`` series.


0.8.3 (2018-03-02)
------------------
- Print stack trace for outputs from ``schedule`` invoker functions tasks
  instead of silently catching exceptions.

- Handle close and receive errors for websockets and cleanly close already
  opened websockets on service exit.


0.8.2 (2018-02-28)
------------------
- Fixed broken HTTP transports due to missing colorama import.


0.8.1 (2018-02-27)
------------------
- Correction for README in 0.8.X release.


0.8.0 (2018-02-27)
------------------
- It's now possible to specify queue_name on AWS SNS+SQS and AMQP decorators
  for competing queues. If not specified an automatically generated hash will
  be used as queue name as it worked previously.

- Fixes an issue with relative imports from within service files, which
  resulted in "SystemParent module '' not loaded, cannot perform relative
  import" or "ImportError: attempted relative import with no known parent
  package". (github: **0x1EE7**)

- Exceptions that are subclasses of ``AmqpInternalServiceError`` and
  ``AWSSNSSQSInternalServiceError`` will now also work in the same way,
  resulting in the messages to be retried when raised.

- Service classes now have built in log functions for setting up logging to
  file as well as logging. They are ``self.log_setup('logname', level,
  filename)`` and ``self.log('logname', level, message)``.

- HTTP services will have their access log color coded when outputting to
  nothing else than stdout, which should be helpful in an overview during
  development.


0.7.0 (2018-01-27)
------------------

- Added `@websocket` as a decorator type for handling websockets. A function
  call should return two callables which will be used for receiving messages
  through the socket and as a way to notify about the closure of the socket.


0.6.5 (2018-01-16)
------------------

- Updated `aiohttp` to latest version which solves incompabilities with `yarl`.


0.6.4 (2018-01-15)
------------------

- Added a stricter dependency check for `yarl`.


0.6.3 (2018-01-12)
------------------

- Gracefully handle exceptions thrown when receiving messages from AWS SNS+SQS.
  For example when invalid XML data in response which causes botocore to throw
  a botocore.parsers.ResponseParserError.

- Updated dependencies to allow for newer version of aiohttp 2.3.X.

- Improved type hinting.


0.6.2 (2017-11-15)
------------------

- Recreate queues and resubscribe to topics if queue is removed during runtime.


0.6.1 (2017-11-15)
------------------

- Introduced new options for AWS SNS/SQS transport to use `aws_endpoint_urls`
  for `sns` and `sqs` if the user wishes to connect to other endpoints and the
  actual AWS endpoints, which could be useful for development and testing. The
  AWS SNS/SQS examples has been updated with values to reflect these options.

- Reworked timeouts and reconnects and fixed an issue in the recreate_client
  method which was called on server disconnects.


0.6.0 (2017-11-15)
------------------

- Stricter version control of required packages to not break installation on
  major/minor related updates.

- Updates to support aiohttp 2.3.X and aiobotocore 0.5.X.


0.5.3 (2017-11-08)
------------------

- Corrects issues on timeouts and server disconnects.

- Specify fixed version for aiohttp to not break installation.

- Code cleanup to conform with pycodestyle.


0.5.2 (2017-10-08)
------------------

- Add argument option for log level as '-l' or '--log'. (github: **djKooks**)

- Better matching of imported modules on hot-reload which will cause reloading
  into code with syntax errors or indentation errors much harder.


0.5.1 (2017-10-03)
------------------

- More improvements regarding hot-reloading of code that may have syntax errors,
  indentation errors or issues when the service is being initiated.


0.5.0 (2017-10-02)
------------------

- Solves the issue where hot-loading into a state where the code errors due to
  syntax errors would crash the application, making the user need to manually
  restart the process.


0.4.10 (2017-10-02)
-------------------

- Fixes for failing tests on hot-reloading during test phase.


0.4.9 (2017-10-02)
------------------

- Solves issue with Segmentation fault in Python 3.6 during hot-reload on
  Linux.


0.4.8 (2017-10-02)
------------------

- Fixes type hinting issues with Python 3.5.1.


0.4.7 (2017-09-30)
------------------

- Reworked watcher since it ended up using 90% CPU of the running core due to
  constant re-indexing (mstat) of every file every 0.5s. Full re-index will now
  only run every 10 seconds, since it's more rare that new files are added than
  existing files edited. Watcher for edited existing files will still run at the
  same intervals.

- Watched file types may now be specified via configuration via
  ``options.watcher.watched_file_endings``.


0.4.6 (2017-09-29)
------------------

- Messages via SNS+SQS or AMQP over 60000 bytes as JSON will now be sent in a
  gzipped base64 encoded format to allow for larger limits and lower potential
  SNS costs due to multiplexed messaging.

- Fixes an issue with multidict 3.2.0 on hot-reload which made the tomodachi
  application crash.


0.4.5 (2017-09-07)
------------------

- Possibility to requeue messages that result in specific exceptions.
  Exceptions that will nack the message (for AMQP transport) is called
  ``AmqpInternalServiceError``. Exceptions that won't delete the message from
  the queue and in turn will result in it to "reappear" unless configured
  non-default (for AWS SNS+SQS transport) is called
  ``AWSSNSSQSInternalServiceError``.


0.4.4 (2017-08-25)
------------------

- Corrected an issue regarding crontab notation for scheduling function calls
  where it didn't parse the upcoming date correctly if both isoweekday and day
  part were given.


0.4.3 (2017-08-09)
------------------

- Catches unintended HTTP exceptions and prints a useful stacktrace if log_level
  is set to DEBUG.


0.4.2 (2017-08-07)
------------------

- Fixes an issue where Content-Type header couldn't be specified without
  charset in HTTP transports.

- Cleared some old debug code.


0.4.1 (2017-08-05)
------------------

- Corrects and issue with AMQP transport which caused invoked functions to not
  be able to declare scope variables without crashes.


0.4.0 (2017-08-05)
------------------

- Release fixes a major issue which caused invoked functions to not be able to
  declare any scope variables.

- ``@http_static`` decorator for serving static files from a folder on disk.
  Takes to values; 1. the path to the folder, either relative to the service
  file or absolute; 2. the base URL path for static files as a regexp.


0.3.0 (2017-07-25)
------------------

- Changed format of access log for HTTP requests - now logging user agent and
  login name (if authorization via Basic Auth).

- Support for ``X-Forwarded-For`` headers via ``real_ip_from`` and
  ``real_ip_header`` options which will log the forwarded IP instead of the
  one from the load balancer / proxy.

- Access log for HTTP can now be specified as a filename to which the service
  will log all requests.

- Fixes issue with schedule invoker which would crash if invoked at second 0.

- Updated dependencies to latest available versions.


0.2.17 (2017-07-05)
-------------------

- Timezone support for ``schedule`` invoker functions.

- Added more decorator invoker functions as aliases for common scheduler
  use cases - ``@minutely``, ``@hourly``, ``@daily`` and ``@heartbeat`` (every
  second)

- Updated example services and better test cases.

- Updated aiohttp / aiobotocore / botocore dependencies.


0.2.16 (2017-07-02)
-------------------

- Solved issues with aiobotocore / aiohttp dependencies.

- Refactored loader functions.


0.2.15 (2017-07-02)
-------------------

- Corrected issue with configuration values for AWS and AWS SNS+SQS settings.

- Improved testing suite and more code coverage for integration tests.


0.2.14 (2017-06-30)
-------------------

- New "transport" invoker for service functions: ``schedule``. It works like
  cron type scheduling where specific functions will be run on the specified
  interval. For example a function can be specified to run once per day at a
  specific time or every second minute, or the last Tuesday of January and
  March at 05:30 AM.

- Values for keyword arguments invoked by transport decorators were earlier
  always set to ``None``, despite having other default values. This is now
  corrected.


0.2.13 (2017-06-20)
-------------------

- Type hinted examples and test cases.

- Shielded function calls for AMQP and SNS+SQS transports to avoid unexpected
  execution stop.

- Added version output to tomodachi CLI tool.

- Additional test cases.


0.2.12 (2017-06-18)
-------------------

- Type hinted code base and minor bug fixes for internal functions.


0.2.11 (2017-06-09)
-------------------

- Invoker methods can now be called directly without the need to mock the
  invoker decorator function.


0.2.10 (2017-06-08)
-------------------

- Added ``@functools.wraps`` decorator to invoked functions of service classes.


0.2.9 (2017-06-06)
------------------

- Added a list of safe modules that may never be removed from the list of
  already loaded modules. Removing the module 'typing' from the list would
  cause a RecursionError exception since Python 3.6.1.


0.2.8 (2017-05-23)
------------------

- Additional improvements to network connectivity issues to not get stuck in
  waiting state.


0.2.7 (2017-05-23)
------------------

- Improved SNS+SQS draining / restart when network connectivity has been lost
  or temporarily suspended. Would improve situations when development machine
  has been in hibernation.

- Replaced deprecated logging functions to rid warnings.


0.2.6 (2017-05-22)
------------------

- Support for a "generic" aws dictonary in options that can hold region,
  access key id and secret to be shared among other AWS resources/services.

- Updated aiobotocore / botocore dependencies.

- Gracefully handle and discard invalid SNS/SQS messages not in JSON format.

- Corrected issue where watched directories with "similar" names as settings
  would be ignored.


0.2.5 (2017-05-16)
------------------

- Updated issues with function caching due to keepalive when hot reloading in
  development. Currently disables keepalive entirely.

- Fixed issue with updated file logging for watcher.


0.2.4 (2017-05-12)
------------------

- Downgraded botocore to meet requirements and to make the installed
  ``tomodachi`` script runnable again.


0.2.3 (2017-05-10)
------------------

- Watcher is now configurable to ignore specific directories dependant on the
  service. (github: **smaaland**)

- Fixed issue where using ``--config`` instead of ``-c`` would result in a
  raised exception. (github: **smaaland**)


0.2.2 (2017-05-04)
------------------

- ``tomodachi.transport.http`` has its own Response object that works better
  with default content types and charsets - examples/http_service.py updated.

- No automatic conversion will be tried if the returned response of an http
  method is of ``bytes`` type.

0.2.1 (2017-05-03)
------------------

- Improved handling of how charsets and encodings work with aiohttp.

- Fixed an issue where ``Content-Type`` header would always be included twice
  for aiohttp.web.Response objects.


0.2.0 (2017-05-02)
------------------

- Watcher now only reacts to files with file endings ``.py``, ``.json``,
  ``.yml``, ``.html`` or ``.html`` and ignores to look at paths
  ``__pycache__``, ``.git``, ``.svn``, ``__ignored__``, ``__temporary__`` and
  ``__tmp__``.

- HTTP transport may now respond with an aiohttp.web.Response object for more
  complex responses.

- HTTP transport response headers can now use the multidict library.


0.1.11 (2017-04-02)
-------------------

- Working PyPI release.

- Added unit tests.

- Works with aiohttp 2 and aiobotocore 0.3.

- Service classes must be decorated with ``@tomodachi.service``.
