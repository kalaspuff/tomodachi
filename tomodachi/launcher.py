import asyncio
import datetime
import importlib
import logging
import os
import platform
import signal
import sys
import time
from typing import Any, Dict, List, Optional, Set, Union, cast

import tomodachi.__version__
import tomodachi.container
import tomodachi.importer
import tomodachi.invoker
from tomodachi.container import ServiceContainer
from tomodachi.helpers.execution_context import clear_execution_context, clear_services, set_execution_context
from tomodachi.importer import ServiceImporter

try:
    CancelledError = asyncio.exceptions.CancelledError  # type: ignore
except Exception:

    class CancelledError(Exception):  # type: ignore
        pass


class ServiceLauncher(object):
    _close_waiter: Optional[asyncio.Future] = None
    _stopped_waiter: Optional[asyncio.Future] = None
    restart_services = False
    services: Set = set()

    @classmethod
    def run_until_complete(
        cls,
        service_files: Union[List, set],
        configuration: Optional[Dict] = None,
        watcher: Any = None,
    ) -> None:
        def stop_services() -> None:
            asyncio.ensure_future(_stop_services())

        async def _stop_services() -> None:
            if cls._close_waiter and not cls._close_waiter.done():
                cls._close_waiter.set_result(None)
                for service in cls.services:
                    try:
                        service.stop_service()
                    except Exception:
                        pass
                if cls._stopped_waiter:
                    cls._stopped_waiter.set_result(None)
            if cls._stopped_waiter:
                await cls._stopped_waiter

        def sigintHandler(*args: Any) -> None:
            sys.stdout.write("\b\b\r")
            sys.stdout.flush()
            logging.getLogger("system").warning("Received <ctrl+c> interrupt [SIGINT]")
            cls.restart_services = False

        def sigtermHandler(*args: Any) -> None:
            logging.getLogger("system").warning("Received termination signal [SIGTERM]")
            cls.restart_services = False

        logging.basicConfig(level=logging.DEBUG)

        loop = asyncio.get_event_loop()
        if loop and loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for signame in ("SIGINT", "SIGTERM"):
            loop.add_signal_handler(getattr(signal, signame), stop_services)

        signal.siginterrupt(signal.SIGTERM, False)
        signal.siginterrupt(signal.SIGUSR1, False)
        signal.signal(signal.SIGINT, sigintHandler)
        signal.signal(signal.SIGTERM, sigtermHandler)

        if watcher:

            async def _watcher_restart(updated_files: Union[List, set]) -> None:
                cls.restart_services = True

                for file in service_files:
                    try:
                        ServiceImporter.import_service_file(file)
                    except (SyntaxError, IndentationError) as e:
                        logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                        logging.getLogger("watcher.restart").warning("Service cannot restart due to errors")
                        cls.restart_services = False
                        return

                pre_import_current_modules = [m for m in sys.modules.keys()]
                cwd = os.getcwd()
                for file in updated_files:
                    if file.lower().endswith(".py"):
                        module_name = file[:-3].replace("/", ".")
                        module_name_full_path = "{}/{}".format(os.path.realpath(cwd), file)[:-3].replace("/", ".")
                        try:
                            for m in pre_import_current_modules:
                                if m == module_name or (len(m) > len(file) and module_name_full_path.endswith(m)):
                                    ServiceImporter.import_module(file)
                        except (SyntaxError, IndentationError) as e:
                            logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                            logging.getLogger("watcher.restart").warning("Service cannot restart due to errors")
                            cls.restart_services = False
                            return

                logging.getLogger("watcher.restart").warning("Restarting services")
                stop_services()

            watcher_future = loop.run_until_complete(watcher.watch(loop=loop, callback_func=_watcher_restart))

        cls.restart_services = True
        init_modules = [m for m in sys.modules.keys()]
        safe_modules = [
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
            "tomodachi.__version__",
            "tomodachi.cli",
            "tomodachi.config",
            "tomodachi.container",
            "tomodachi.envelope",
            "tomodachi.envelope.json_base",
            "tomodachi.protocol.json_base",
            "tomodachi.envelope.proto_build",
            "tomodachi.envelope.proto_build.protobuf",
            "tomodachi.envelope.proto_build.protobuf.sns_sqs_message_pb2",
            "tomodachi.envelope.protobuf_base",
            "tomodachi.helpers",
            "tomodachi.helpers.crontab",
            "tomodachi.helpers.dict",
            "tomodachi.helpers.execution_context",
            "tomodachi.helpers.logging",
            "tomodachi.helpers.middleware",
            "tomodachi.importer",
            "tomodachi.invoker",
            "tomodachi.invoker.base",
            "tomodachi.invoker.decorator",
            "tomodachi.launcher",
            "tomodachi.protocol",
            "tomodachi.protocol.json_base",
            "tomodachi.protocol.protobuf_base",
            "tomodachi.transport",
            "tomodachi.transport.amqp",
            "tomodachi.transport.aws_sns_sqs",
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
        ]

        restarting = False
        while cls.restart_services:
            init_timestamp = time.time()
            init_timestamp_str = datetime.datetime.utcfromtimestamp(init_timestamp).isoformat() + "Z"

            process_id = os.getpid()

            event_loop_alias = ""
            event_loop_version = ""
            try:
                if "uvloop." in str(loop.__class__):
                    event_loop_alias = "uvloop"
                    import uvloop  # noqa  # isort:skip

                    event_loop_version = str(uvloop.__version__)
                elif "asyncio." in str(loop.__class__):
                    event_loop_alias = "asyncio"
                else:
                    event_loop_alias = "{}.{}".format(loop.__class__.__module__, loop.__class__.__name__)
            except Exception:
                event_loop_alias = str(loop)

            clear_services()
            clear_execution_context()
            set_execution_context(
                {
                    "tomodachi_version": tomodachi.__version__,
                    "python_version": platform.python_version(),
                    "system_platform": platform.system(),
                    "process_id": process_id,
                    "init_timestamp": init_timestamp_str,
                    "event_loop": event_loop_alias,
                }
            )

            if event_loop_alias == "uvloop" and event_loop_version:
                set_execution_context(
                    {
                        "uvloop_version": event_loop_version,
                    }
                )

            if watcher:
                tz: Any = None
                utc_tz: Any = None

                try:
                    import pytz  # noqa  # isort:skip
                    import tzlocal  # noqa  # isort:skip

                    utc_tz = pytz.UTC
                    try:
                        tz = tzlocal.get_localzone()
                        if not tz:
                            tz = pytz.UTC
                    except Exception:
                        tz = pytz.UTC
                except Exception:
                    pass

                init_local_datetime = (
                    datetime.datetime.fromtimestamp(init_timestamp)
                    if tz and tz is not utc_tz and str(tz) != "UTC"
                    else datetime.datetime.utcfromtimestamp(init_timestamp)
                )

                print("---")
                print("Starting tomodachi services (pid: {}) ...".format(process_id))
                for file in service_files:
                    print("* {}".format(file))

                print()
                print(
                    "Current version: tomodachi {} on Python {}".format(
                        tomodachi.__version__, platform.python_version()
                    )
                )
                print(
                    "Event loop implementation: {}{}".format(
                        event_loop_alias, " {}".format(event_loop_version) if event_loop_version else ""
                    )
                )
                if tz:
                    print("Local time: {} {}".format(init_local_datetime.strftime("%B %d, %Y - %H:%M:%S,%f"), str(tz)))
                print("Timestamp in UTC: {}".format(init_timestamp_str))
                print()
                print("File watcher is active - code changes will automatically restart services")
                print("Quit running services with <ctrl+c>")
                print()

            cls._close_waiter = asyncio.Future()
            cls._stopped_waiter = asyncio.Future()
            cls.restart_services = False

            try:
                cls.services = set(
                    [
                        ServiceContainer(ServiceImporter.import_service_file(file), configuration)
                        for file in service_files
                    ]
                )
                result = loop.run_until_complete(
                    asyncio.wait([asyncio.ensure_future(service.run_until_complete()) for service in cls.services])
                )
                exception = [v.exception() for v in [value for value in result if value][0] if v.exception()]
                if exception:
                    raise cast(Exception, exception[0])
            except tomodachi.importer.ServicePackageError:
                pass
            except Exception as e:
                logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))

                if isinstance(e, ModuleNotFoundError):  # pragma: no cover
                    missing_module_name = str(getattr(e, "name", None) or "")
                    if missing_module_name:
                        color = ""
                        color_reset = ""
                        try:
                            import colorama  # noqa  # isort:skip

                            color = colorama.Fore.WHITE + colorama.Back.RED
                            color_reset = colorama.Style.RESET_ALL
                        except Exception:
                            pass

                        print("")
                        print(
                            "{}[fatal error] The '{}' package is missing or cannot be imported.{}".format(
                                color, missing_module_name, color_reset
                            )
                        )
                        print("")

                if restarting:
                    logging.getLogger("watcher.restart").warning("Service cannot restart due to errors")
                    logging.getLogger("watcher.restart").warning("Trying again in 1.5 seconds")
                    loop.run_until_complete(asyncio.wait([asyncio.sleep(1.5)]))
                    if cls._close_waiter and not cls._close_waiter.done():
                        cls.restart_services = True
                    else:
                        for signame in ("SIGINT", "SIGTERM"):
                            loop.remove_signal_handler(getattr(signal, signame))
                else:
                    for signame in ("SIGINT", "SIGTERM"):
                        loop.remove_signal_handler(getattr(signal, signame))

            current_modules = [m for m in sys.modules.keys()]
            for m in current_modules:
                if m not in init_modules and m not in safe_modules:
                    del sys.modules[m]

            importlib.reload(tomodachi.container)
            importlib.reload(tomodachi.invoker)
            importlib.reload(tomodachi.invoker.base)
            importlib.reload(tomodachi.importer)

            restarting = True

        if watcher:
            if not watcher_future.done():
                try:
                    watcher_future.set_result(None)
                except RuntimeError:  # pragma: no cover
                    watcher_future.cancel()
                if not watcher_future.done():  # pragma: no cover
                    try:
                        loop.run_until_complete(watcher_future)
                    except (Exception, CancelledError):
                        pass
