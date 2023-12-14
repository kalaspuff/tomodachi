Changes
=======

0.26.4 (xxxx-xx-xx)
-------------------

- ...


0.26.3 (2023-12-14)
-------------------

- Updated version constraints of the ``opentelemetry-exporter-prometheus`` dependency to use the correct (non-yanked) version range.
- Support for ``aiobotocore`` 2.8.x releases and 2.9.x releases.


0.26.2 (2023-11-24)
-------------------

- Support for Python 3.12. Python 3.12 has been added to test matrix and trove classifiers.
- Supports ``aiohttp`` 3.9.x versions.
- Updated OpenTelemetry distro to handle MetricReaders and MetricExporters in a more flexible way (similar to how it was changed to be done in ``opentelemetry-sdk`` 1.21.0).
- Log entries from ``tomodachi.logging`` on OTEL instrumented services will now include TraceContext (``span_id``, ``trace_id`` and ``parent_span_id``) on non-recording (but valid) spans.


0.26.1 (2023-10-02)
-------------------

- Uses less strict version constraints on OpenTelemetry dependencies to make it easier to use newer versions of OpenTelemetry libraries together with ``tomodachi`` services.
- Passes FIFO message attributes (``message_deduplication_id`` and ``message_group_id``) to ``tomodachi`` handler functions as keyword argument provided transport values. (github: **filipsnastins**)


0.26.0 (2023-09-01)
-------------------

**New and updated**

- Major refactoring of how logging is done, introducing ``tomodachi.get_logger()`` built on ``structlog``. Contextual logger available for all handlers, etc.
- Provides the option of hooking in ``tomodachi`` to a custom logger the user provides.
- Adds instrumentation for ``opentelemetry`` (OTEL / OpenTelemetry) that can be enabled if ``tomodachi`` is installed using the ``opentelemetry`` extras.
- OTEL auto instrumentation can be achieved by starting services using either the ``tomodachi run`` argument ``--opentelemetry-instrument`` (equivalent to setting env: ``TOMODACHI_OPENTELEMETRY_INSTRUMENT=1``) or using the ``opentelemetry-instrument`` CLI.
- An experimental meter provider for exporting OpenTelemetry metrics on a Prometheus server can be used by installing the ``opentelemetry-exporter-prometheus`` extras and using the ``OTEL_PYTHON_METER_PROVIDER=tomodachi_prometheus`` environment value in combination with OTEL instrumentation.
- Adds the option to enable exemplars in the Prometheus client for OpenTelemetry metrics, to be able to link to traces from collected metrics in Grafana, et al.
- The HTTP body for requests with a body is read before the handler is called and if the connection was closed prematurely before the body could be read, the request will be ignored.
- Replaces the banner shown when starting a service without ``--production``. The banner now includes the operating system, architecture, which Python runtime from which virtualenv is used, etc. in order to aid debugging during development for issues caused by environment misconfiguration.
- Updated the CLI usage output from ``--help``.
- Added a value ``tomodachi.__build_time__`` which includes the timestamp when the build for the installed release was done. The time that has passed since build time will be included in the start banner.
- Makes use of ``asyncio`` tasks instead of simply awaiting the coroutines so that the context from contextvars will be propagated correctly and not risk being corrupted by handlers.
- Added an internal lazy meta importer to ease renaming and deprecations of modules.
- Added additional lazy loading of submodules.
- Each argument for ``tomodachi run`` is now accompanied with an environment variable to do the same. For example ``--log-level warning`` can be achieved by setting ``TOMODACHI_LOG_LEVEL=warning``.
- Updated documentation with additional information.

**Potentially breaking changes**

- The complete refactoring of logging changes how log entries are being emitted, both in the way that the event / message of the log records has changed, but also how a log handler is now also added to the ``logging.root`` logger on service start.
- Third party log records will if propagation is enabled also be processed in ``tomodachi.logging`` which may cause duplicate log output depending on how the third party logger is configured.
- Removed the ``log_setup()`` function that previously was added to the service object on class initialization and that was used to setup log output to disk.
- Tracebacks for uncaught exceptions are now extracted to only include frames relevant to the service application and not the internal ``tomodachi`` frames, which usually will be uninteresting for debugging.

**Bug fixes**

- Fixes exception catching of lifecycle handlers (``_start_service``, ``_started_service``, etc.) which previously could stall a service raising an exception while starting, instead of exiting with a non-zero exit code.
- Bug fix for an issue which could cause the watcher to fail to restart the service after a syntax error was encountered.
- Adds some missing type hint annotations.
- Added additional logging of uncaught exceptions that previously may have been silenced.
- Fixed that the ``--log-level`` CLI argument value is actually applied to loggers.
- Fix for a race condition which could freeze a process if a service was manually stopped (interrupted with ctrl+c) before it had called its first lifecycle function (``_start_service``).

**Deprecations**

- Added deprecation warnings for more legacy functionality to give notice that those functions will be removed in a future release.
- The use of the ``log()`` function added to the service object is deprecated. Use the ``structlog`` logger from ``tomodachi.get_logger()`` instead.
- Using the ``RequestHandler.get_request_ip`` is deprecated. Instead use the ``tomodachi.get_forwarded_remote_ip()`` function.
- Deprecated the use of the CLI argument ``-c`` (``--config``) which could be used to set object attributes from a JSON file. A better pattern is to read optional config data from an environment variable.


0.25.1 (2023-08-11)
-------------------

- Fix for an issue where a wrapped function is used as a handler function,
  which would then cause the keyword argument provided transport values to
  rely on the keyword arguments from the *wrapped function's* signature to be
  used instead of the keyword arguments from the *wrapper function's* signature.

  The bug was found to be present since the last release, which included major
  refactoring of the *keyword argument provided transport values* functionality.


0.25.0 (2023-06-24)
-------------------

- The middleware execution logic has been improved to handle different argument
  types and edge cases more smoothly. Enhanced the way arguments are passed to
  middlewares and handlers, allowing better flexibility.

- Resolved an edge case where a service could end up calling ``SNS.CreateTopic``
  numerous times due to thousands of messages simultanously being published to
  a topic that were previously unknown to the service.

- The ``aws_sns_sqs_publish`` function will now return the SNS message identifier
  as a ``str`` value if it is called with ``wait=True`` (default), or instead
  return an ``asyncio.Task`` object if called with ``wait=False``.

- Function handlers, middlewares and envelopes can all now specify additional
  keyword arguments in their signatures and receive transport centric values.

  Previously a few of these keyword values could be used for function handlers
  or envelopes, but not within middlewares. With this update the following
  keywords can be used across all kind of handler functions to allow for more
  flexibility in how to structure apps, logging, tracing, authentication, etc.

  |
  .. code:: python

    Category: "AWS SNS+SQS related values"

  :sup:`Use the following keywords arguments in function signatures (for handlers, middlewares and envelopes used for AWS SNS+SQS messages).`

  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``message_attributes``        | Values specified as message attributes that accompanies the message                            |
  |                               | body and that are among other things used for SNS queue subscription                           |
  |                               | filter policies and for distributed tracing.                                                   |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``queue_url``                 | Can be used to modify visibility of messages, provide exponential backoffs, move to DLQs, etc. |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``receipt_handle``            | Can be used to modify visibility of messages, provide exponential backoffs, move to DLQs, etc. |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``approximate_receive_count`` | A value that specifies approximately how many times this message has                           |
  |                               | been received from consumers on ``SQS.ReceiveMessage`` calls. Handlers                         |
  |                               | that received a message, but that doesn't delete it from the queue                             |
  |                               | (for example in order to make it visible for other consumers or in                             |
  |                               | case of errors), will add to this count for each time they received it.                        |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``topic``                     | Simply the name of the SNS topic.                                                              |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``sns_message_id``            | The message identifier for the SNS message (which is usually embedded                          |
  |                               | in the body of a SQS message). Ths SNS message identifier is the same                          |
  |                               | that is returned in the response when publishing a message with                                |
  |                               | ``SNS.Publish``.                                                                               |
  |                               |                                                                                                |
  |                               | The ``sns_message_id`` is read from within the ``"Body"`` of SQS                               |
  |                               | messages.                                                                                      |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``sqs_message_id``            | The SQS message identifier, which naturally will differ from the SNS                           |
  |                               | message identifier as one SNS message can be propagated to several                             |
  |                               | SQS queues.                                                                                    |
  |                               |                                                                                                |
  |                               | The ``sns_message_id`` is read from the ``"MessageId"`` value in the                           |
  |                               | top of the SQS message.                                                                        |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``message_timestamp``         | A timestamp of when the original SNS message was published.                                    |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``_________________________`` | ``_________________________``                                                                  |
  +-------------------------------+------------------------------------------------------------------------------------------------+

  |
  .. code:: python

    Category: "HTTP related values"

  :sup:`Use the following keywords arguments in function signatures (for handlers and middlewares used for HTTP requests).`

  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``request``                   | The ``aiohttp`` request object which holds functionality for all                               |
  |                               | things HTTP requests.                                                                          |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``status_code``               | Specified when predefined error handlers are run. Using the                                    |
  |                               | keyword in handlers and middlewares for requests not invoking                                  |
  |                               | error handlers should preferably be specified with a default                                   |
  |                               | value to ensure it will work on both error handlers and request                                |
  |                               | router handlers.                                                                               |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``websocket``                 | Will be added to websocket requests if used.                                                   |
  +-------------------------------+------------------------------------------------------------------------------------------------+
  | ``_________________________`` | ``_________________________``                                                                  |
  +-------------------------------+------------------------------------------------------------------------------------------------+


0.24.3 (2023-06-15)
-------------------

- Fixes an issue in the internal retry logic when using ``aws_sns_sqs_publish``
  if calls to the AWS API ``SNS.Publish`` would intermittently respond with 408
  response without any body, which previously would've resulted in a
  ``AWSSNSSQSException("Missing MessageId in response")`` immediately without
  retries.

  This was previously attempted to be fixed in the 0.23.0 release, but instead
  fell through to become an exception with the
  ``"Missing MessageId in response"`` message instead.

  The publish function will now catch exceptions from ``botocore`` of type
  ``ResponseParserError`` to which ``botocore`` has added that
  ``"Further retries may succeed"``. ``tomodachi`` will retry such
  ``SNS.Publish`` calls up to 3 times and if after all retries the library will
  reraise the exception from ``botocore``.

  It seems that ``botocore`` does not automatically retry such errors itself.

- Similar to the above, the same kind of retries will now also be done during
  AWS API calls for ``SQS.DeleteMessage``, where the
  ``botocore.parser.QueryParser`` would raise an ``ResponseParserError`` exception
  on 408 responses without body.


0.24.2 (2023-06-13)
-------------------

- Fixes typing syntax for compatibility with Python 3.8 and Python 3.9 to solve the
  incompatibility for Python 3.8 and Python 3.9 introduced in the the 0.24.1 release.

- Fixes an issue with an AWS SQS queue's message retention period attribute using an
  incompatible default value for FIFO queues.

- Support for ``aiobotocore`` 2.5.x releases.

- README.rst fixes to conform with RST format. (github: **navid-agz**)


0.24.1 (2023-06-01)
-------------------

- Adds max number of messages that the service will consume when using AWS SNS+SQS
  handlers configurable. (github: **navid-agz**)

- Changed default retention period of dead-letter-queues on AWS SNS+SQS.
  (github: **PabloAJomer**)


0.24.0 (2022-10-25)
-------------------

- ``cchardet`` is no longer a direct dependency to ``tomodachi`` on Python 3.10 and
  Python 3.11. If you want to use it, you must install it separately, which may
  require additional build tools when installing on Python 3.10+.

- Updates to the internal ``tomodachi.envelope.ProtobufBase`` envelope to now also
  support protobuf Python bindings versioned >=4.0.0, when running with the
  (new default) ``PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=upb`` as ``upb`` slightly
  differs in representation of a Message type in relation to ``cpp`` and ``python``
  implementations.

- Python 3.11 added to test matrix and trove classifiers to officially claim support.


0.23.0 (2022-10-16)
-------------------

- Properly handles ``aiobotocore`` client using an async contextmanager.
  Drops support for ``aiobotocore`` versions prior 1.3.0, but will now supporting
  newer versions. (github: **drestrepom**)

- Fixes an issue to now retry calls where AWS SNS intermittently responds with
  408 responses without any body, which trips up ``botocore.parser.QueryParser``.
  (github: **technomunk**)

- Refactored options used for AWS SNS+SQS, HTTP, AMQP and the Watcher
  functionality. Options set on the service class should now be defined as a
  ``tomodachi.Options`` object, which provides type hints and much nicer path
  traversal of the class.

  Only the specified typed values for ``options`` will now be allowed to be set.
  Setting a non-defined option will raise an ``AttributeError`` exception on
  service start.

  The previous ``dict`` based approach is still supported, but will be removed
  in a future version.

- Dropped support for Python 3.7.


0.22.3 (2022-08-09)
-------------------

- Support for assigning values to AWS SQS queue attributes value
  ``VisibilityTimeout`` and ``RedrivePolicy`` that is used to assign a
  queue to use a dead-letter queue after a number of failed attempts to
  consume a message. By default no changes will be done to the existing
  queue attributes and a change will only be triggered by assigning
  values to the ``visibility_timeout`` or both of
  ``dead_letter_queue_name`` + ``max_receive_count`` keyword arguments.

  .. code:: python

      @tomodachi.aws_sns_sqs(
          topic=None,
          competing=True,
          queue_name=None,
          filter_policy=FILTER_POLICY_DEFAULT,
          visibility_timeout=VISIBILITY_TIMEOUT_DEFAULT,     # affects MessageVisibility
          dead_letter_queue_name=DEAD_LETTER_QUEUE_DEFAULT,  # affects RedrivePolicy
          max_receive_count=MAX_RECEIVE_COUNT_DEFAULT,       # affects RedrivePolicy
          **kwargs,
      )

- Fixes a bug where SQS messages wouldn't get deleted from the queue if
  a middleware function catches an exception without reraising it. This
  is because the ``delete_message`` is not called from within ``routine_func``
  (due to the exception breaking normal control flow), but the message
  deletion from middleware bubble is also skipped, as no exception is
  propagated from it. (github: **technomunk**)

- Adds basic support for FIFO queues & topics on AWS SQS queues managed by
  a ``tomodachi`` service decorated function, which can be used where one
  needs guaranteed ordering of the consumed messages. (github: **kjagiello**)

- Updates to the internal ``tomodachi.envelope.ProtobufBase`` envelope to now also
  support newer versions of protobuf.

- Added documentation to describe the "magic" functions that hooks into the
  service lifecycle; ``_start_service``, ``_started_service``, ``_stopping_service``,
  ``_stop_service``.


0.22.2 (2022-04-07)
-------------------

- Fixes an issue with live reloading on code changes (development mode)
  with services utilizing ``protobuf`` messages, which in same edge cases
  could trigger a repeated
  ``TypeError("A Message class can only inherit from Message")`` that would
  prevent the service from restarting correctly.


0.22.1 (2022-03-14)
-------------------

- Added an additional way of gracefully triggering shutdown of a running
  service, by using the new ``tomodachi.exit()`` function, which will
  initiate the termination processing flow in the same way as signaling
  ``SIGINT`` or ``SIGTERM``. The ``tomodachi.exit()`` call can additionally
  take an optional exit code as an argument to support new ways of catching
  service operation.

- The process' exit code can also be altered by changing the value of
  ``tomodachi.SERVICE_EXIT_CODE``, however using the new ``tomodachi.exit``
  call with an integer argument will override any previous value set to
  ``tomodachi.SERVICE_EXIT_CODE``. The default value is set to ``0``.


0.22.0 (2022-02-25)
-------------------

- Handle exceptions lower in the stack for messaging services (AMQP and AWS
  SNS+SQS handlers), which now allows catching exceptions in middlewares,
  which was previously not possible. (github: **justcallmelarry**)

- Improved documentation for uses of ``tomodachi.get_service``
  (github: **jmfederico**)

- Type hint annotation improvements.


0.21.8 (2021-11-19)
-------------------

- Adds the possibility to add a function called ``_stopping_service`` to the
  ``tomodachi`` Service class, which is run as soon as a termination signal
  is received by the service. (github: **justcallmelarry**)

- Fix for potential exceptions on botocore session client raising a
  ``RuntimeError``, resulting in a tomodachi "Client has never been created
  in the first place" exception on reconnection to AWS APIs.

- Added Python 3.10 to the CI test matrix run via GitHub Actions.

- Additional updates for compatibility with typing libraries to improve
  support for installations on Python 3.10.

- Supports ``aiohttp`` 3.8.x versions.

- Supports ``tzlocal`` 3.x and 4.x releases.


0.21.7 (2021-08-24)
-------------------

- Pins ``aiobotocore`` to use up to 1.3.x releases, since the 1.4.x
  versions session handling currently causes issues when used.


0.21.6 (2021-08-17)
-------------------

- Now pins the ``tzlocal`` version to not use the 3.x releases as it would
  currently break services using scheduled functions (the ``@schedule``
  decorator, et al) if ``tzlocal`` 3.0 is installed.

- Updated classifiers to identify that the library works on Python 3.10.

- Added the new ``Framework :: aiohttp`` classifier.


0.21.5 (2021-08-04)
-------------------

- If a ``PYTHONPATH`` environment value is set and a service is started
  without the ``--production`` flag, the paths specified in ``PYTHONPATH``
  will be added to the list of directories to watch for code changes and
  in the event of any changes done to files on those directories, the
  service will restart. Previously only code changes in the directory or
  sub directory of the current working directory + the directory of the
  started service (or services) were monitored.

- The ``topic`` argument to the ``@tomodachi.aws_sns_sqs`` decorator is
  now optional, which is useful if subscribing to a SQS queue where the SNS
  topic or the topic subscriptions are set up apart from the service code,
  for example during deployment or as infra.


0.21.4 (2021-07-26)
-------------------

- Encryption at rest for AWS SNS and/or AWS SQS which can optionally be configured by specifying the KMS key alias or KMS key id as a tomodachi service option ``options.aws_sns_sqs.sns_kms_master_key_id`` (to configure encryption at rest on the SNS topics for which the tomodachi service handles the SNS -> SQS subscriptions) and/or ``options.aws_sns_sqs.sqs_kms_master_key_id`` (to configure encryption at rest for the SQS queues which the service is consuming).

  Note that an option value set to empty string (``""``) or ``False`` will unset the KMS master key id and thus disable encryption at rest. (The AWS APIs for SNS and SQS uses empty string value to the KMSMasterKeyId attribute to disable encryption with KMS if it was previously enabled).

  If instead an option is completely unset or set to ``None`` value no changes will be done to the KMS related attributes on an existing topic or queue.

  If it's expected that the services themselves, via their IAM credentials or assumed role, are responsible for creating queues and topics, these options could be used to provide encryption at rest without additional manual intervention

  *However, do not use these options if you instead are using IaC tooling to handle the topics, queues and subscriptions or that they for example are created / updated as a part of deployments. To not have the service update any attributes keep the options unset or set to a* ``None`` *value.*

  | https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-server-side-encryption.html
  | https://docs.aws.amazon.com/sns/latest/dg/sns-server-side-encryption.html#sse-key-terms.

- Fixes an issue where a GET request to an endpoint serving static files via ``@http_static`` could be crafted to probe the directory structure setup (but not read file content outside of its permitted path), by applying directory traversal techniques. This could expose the internal directory structure of the file system in the container or environment that the service is hosted on. Limited to if ``@http_static`` handlers were used within the service and those endpoints could be accessed.

- Additional validation for the path used in the ``@http_static`` decorator to prevent a developer from accidentally supplying a ``"/"`` or ``""`` value to the ``path`` argument, which in those cases could lead to unintended files being exposed via the static file handler.


0.21.3 (2021-06-30)
-------------------

- Fixes an issue causing a ``UnboundLocalError`` if an incoming
  message to a service that had specified the enveloping
  implementation ``JsonBase`` where JSON encoded but actually
  wasn't originating from a source using a ``JsonBase`` compatible
  envelope.

- Fixes error message strings for some cases of AWS SNS + SQS
  related cases of ``botocore.exceptions.ClientError``.

- Fixes the issue where some definitions of filter policies would
  result in an error when running mypy – uses ``Sequence`` instead
  of ``List`` in type hint definition for filter policy input types.

- Internal updates for developer experience – refactoring and
  improvements for future code analysis and better support for
  IntelliSense.

- Updates to install typeshed generated type hint annotation stubs
  and updates to support ``mypy==0.910``.


0.21.2 (2021-02-16)
-------------------

- Bugfix for an issue which caused the ``sqs.DeleteMessage`` API call
  to be called three times for each processed SQS message (the
  request to delete a message from the queue is idempotent) when
  using AWS SNS+SQS via ``@tomodachi.aws_sns_sqs``.

- Now properly cleaning up clients created with
  ``tomodachi.helpers.aiobotocore_connector`` for ``aiobotocore``,
  which previously could result in the error output
  "Unclosed client session" if the service would fails to start,
  for example due to initialization errors.


0.21.1 (2021-02-14)
-------------------

- Added ``sentry_sdk`` to the list of modules and packages to not be
  unloaded from ``sys.modules`` during hot reload of the running
  when code changes has been noticed. This to prevent errors like
  ``TypeError: run() takes 1 positional argument but X were given``
  from ``sentry_sdk.integrations.threading`` when handling early
  errors or leftover errors from previous session.


0.21.0 (2021-02-10)
-------------------

- Uses the socket option ``SO_REUSEPORT`` by default on Linux unless
  specifically disabled via the ``http.reuse_port`` option set
  to ``False``. This will allow several processes to bind to the
  same port, which could be useful when running services via a
  process manager such as ``supervisord`` or when it's desired to
  run several processes of a service to utilize additional CPU cores.
  The ``http.reuse_port`` option doesn't have any effect when a
  service is running on a non-Linux platform.
  (github: **tranvietanh1991**)

- Services which works as AMQP consumers now has a default prefetch
  count  value of 100, where previously the service didn't specify
  any prefetch count option, which could exhaust the host's resources
  if messages would be published faster to the queue than the
  services could process them. (github: **tranvietanh1991**)

- AWS SNS+SQS calls now uses a slightly changed config which will
  increase the connection pool to 50 connections, decreases the
  connect timeout to 8 seconds and the read timeout to 35 seconds.

- Possible to run services using without using the ``tomodachi``
  CLI, by adding ``tomodachi.run()`` to the end of the Python
  file invoked by ``python`` which will start services within
  that file. Usually in a ``if __name__ == "__main__":``
  if-block.

- The environment variable ``TOMODACHI_LOOP`` can be used to specify
  the event loop implementation in a similar way as the CLI
  argument ``--loop [auto|asyncio|uvloop]`` would.

- Environment variable ``TOMODACHI_PRODUCTION`` set to ``1`` can be
  used to run the service without the file watcher for automatic
  code reloads enabled, which then yields higher performance.
  Equivalent as starting the service with the ``--production``
  argument.

- Smaller performance improvements throughout the framework.

- Improved error handling overall in regards to non-standard
  exceptions and additional output, if scheduled tasks are unable
  to run due to other start methods not completing their initial
  setup.


0.20.7 (2020-11-27)
-------------------

- Reworked type hinting annotations for AWS SNS+SQS filter policies
  as there were still cases found in the previous tomodachi version
  that didn't work as they should, and raised mypy errors where a
  correct filter policy had been applied.


0.20.6 (2020-11-24)
-------------------

- Fixes a type annotation for the ``aws_sns_sqs`` decorator's keyword
  argument ``filter_policy``, which could result in a ``mypy`` error
  if an "anything-but" filter policy was used.


0.20.5 (2020-11-18)
-------------------

- Await potential lingering connection responses before shutting down
  HTTP server.


0.20.4 (2020-11-17)
-------------------

- Optimizations for HTTP based function tasks, which should lower the
  base CPU usage for ``tomodachi.http`` decorated tasks between
  5% - 25% when using middlewares or the default access log.


0.20.3 (2020-11-16)
-------------------

- Corrects an issue with having multiple invoker decorators to the
  same service function / task.

- Fixed the ``http.client_max_size`` option, which invalidly always
  defaulted to ``(1024 ** 2) * 100`` (``100MB``), even though specified
  to another value.

- Fixes backward compability with ``aiohttp`` 3.5.x.


0.20.2 (2020-11-16)
-------------------

- Fixes an issue which could cause hot reloading of services to break
  (for example when using Protocol Buffers), due to the change in
  pre-initialized modules from the ``tomodachi`` 0.20.0 release.


0.20.1 (2020-11-04)
-------------------

- Fixes the bug which caused almost all dependencies to be optional
  installs ("extras") if ``tomodachi`` were installed with ``pip``.
  All previous required dependencies are now again installed by default
  also when using ``pip`` installer.


0.20.0 (2020-10-27)
-------------------

- Lazy loading of dependencies to lower memory footprint and to make
  services launch quicker as they usually don't use all built-in
  implementations. Reference services launch noticeable faster now.

- Optimizations and refactoring of middleware for all service function
  calls of all built-in invokers, saving somewhere around 10-20% on CPU
  time in average.

- Improvements to awaiting open keep-alive connections when terminating
  a service for a lower chance of interrupting last second incoming
  requests over the connection.

- New option: ``http.max_keepalive_requests``. An optional number (int)
  of requests which is allowed for a keep-alive connection. After the
  specified number of requests has been done, the connection will be
  closed. A value of ``0`` or ``None`` (default) will allow any number
  of requests over an open keep-alive connection.

- New option: ``http.max_keepalive_time``. An optional maximum time in
  seconds (int) for which keep-alive connections are kept open. If a
  keep-alive connection has been kept open for more than
  ``http.max_keepalive_time`` seconds, the following request will be
  closed upon returning a response. The feature is not used by default
  and won't be used if the value is ``0`` or ``None``. A keep-alive
  connection may otherwise be open unless inactive for more than the
  keep-alive timeout.

- Improved type hint annotations for invoker decorators.

- Preparations to be able to loosen dependencies and in the future make
  the related packages into optional extras instead.

- Printed hints (in development) on missing packages that haven't been
  installed or couldn't be imported and in turn causing fatal errors.


0.19.2 (2020-10-27)
-------------------

- Added support for ``aiohttp`` 3.7.x.


0.19.1 (2020-10-26)
-------------------

- Documentation related updates. External documentation is available at
  https://tomodachi.dev/docs.


0.19.0 (2020-10-23)
-------------------

- Note: This is a rather large release with a lot of updates. Also, this
  release includes a lot of improvements to be able to quicker implement
  features for the future and modernizes a lot of the build, testing and
  linting steps to be on par with cutting edge Python development.

- ``@tomodachi.aws_sns_sqs`` and ``@tomodachi.amqp`` decorators has
  changed the default value of the ``competing`` keyword-argument to
  ``True``. Note that this is a change in default behaviour and may be a
  breaking change if "non-competing" services were used. This change was
  triggered in an attempt to make the API more clear and use more
  common default values. It's rare that a non-shared queue would be used
  for service replicas of the same type in a distributed architecture.

- The ``@tomodachi.aws_sns_sqs`` decorator can now specify a
  ``filter_policy`` which will be applied on the SNS subscription (for
  the specified topic and queue) as the ``"FilterPolicy`` attribute.
  This will apply a filter on SNS messages using the chosen "message
  attributes" and/or their values specified in the filter.
  Example: A filter policy value of
  ``{"event": ["order_paid"], "currency": ["EUR", "USD"]}``
  would set up the SNS subscription to receive messages on the topic
  only where the message attribute ``"event"`` is ``"order_paid"``
  and the ``"currency"`` value is either ``"EUR"`` or ``"USD"``.
  If ``filter_policy`` is not specified as an argument, the
  queue will receive messages on the topic as per already specified if
  using an existing subscription, or receive all messages on the topic
  if a new subscription is set up (default).
  Changing the ``filter_policy`` on an existing subscription may take
  several minutes to propagate. Read more about the filter policy format
  on AWS, since it doesn't follow the same pattern as specifying message
  attributes. https://docs.aws.amazon.com/sns/latest/dg/sns-subscription-filter-policies.html

- Related to the above mentioned filter policy, the ``aws_sns_sqs_publish``
  function has also been updated with the possibility to specify said
  "message attributes" using the ``message_attributes`` keyword
  argument. Values should be specified as a simple ``dict`` with keys
  and values. Example:
  ``{"event": "order_paid", "paid_amount": 100, "currency": "EUR"}``.

- The event loop that the process will execute on can now be specified
  on startup using ``--loop [auto|asyncio|uvloop]``, currently the ``auto``
  (or ``default``) value will use Python's builtin ``asyncio`` event loop.

- Fixes a bug that could cause a termination signal to stop the service
  in the middle of processing a message received via AWS SQS. The service
  will now await currently executing tasks before finally shutting down.

- Added SSL and virtualhost settings to AMQP transport, as well as
  additional configuration options which can be passed via
  ``options.amqp.virtualhost``, ``options.amqp.ssl`` and
  ``options.amqp.heartbeat``. (github: **xdmiodz**)

- HTTP server functionality, which is based on ``aiohttp``, can now be
  configured to allow keep-alive connections by specifying the
  ``options.http.keepalive_timeout`` config value.

- Service termination for HTTP based services will now correctly await
  started tasks from clients that has disconnected before receiving
  the response.

- Functions decorated with ``@tomodachi.aws_sns_sqs`` will now be called
  with the ``queue_url``, ``receipt_handle`` and ``message_attributes``
  keyword arguments if specified in the function signature.
  These can be used to update the visibility timeouts, among other things.

- The ``message_protocol`` value that can be specified on service classes
  has been renamed to ``message_envelope`` and the two example
  implementations ``JsonBase`` and ``ProtobufBase`` has been moved from
  ``tomodachi.protocol`` to ``tomodachi.envelope``. The previous imports
  and service attribute is deprecated, but can still be used. Likewise
  the optional ``message_protocol`` keyword argument passed to
  ``@tomodachi.aws_sns_sqs``, ``@tomodachi.amqp``,
  ``aws_sns_sqs_publish``, ``amqp_publish`` is renamed to
  ``message_envelope``.

- The argument to specify ``message_envelope`` on the
  ``@tomodachi.aws_sns_sqs`` and ``@tomodachi.amqp`` decorators is now
  keyword only.

- The arguments to specify ``message_envelope`` and ``topic_prefix`` to
  ``aws_sns_sqs_publish`` is now keyword only.

- The arguments to specify ``message_envelope`` and ``routing_key_prefix``
  to ``amqp_publish`` is now keyword only.

- ``uvloop`` is now an optional installation.

- More verbose output when waiting for active tasks during termination.

- Added ``tomodachi.get_execution_context()`` that holds metadata about
  the service execution that can be used for debugging purposes or be
  sent to application monitoring platforms such as Sentry or to be
  included in custom log output for log search indexing. The
  ``tomodachi.get_execution_context()`` function returns a ``dict``
  with installed package versions of some key dependencies, function
  call counters of different types, etc.

- Refactoring and updates to code formatting, now using Black code style.

- Updated startup output with additional information about the running
  process, including versions, etc.

- Overall updated documentation and improved examples around running services
  within Docker.

- ``requirements.txt`` is no more and has been replaced with
  ``pyproject.toml`` with a Poetry section together with the ``poetry.lock``.

- Replaced Travis CI with GitHub actions.

- Replaced py-up with GitHub's dependabot, which as of recently also
  supports Poetry's lock files.

- Added support for ``aiohttp`` 3.6.x.

- Added support for ``aiobotocore`` 1.x.x.

- Added ``aiodns`` as an optional installation, as it's recommended for
  running DNS resolution on the event loop when using ``aiohttp``.

- Updated classifiers for support of Python 3.9.

- Dropped support for Python 3.6.

- The service class decorator ``@tomodachi.service`` is now considered
  deprecated and the service classes should inherit from the
  ``tomodachi.Service`` class instead. This also works better with
  type-hinting, which currently cannot handle decorators that
  modify a class.

- The ``name`` attribute is no longer required on the service classes
  and if not specified the value will now instead default to
  ``"service"``.


0.18.0 (2020-09-15)
-------------------

- Changed the order of when to execute the service's own
  ``_stop_service()`` function, to always run after active HTTP
  requests has finished executing, as well as awaiting ongoing AMQP
  before finally running the user defined function.


0.17.1 (2020-06-16)
-------------------

- Updated generated proto class using protoc 3.12.2 for messages
  using proto envelope, which should solve some deprecation
  warnings.


0.17.0 (2020-06-16)
-------------------

- Proper support for Python 3.8. Now correctly handles
  ``CancelledError`` exceptions that previously sent a lot of
  unwanted output on service shutdown or restart.

- Updated dependencies across the board, utilizing
  package versions that supports Python 3.8.

- Dropped support for Python 3.5.

- Now gracefully handles shutdown for HTTP based services,
  by awaiting active requests and giving them time to finish.
  By default the ongoing HTTP requests will have 30 seconds to
  complete their work, which can also be configured via
  ``options.http.termination_grace_period_seconds``.

- Taking steps into making the codebase following more modern
  patterns. Additional updates to be followed in a later release.


0.16.6 (2020-02-25)
-------------------

- Removes the dependency on ``ujson``.


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

- Added ``@websocket`` as a decorator type for handling websockets. A function
  call should return two callables which will be used for receiving messages
  through the socket and as a way to notify about the closure of the socket.


0.6.5 (2018-01-16)
------------------

- Updated ``aiohttp`` to latest version which solves incompabilities with ``yarl``.


0.6.4 (2018-01-15)
------------------

- Added a stricter dependency check for ``yarl``.


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

- Introduced new options for AWS SNS/SQS transport to use ``aws_endpoint_urls``
  for ``sns`` and ``sqs`` if the user wishes to connect to other endpoints and the
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
