# This is a set of Python modules that shouldn't be unloaded during hot reload.

SAFE_MODULES = {
    "__future__",
    "__main__",
    "_abc",
    "_asyncio",
    "_bisect",
    "_blake2",
    "_bootlocale",
    "_bz2",
    "_cares",
    "_cares.lib",
    "_cffi_backend",
    "_codecs",
    "_collections",
    "_collections_abc",
    "_compat_pickle",
    "_compression",
    "_contextvars",
    "_ctypes",
    "_cython_0_29_21",
    "_datetime",
    "_decimal",
    "_elementtree",
    "_frozen_importlib",
    "_frozen_importlib_external",
    "_functools",
    "_hashlib",
    "_heapq",
    "_imp",
    "_io",
    "_json",
    "_locale",
    "_lzma",
    "_markupbase",
    "_opcode",
    "_operator",
    "_pickle",
    "_posixsubprocess",
    "_queue",
    "_random",
    "_sha3",
    "_sha512",
    "_signal",
    "_sitebuiltins",
    "_socket",
    "_sre",
    "_ssl",
    "_stat",
    "_string",
    "_struct",
    "_thread",
    "_uuid",
    "_warnings",
    "_weakref",
    "_weakrefset",
    "abc",
    "aioamqp",
    "aioamqp.channel",
    "aioamqp.constants",
    "aioamqp.envelope",
    "aioamqp.exceptions",
    "aioamqp.frame",
    "aioamqp.properties",
    "aioamqp.protocol",
    "aioamqp.version",
    "aiobotocore",
    "aiobotocore._endpoint_helpers",
    "aiobotocore.args",
    "aiobotocore.client",
    "aiobotocore.config",
    "aiobotocore.credentials",
    "aiobotocore.endpoint",
    "aiobotocore.eventstream",
    "aiobotocore.hooks",
    "aiobotocore.paginate",
    "aiobotocore.parsers",
    "aiobotocore.response",
    "aiobotocore.session",
    "aiobotocore.signers",
    "aiobotocore.utils",
    "aiobotocore.waiter",
    "aiodns",
    "aiodns.error",
    "aiohttp",
    "aiohttp._frozenlist",
    "aiohttp._helpers",
    "aiohttp._http_parser",
    "aiohttp._http_writer",
    "aiohttp._websocket",
    "aiohttp.abc",
    "aiohttp.base_protocol",
    "aiohttp.client",
    "aiohttp.client_exceptions",
    "aiohttp.client_proto",
    "aiohttp.client_reqrep",
    "aiohttp.client_ws",
    "aiohttp.connector",
    "aiohttp.cookiejar",
    "aiohttp.formdata",
    "aiohttp.frozenlist",
    "aiohttp.hdrs",
    "aiohttp.helpers",
    "aiohttp.http",
    "aiohttp.http_exceptions",
    "aiohttp.http_parser",
    "aiohttp.http_websocket",
    "aiohttp.http_writer",
    "aiohttp.locks",
    "aiohttp.log",
    "aiohttp.multipart",
    "aiohttp.payload",
    "aiohttp.payload_streamer",
    "aiohttp.resolver",
    "aiohttp.signals",
    "aiohttp.streams",
    "aiohttp.tcp_helpers",
    "aiohttp.tracing",
    "aiohttp.typedefs",
    "aiohttp.web",
    "aiohttp.web_app",
    "aiohttp.web_exceptions",
    "aiohttp.web_fileresponse",
    "aiohttp.web_log",
    "aiohttp.web_middlewares",
    "aiohttp.web_protocol",
    "aiohttp.web_request",
    "aiohttp.web_response",
    "aiohttp.web_routedef",
    "aiohttp.web_runner",
    "aiohttp.web_server",
    "aiohttp.web_urldispatcher",
    "aiohttp.web_ws",
    "aioitertools",
    "aioitertools.__version__",
    "aioitertools.asyncio",
    "aioitertools.builtins",
    "aioitertools.helpers",
    "aioitertools.itertools",
    "aioitertools.types",
    "argparse",
    "async_timeout",
    "asyncio",
    "asyncio.base_events",
    "asyncio.base_futures",
    "asyncio.base_subprocess",
    "asyncio.base_tasks",
    "asyncio.constants",
    "asyncio.coroutines",
    "asyncio.events",
    "asyncio.exceptions",
    "asyncio.format_helpers",
    "asyncio.futures",
    "asyncio.locks",
    "asyncio.log",
    "asyncio.protocols",
    "asyncio.queues",
    "asyncio.runners",
    "asyncio.selector_events",
    "asyncio.sslproto",
    "asyncio.staggered",
    "asyncio.streams",
    "asyncio.subprocess",
    "asyncio.tasks",
    "asyncio.transports",
    "asyncio.trsock",
    "asyncio.unix_events",
    "atexit",
    "attr",
    "attr._compat",
    "attr._config",
    "attr._funcs",
    "attr._make",
    "attr._next_gen",
    "attr._version_info",
    "attr.converters",
    "attr.exceptions",
    "attr.filters",
    "attr.setters",
    "attr.validators",
    "base64",
    "binascii",
    "bisect",
    "botocore",
    "botocore.args",
    "botocore.auth",
    "botocore.awsrequest",
    "botocore.client",
    "botocore.compat",
    "botocore.config",
    "botocore.configloader",
    "botocore.configprovider",
    "botocore.credentials",
    "botocore.discovery",
    "botocore.docs",
    "botocore.docs.bcdoc",
    "botocore.docs.bcdoc.docstringparser",
    "botocore.docs.bcdoc.restdoc",
    "botocore.docs.bcdoc.style",
    "botocore.docs.client",
    "botocore.docs.docstring",
    "botocore.docs.example",
    "botocore.docs.method",
    "botocore.docs.paginator",
    "botocore.docs.params",
    "botocore.docs.service",
    "botocore.docs.shape",
    "botocore.docs.sharedexample",
    "botocore.docs.utils",
    "botocore.docs.waiter",
    "botocore.endpoint",
    "botocore.errorfactory",
    "botocore.eventstream",
    "botocore.exceptions",
    "botocore.handlers",
    "botocore.history",
    "botocore.hooks",
    "botocore.httpsession",
    "botocore.loaders",
    "botocore.model",
    "botocore.monitoring",
    "botocore.paginate",
    "botocore.parsers",
    "botocore.regions",
    "botocore.response",
    "botocore.retries",
    "botocore.retries.adaptive",
    "botocore.retries.base",
    "botocore.retries.bucket",
    "botocore.retries.quota",
    "botocore.retries.special",
    "botocore.retries.standard",
    "botocore.retries.throttling",
    "botocore.retryhandler",
    "botocore.serialize",
    "botocore.session",
    "botocore.signers",
    "botocore.translate",
    "botocore.utils",
    "botocore.validate",
    "botocore.vendored",
    "botocore.vendored.requests",
    "botocore.vendored.requests.exceptions",
    "botocore.vendored.requests.packages",
    "botocore.vendored.requests.packages.urllib3",
    "botocore.vendored.requests.packages.urllib3.exceptions",
    "botocore.vendored.six",
    "botocore.vendored.six.moves",
    "botocore.vendored.six.moves.urllib",
    "botocore.vendored.six.moves.urllib.request",
    "botocore.vendored.six.moves.urllib_parse",
    "botocore.waiter",
    "builtins",
    "bz2",
    "calendar",
    "cchardet",
    "cchardet._cchardet",
    "cchardet.version",
    "certifi",
    "certifi.core",
    "cgi",
    "codecs",
    "collections",
    "collections.abc",
    "colorama",
    "colorama.ansi",
    "colorama.ansitowin32",
    "colorama.initialise",
    "colorama.win32",
    "colorama.winterm",
    "concurrent",
    "concurrent.futures",
    "concurrent.futures._base",
    "contextlib",
    "contextvars",
    "copy",
    "copyreg",
    "ctypes",
    "ctypes._endian",
    "cython_runtime",
    "datetime",
    "dateutil",
    "dateutil._common",
    "dateutil._version",
    "dateutil.parser",
    "dateutil.parser._parser",
    "dateutil.parser.isoparser",
    "dateutil.relativedelta",
    "dateutil.tz",
    "dateutil.tz._common",
    "dateutil.tz._factories",
    "dateutil.tz.tz",
    "decimal",
    "dis",
    "email",
    "email._encoded_words",
    "email._parseaddr",
    "email._policybase",
    "email.base64mime",
    "email.charset",
    "email.encoders",
    "email.errors",
    "email.feedparser",
    "email.header",
    "email.iterators",
    "email.message",
    "email.parser",
    "email.quoprimime",
    "email.utils",
    "encodings",
    "encodings.aliases",
    "encodings.latin_1",
    "encodings.utf_8",
    "enum",
    "errno",
    "fnmatch",
    "functools",
    "genericpath",
    "getopt",
    "getpass",
    "gettext",
    "google",
    "google.protobuf",
    "google.protobuf.message",
    "grp",
    "hashlib",
    "heapq",
    "hmac",
    "html",
    "html.entities",
    "html.parser",
    "http",
    "http.client",
    "http.cookies",
    "http.server",
    "idna",
    "idna.core",
    "idna.idnadata",
    "idna.intranges",
    "idna.package_data",
    "importlib",
    "importlib._bootstrap",
    "importlib._bootstrap_external",
    "importlib.abc",
    "importlib.machinery",
    "importlib.resources",
    "importlib.util",
    "inspect",
    "io",
    "ipaddress",
    "itertools",
    "jmespath",
    "jmespath.ast",
    "jmespath.compat",
    "jmespath.exceptions",
    "jmespath.functions",
    "jmespath.lexer",
    "jmespath.parser",
    "jmespath.visitor",
    "json",
    "json.decoder",
    "json.encoder",
    "json.scanner",
    "keyword",
    "linecache",
    "locale",
    "logging",
    "logging.handlers",
    "lzma",
    "marshal",
    "math",
    "mimetypes",
    "multidict",
    "multidict._abc",
    "multidict._compat",
    "multidict._multidict",
    "multidict._multidict_base",
    "netrc",
    "ntpath",
    "numbers",
    "opcode",
    "operator",
    "os",
    "os.path",
    "pamqp",
    "pamqp.body",
    "pamqp.constants",
    "pamqp.decode",
    "pamqp.encode",
    "pamqp.exceptions",
    "pamqp.frame",
    "pamqp.header",
    "pamqp.heartbeat",
    "pamqp.specification",
    "pathlib",
    "pickle",
    "platform",
    "posix",
    "posixpath",
    "pwd",
    "pycares",
    "pycares._cares",
    "pycares._version",
    "pycares.errno",
    "pycares.utils",
    "pyexpat",
    "pyexpat.errors",
    "pyexpat.model",
    "pytz",
    "pytz.exceptions",
    "pytz.lazy",
    "pytz.tzfile",
    "pytz.tzinfo",
    "queue",
    "quopri",
    "random",
    "re",
    "reprlib",
    "select",
    "selectors",
    "sentry_sdk",
    "sentry_sdk._compat",
    "sentry_sdk._functools",
    "sentry_sdk._queue",
    "sentry_sdk._types",
    "sentry_sdk.api",
    "sentry_sdk.attachments",
    "sentry_sdk.client",
    "sentry_sdk.consts",
    "sentry_sdk.debug",
    "sentry_sdk.envelope",
    "sentry_sdk.hub",
    "sentry_sdk.integrations",
    "sentry_sdk.integrations._wsgi_common",
    "sentry_sdk.integrations.aiohttp",
    "sentry_sdk.integrations.argv",
    "sentry_sdk.integrations.atexit",
    "sentry_sdk.integrations.aws_lambda",
    "sentry_sdk.integrations.beam",
    "sentry_sdk.integrations.boto3",
    "sentry_sdk.integrations.celery",
    "sentry_sdk.integrations.chalice",
    "sentry_sdk.integrations.dedupe",
    "sentry_sdk.integrations.excepthook",
    "sentry_sdk.integrations.flask",
    "sentry_sdk.integrations.gcp",
    "sentry_sdk.integrations.logging",
    "sentry_sdk.integrations.modules",
    "sentry_sdk.integrations.pyramid",
    "sentry_sdk.integrations.redis",
    "sentry_sdk.integrations.sanic",
    "sentry_sdk.integrations.serverless",
    "sentry_sdk.integrations.sqlalchemy",
    "sentry_sdk.integrations.stdlib",
    "sentry_sdk.integrations.threading",
    "sentry_sdk.integrations.tornado",
    "sentry_sdk.integrations.trytond",
    "sentry_sdk.integrations.wsgi",
    "sentry_sdk.scope",
    "sentry_sdk.serializer",
    "sentry_sdk.session",
    "sentry_sdk.sessions",
    "sentry_sdk.tracing",
    "sentry_sdk.transport",
    "sentry_sdk.utils",
    "sentry_sdk.worker",
    "shlex",
    "shutil",
    "signal",
    "site",
    "six",
    "six.moves",
    "socket",
    "socketserver",
    "sre_compile",
    "sre_constants",
    "sre_parse",
    "ssl",
    "stat",
    "string",
    "struct",
    "subprocess",
    "sys",
    "tempfile",
    "termios",
    "threading",
    "time",
    "token",
    "tokenize",
    "tomodachi",
    "tomodachi.__main__",
    "tomodachi.__version__",
    "tomodachi._importer",
    "tomodachi.cli",
    "tomodachi.config",
    "tomodachi.container",
    "tomodachi.discovery",
    "tomodachi.discovery.aws_sns_registration",
    "tomodachi.discovery.dummy_registry",
    "tomodachi.envelope",
    "tomodachi.envelope.json_base",
    "tomodachi.envelope.proto_build",
    "tomodachi.envelope.proto_build.protobuf",
    "tomodachi.envelope.proto_build.protobuf.sns_sqs_message_pb2",
    "tomodachi.envelope.protobuf_base",
    "tomodachi.helpers",
    "tomodachi.helpers.aiobotocore_connector",
    "tomodachi.helpers.banner",
    "tomodachi.helpers.crontab",
    "tomodachi.helpers.dict",
    "tomodachi.helpers.execution_context",
    "tomodachi.helpers.logging",
    "tomodachi.helpers.middleware",
    "tomodachi.helpers.safe_modules",
    "tomodachi.importer",
    "tomodachi.invoker",
    "tomodachi.invoker.base",
    "tomodachi.invoker.decorator",
    "tomodachi.launcher",
    "tomodachi.logging",
    "tomodachi.options",
    "tomodachi.options.definitions",
    "tomodachi.options.interface",
    "tomodachi.protocol",
    "tomodachi.protocol.json_base",
    "tomodachi.protocol.proto_build",
    "tomodachi.protocol.proto_build.protobuf",
    "tomodachi.protocol.proto_build.protobuf.sns_sqs_message_pb2",
    "tomodachi.protocol.protobuf_base",
    "tomodachi.run",
    "tomodachi.run.__main__",
    "tomodachi.transport",
    "tomodachi.transport.amqp",
    "tomodachi.transport.aws_sns_sqs",
    "tomodachi.transport.awssnssqs",
    "tomodachi.transport.http",
    "tomodachi.transport.schedule",
    "tomodachi.watcher",
    "traceback",
    "types",
    "typing",
    "typing.io",
    "typing.re",
    "typing_extensions",
    "tzlocal",
    "tzlocal.unix",
    "tzlocal.utils",
    "unicodedata",
    "urllib",
    "urllib.error",
    "urllib.parse",
    "urllib.request",
    "urllib.response",
    "urllib3",
    "urllib3._collections",
    "urllib3._version",
    "urllib3.connection",
    "urllib3.connectionpool",
    "urllib3.contrib",
    "urllib3.contrib._appengine_environ",
    "urllib3.exceptions",
    "urllib3.fields",
    "urllib3.filepost",
    "urllib3.packages",
    "urllib3.packages.six",
    "urllib3.packages.six.moves",
    "urllib3.packages.six.moves.http_client",
    "urllib3.packages.six.moves.urllib",
    "urllib3.packages.six.moves.urllib.parse",
    "urllib3.packages.ssl_match_hostname",
    "urllib3.poolmanager",
    "urllib3.request",
    "urllib3.response",
    "urllib3.util",
    "urllib3.util.connection",
    "urllib3.util.queue",
    "urllib3.util.request",
    "urllib3.util.response",
    "urllib3.util.retry",
    "urllib3.util.ssl_",
    "urllib3.util.timeout",
    "urllib3.util.url",
    "urllib3.util.wait",
    "uu",
    "uuid",
    "warnings",
    "weakref",
    "wrapt",
    "wrapt.decorators",
    "wrapt.importer",
    "wrapt.wrappers",
    "xml",
    "xml.etree",
    "xml.etree.ElementPath",
    "xml.etree.ElementTree",
    "xml.etree.cElementTree",
    "yarl",
    "yarl._quoting",
    "yarl._quoting_c",
    "yarl._url",
    "zipimport",
    "zlib",
}
