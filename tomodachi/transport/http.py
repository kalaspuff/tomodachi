import asyncio
import functools
import inspect
import ipaddress
import logging
import os
import pathlib
import re
import time
import uuid
from logging.handlers import WatchedFileHandler
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, SupportsInt, Tuple, Union  # noqa

import colorama
from aiohttp import WSMsgType
from aiohttp import __version__ as aiohttp_version
from aiohttp import hdrs, web, web_protocol, web_server, web_urldispatcher
from aiohttp.helpers import BasicAuth
from aiohttp.http import HttpVersion
from aiohttp.streams import EofStream
from aiohttp.web_fileresponse import FileResponse
from multidict import CIMultiDict, CIMultiDictProxy

from tomodachi.helpers.dict import merge_dicts
from tomodachi.helpers.execution_context import (
    decrease_execution_context_value,
    increase_execution_context_value,
    set_execution_context,
)
from tomodachi.helpers.middleware import execute_middlewares
from tomodachi.invoker import Invoker

try:
    CancelledError = asyncio.exceptions.CancelledError  # type: ignore
except Exception:

    class CancelledError(Exception):  # type: ignore
        pass


class HttpException(Exception):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._log_level = kwargs.get("log_level") if kwargs and kwargs.get("log_level") else "INFO"


class RequestHandler(web_protocol.RequestHandler):  # type: ignore
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._server_header = kwargs.pop("server_header", None) if kwargs else None
        self._access_log = kwargs.pop("access_log", None) if kwargs else None
        super().__init__(*args, **kwargs)  # type: ignore

    @staticmethod
    def get_request_ip(request: Any, context: Optional[Dict] = None) -> Optional[str]:
        if request._cache.get("request_ip"):
            return str(request._cache.get("request_ip", ""))

        if request.transport:
            if not context:
                context = {}
            real_ip_header = context.get("options", {}).get("http", {}).get("real_ip_header", "X-Forwarded-For")
            real_ip_from = context.get("options", {}).get("http", {}).get("real_ip_from", [])
            if isinstance(real_ip_from, str):
                real_ip_from = [real_ip_from]

            peername = request.transport.get_extra_info("peername")
            request_ip = None
            if peername:
                request_ip, _ = peername
            if (
                real_ip_header
                and real_ip_from
                and request.headers.get(real_ip_header)
                and request_ip
                and len(real_ip_from)
            ):
                if any([ipaddress.ip_address(request_ip) in ipaddress.ip_network(cidr) for cidr in real_ip_from]):
                    request_ip = request.headers.get(real_ip_header).split(",")[0].strip().split(" ")[0].strip()

            request._cache["request_ip"] = request_ip
            return request_ip

        return None

    @staticmethod
    def colorize_status(text: Optional[Union[str, int]], status: Optional[Union[str, int, bool]] = False) -> str:
        if status is False:
            status = text
        status_code = str(status) if status else None
        if status_code and not logging.getLogger("transport.http").handlers:
            output_text = str(text) if text else ""
            color = None

            if status_code == "101":
                color = colorama.Fore.CYAN
            elif status_code[0] == "2":
                color = colorama.Fore.GREEN
            elif status_code[0] == "3" or status_code == "499":
                color = colorama.Fore.YELLOW
            elif status_code[0] == "4":
                color = colorama.Fore.RED
            elif status_code[0] == "5":
                color = colorama.Fore.WHITE + colorama.Back.RED

            if color:
                return "{}{}{}".format(color, output_text, colorama.Style.RESET_ALL)
            return output_text

        return str(text) if text else ""

    def handle_error(
        self, request: Any, status: int = 500, exc: Any = None, message: Optional[str] = None
    ) -> web.Response:
        """Handle errors.

        Returns HTTP response with specific status code. Logs additional
        information. It always closes current connection."""
        if self.transport is None:
            # client has been disconnected during writing.
            if self._access_log:
                request_ip = RequestHandler.get_request_ip(request, None)
                version_string = None
                if isinstance(request.version, HttpVersion):
                    version_string = "HTTP/{}.{}".format(request.version.major, request.version.minor)
                logging.getLogger("transport.http").info(
                    '[{}] [{}] {} {} "{} {}{}{}" - {} "{}" -'.format(
                        RequestHandler.colorize_status("http", 499),
                        RequestHandler.colorize_status(499),
                        request_ip or "",
                        '"{}"'.format(request._cache["auth"].login.replace('"', ""))
                        if request._cache.get("auth") and getattr(request._cache.get("auth"), "login", None)
                        else "-",
                        request.method,
                        request.path,
                        "?{}".format(request.query_string) if request.query_string else "",
                        " {}".format(version_string) if version_string else "",
                        request.content_length if request.content_length is not None else "-",
                        request.headers.get("User-Agent", "").replace('"', ""),
                    )
                )

        headers = CIMultiDict({})  # type: CIMultiDict
        headers[hdrs.CONTENT_TYPE] = "text/plain; charset=utf-8"

        msg = "" if status == 500 or not message else message

        headers[hdrs.CONTENT_LENGTH] = str(len(msg))
        headers[hdrs.SERVER] = self._server_header or ""

        if isinstance(request.version, HttpVersion) and (request.version.major, request.version.minor) in (
            (1, 0),
            (1, 1),
        ):
            headers[hdrs.CONNECTION] = "close"

        resp = web.Response(
            status=status, text=msg, headers=headers  # type: ignore
        )  # type: web.Response
        resp.force_close()  # type: ignore

        # some data already got sent, connection is broken
        if request.writer.output_size > 0 or self.transport is None:
            self.force_close()  # type: ignore
        elif self.transport is not None:
            request_ip = RequestHandler.get_request_ip(request, None)
            if not request_ip:
                peername = request.transport.get_extra_info("peername")
                if peername:
                    request_ip, _ = peername
            if self._access_log:
                logging.getLogger("transport.http").info(
                    '[{}] [{}] {} {} "INVALID" {} - "" -'.format(
                        RequestHandler.colorize_status("http", status),
                        RequestHandler.colorize_status(status),
                        request_ip or "",
                        '"{}"'.format(request._cache["auth"].login.replace('"', ""))
                        if request._cache.get("auth") and getattr(request._cache.get("auth"), "login", None)
                        else "-",
                        len(msg),
                    )
                )

        return resp


class Server(web_server.Server):  # type: ignore
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._server_header = kwargs.pop("server_header", None) if kwargs else None
        self._access_log = kwargs.pop("access_log", None) if kwargs else None
        super().__init__(*args, **kwargs)  # type: ignore

    def __call__(self) -> RequestHandler:
        return RequestHandler(
            self, loop=self._loop, server_header=self._server_header, access_log=self._access_log, **self._kwargs
        )


class DynamicResource(web_urldispatcher.DynamicResource):  # type: ignore
    def __init__(self, pattern: Any, *, name: Optional[str] = None) -> None:
        self._routes = []  # type: List
        self._name = name
        self._pattern = pattern
        self._formatter = ""


class Response(object):
    def __init__(
        self,
        *,
        body: Optional[Union[bytes, str]] = None,
        status: int = 200,
        reason: Optional[str] = None,
        headers: Optional[Union[Dict, CIMultiDict, CIMultiDictProxy]] = None,
        content_type: Optional[str] = None,
        charset: Optional[str] = None,
    ) -> None:
        if headers is None:
            headers = CIMultiDict()
        elif not isinstance(headers, (CIMultiDict, CIMultiDictProxy)):
            headers = CIMultiDict(headers)

        self._body = body
        self._status = status
        self._reason = reason
        self._headers = headers
        self.content_type = content_type if hdrs.CONTENT_TYPE not in headers else None
        self.charset = charset if hdrs.CONTENT_TYPE not in headers else None

        self.missing_content_type = hdrs.CONTENT_TYPE not in headers and not content_type and not charset

    def get_aiohttp_response(
        self, context: Dict, default_charset: Optional[str] = None, default_content_type: Optional[str] = None
    ) -> web.Response:
        if self.missing_content_type:
            self.charset = default_charset
            self.content_type = default_content_type

        charset = self.charset
        if hdrs.CONTENT_TYPE in self._headers and ";" in self._headers[hdrs.CONTENT_TYPE]:
            try:
                charset = (
                    str([v for v in self._headers[hdrs.CONTENT_TYPE].split(";") if "charset=" in v][0])
                    .replace("charset=", "")
                    .strip()
                )
            except IndexError:
                pass
        elif hdrs.CONTENT_TYPE in self._headers and ";" not in self._headers[hdrs.CONTENT_TYPE]:
            charset = None

        if self._body and not isinstance(self._body, bytes) and charset:
            body = self._body
            try:
                body_value = body.encode(charset.lower())
            except (ValueError, LookupError, UnicodeEncodeError) as e:
                logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                raise web.HTTPInternalServerError() from e  # type: ignore
        elif self._body:
            body_value = self._body.encode() if not isinstance(self._body, bytes) else self._body
        else:
            body_value = b""

        response = web.Response(
            body=body_value,  # type: ignore
            status=self._status,
            reason=self._reason,
            headers=self._headers,
            content_type=self.content_type,
            charset=self.charset,
        )  # type: web.Response
        return response


class HttpTransport(Invoker):
    async def request_handler(
        cls: Any,
        obj: Any,
        context: Dict,
        func: Any,
        method: str,
        url: str,
        ignore_logging: Union[bool, List[int], Tuple[int]] = False,
        pre_handler_func: Optional[Callable] = None,
    ) -> Any:
        pattern = r"^{}$".format(re.sub(r"\$$", "", re.sub(r"^\^?(.*)$", r"\1", url)))
        compiled_pattern = re.compile(pattern)

        default_content_type = context.get("options", {}).get("http", {}).get("content_type", "text/plain")
        default_charset = context.get("options", {}).get("http", {}).get("charset", "utf-8")

        if default_content_type is not None and ";" in default_content_type:
            # for backwards compability
            try:
                default_charset = (
                    str([v for v in default_content_type.split(";") if "charset=" in v][0])
                    .replace("charset=", "")
                    .strip()
                )
                default_content_type = str([v for v in default_content_type.split(";")][0]).strip()
            except IndexError:
                pass

        async def handler(request: web.Request) -> Union[web.Response, web.FileResponse]:
            result = compiled_pattern.match(request.path)
            values = inspect.getfullargspec(func)
            kwargs = (
                {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults) :])}
                if values.defaults
                else {}
            )
            if result:
                for k, v in result.groupdict().items():
                    kwargs[k] = v

            @functools.wraps(func)
            async def routine_func(
                *a: Any, **kw: Any
            ) -> Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]:
                routine = func(*(obj, request, *a), **merge_dicts(kwargs, kw))
                return_value = (
                    (await routine) if isinstance(routine, Awaitable) else routine
                )  # type: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]
                return return_value

            if not context.get("_http_accept_new_requests"):
                raise web.HTTPServiceUnavailable()

            if pre_handler_func:
                await pre_handler_func(obj, request)

            return_value = await execute_middlewares(
                func, routine_func, context.get("http_middleware", []), *(obj, request)
            )
            response = await resolve_response(
                return_value,
                request=request,
                context=context,
                default_content_type=default_content_type,
                default_charset=default_charset,
            )
            return response

        context["_http_routes"] = context.get("_http_routes", [])
        route_context = {"ignore_logging": ignore_logging}
        if isinstance(method, list) or isinstance(method, tuple):
            for m in method:
                context["_http_routes"].append((m.upper(), pattern, handler, route_context))
        else:
            context["_http_routes"].append((method.upper(), pattern, handler, route_context))

        start_func = cls.start_server(obj, context)
        return (await start_func) if start_func else None

    async def static_request_handler(
        cls: Any,
        obj: Any,
        context: Dict,
        func: Any,
        path: str,
        base_url: str,
        ignore_logging: Union[bool, List[int], Tuple[int]] = False,
    ) -> Any:
        if "?P<filename>" not in base_url:
            pattern = r"^{}(?P<filename>.+?)$".format(re.sub(r"\$$", "", re.sub(r"^\^?(.*)$", r"\1", base_url)))
        else:
            pattern = r"^{}$".format(re.sub(r"\$$", "", re.sub(r"^\^?(.*)$", r"\1", base_url)))
        compiled_pattern = re.compile(pattern)

        if path.startswith("/"):
            path = os.path.dirname(path)
        else:
            path = "{}/{}".format(os.path.dirname(context.get("context", {}).get("_service_file_path")), path)

        if not path.endswith("/"):
            path = "{}/".format(path)

        async def handler(request: web.Request) -> Union[web.Response, web.FileResponse]:
            result = compiled_pattern.match(request.path)
            filename = result.groupdict()["filename"] if result else ""
            filepath = "{}{}".format(path, filename)

            try:
                if (
                    os.path.commonprefix((os.path.realpath(filepath), os.path.realpath(path))) != os.path.realpath(path)
                    or os.path.isdir(filepath)
                    or not os.path.exists(filepath)
                ):
                    raise web.HTTPNotFound()  # type: ignore

                pathlib.Path(filepath).open("r")

                response = FileResponse(
                    path=filepath, chunk_size=256 * 1024  # type: ignore
                )  # type: Union[web.Response, web.FileResponse]
                return response
            except PermissionError:
                raise web.HTTPForbidden()  # type: ignore

        route_context = {"ignore_logging": ignore_logging}
        context["_http_routes"] = context.get("_http_routes", [])
        context["_http_routes"].append(("GET", pattern, handler, route_context))

        start_func = cls.start_server(obj, context)
        return (await start_func) if start_func else None

    async def error_handler(cls: Any, obj: Any, context: Dict, func: Any, status_code: int) -> Any:
        default_content_type = context.get("options", {}).get("http", {}).get("content_type", "text/plain")
        default_charset = context.get("options", {}).get("http", {}).get("charset", "utf-8")

        if default_content_type is not None and ";" in default_content_type:
            # for backwards compability
            try:
                default_charset = (
                    str([v for v in default_content_type.split(";") if "charset=" in v][0])
                    .replace("charset=", "")
                    .strip()
                )
                default_content_type = str([v for v in default_content_type.split(";")][0]).strip()
            except IndexError:
                pass

        async def handler(request: web.Request) -> Union[web.Response, web.FileResponse]:
            request._cache["error_status_code"] = status_code

            values = inspect.getfullargspec(func)
            kwargs = (
                {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults) :])}
                if values.defaults
                else {}
            )

            @functools.wraps(func)
            async def routine_func(
                *a: Any, **kw: Any
            ) -> Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]:
                routine = func(*(obj, request, *a), **merge_dicts(kwargs, kw))
                return_value = (
                    (await routine) if isinstance(routine, Awaitable) else routine
                )  # type: Union[str, bytes, Dict, List, Tuple, web.Response, Response]
                return return_value

            return_value = await execute_middlewares(
                func, routine_func, context.get("http_middleware", []), *(obj, request)
            )
            response = await resolve_response(
                return_value,
                request=request,
                context=context,
                status_code=status_code,
                default_content_type=default_content_type,
                default_charset=default_charset,
            )
            return response

        context["_http_error_handler"] = context.get("_http_error_handler", {})
        context["_http_error_handler"][int(status_code)] = handler

        start_func = cls.start_server(obj, context)
        return (await start_func) if start_func else None

    async def websocket_handler(cls: Any, obj: Any, context: Dict, func: Any, url: str) -> Any:
        pattern = r"^{}$".format(re.sub(r"\$$", "", re.sub(r"^\^?(.*)$", r"\1", url)))
        compiled_pattern = re.compile(pattern)

        access_log = context.get("options", {}).get("http", {}).get("access_log", True)

        async def _pre_handler_func(obj: Any, request: web.Request) -> None:
            request._cache["is_websocket"] = True
            request._cache["websocket_uuid"] = str(uuid.uuid4())

        @functools.wraps(func)
        async def _func(obj: Any, request: web.Request, *a: Any, **kw: Any) -> None:
            websocket = web.WebSocketResponse()  # type: ignore

            request_ip = RequestHandler.get_request_ip(request, context)
            try:
                await websocket.prepare(request)
            except Exception:
                try:
                    await websocket.close()
                except Exception:
                    pass

                if access_log:
                    logging.getLogger("transport.http").info(
                        '[{}] {} {} "CANCELLED {}{}" {} "{}" {}'.format(
                            RequestHandler.colorize_status("websocket", 101),
                            request_ip,
                            '"{}"'.format(request._cache["auth"].login.replace('"', ""))
                            if request._cache.get("auth") and getattr(request._cache.get("auth"), "login", None)
                            else "-",
                            request.path,
                            "?{}".format(request.query_string) if request.query_string else "",
                            request._cache.get("websocket_uuid", ""),
                            request.headers.get("User-Agent", "").replace('"', ""),
                            "-",
                        )
                    )

                return

            context["_http_open_websockets"] = context.get("_http_open_websockets", [])
            context["_http_open_websockets"].append(websocket)

            if access_log:
                logging.getLogger("transport.http").info(
                    '[{}] {} {} "OPEN {}{}" {} "{}" {}'.format(
                        RequestHandler.colorize_status("websocket", 101),
                        request_ip,
                        '"{}"'.format(request._cache["auth"].login.replace('"', ""))
                        if request._cache.get("auth") and getattr(request._cache.get("auth"), "login", None)
                        else "-",
                        request.path,
                        "?{}".format(request.query_string) if request.query_string else "",
                        request._cache.get("websocket_uuid", ""),
                        request.headers.get("User-Agent", "").replace('"', ""),
                        "-",
                    )
                )

            result = compiled_pattern.match(request.path)
            values = inspect.getfullargspec(func)
            kwargs = (
                {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults) :])}
                if values.defaults
                else {}
            )
            if result:
                for k, v in result.groupdict().items():
                    kwargs[k] = v

            if len(values.args) - (len(values.defaults) if values.defaults else 0) >= 3:
                # If the function takes a third required argument the value will be filled with the request object
                a = a + (request,)
            if "request" in values.args and (
                len(values.args) - (len(values.defaults) if values.defaults else 0) < 3 or values.args[2] != "request"
            ):
                kwargs["request"] = request

            try:
                routine = func(*(obj, websocket, *a), **merge_dicts(kwargs, kw))
                callback_functions = (
                    (await routine) if isinstance(routine, Awaitable) else routine
                )  # type: Optional[Union[Tuple, Callable]]
            except Exception as e:
                logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                try:
                    await websocket.close()
                except Exception:
                    pass

                try:
                    context["_http_open_websockets"].remove(websocket)
                except Exception:
                    pass

                if access_log:
                    logging.getLogger("transport.http").info(
                        '[{}] {} {} "{} {}{}" {} "{}" {}'.format(
                            RequestHandler.colorize_status("websocket", 500),
                            request_ip,
                            '"{}"'.format(request._cache["auth"].login.replace('"', ""))
                            if request._cache.get("auth") and getattr(request._cache.get("auth"), "login", None)
                            else "-",
                            RequestHandler.colorize_status("ERROR", 500),
                            request.path,
                            "?{}".format(request.query_string) if request.query_string else "",
                            request._cache.get("websocket_uuid", ""),
                            request.headers.get("User-Agent", "").replace('"', ""),
                            "-",
                        )
                    )

                return

            _receive_func = None
            _close_func = None

            if callback_functions and isinstance(callback_functions, tuple):
                try:
                    _receive_func, _close_func = callback_functions
                except ValueError:
                    (_receive_func,) = callback_functions
            elif callback_functions:
                _receive_func = callback_functions

            try:
                async for message in websocket:
                    if message.type == WSMsgType.TEXT:
                        if _receive_func:
                            try:
                                await _receive_func(message.data)
                            except Exception as e:
                                logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                    elif message.type == WSMsgType.ERROR:
                        if not context.get("log_level") or context.get("log_level") in ["DEBUG"]:
                            ws_exception = websocket.exception()
                            if isinstance(ws_exception, (EofStream, RuntimeError)):
                                pass
                            elif isinstance(ws_exception, Exception):
                                logging.getLogger("exception").exception(
                                    "Uncaught exception: {}".format(str(ws_exception))
                                )
                            else:
                                logging.getLogger("transport.http").warning(
                                    'Websocket exception: "{}"'.format(ws_exception)
                                )
                    elif message.type == WSMsgType.CLOSED:
                        break  # noqa
            except Exception:
                pass
            finally:
                if _close_func:
                    try:
                        await _close_func()
                    except Exception as e:
                        logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                try:
                    await websocket.close()
                except Exception:
                    pass

                try:
                    context["_http_open_websockets"].remove(websocket)
                except Exception:
                    pass

        return await cls.request_handler(cls, obj, context, _func, "GET", url, pre_handler_func=_pre_handler_func)

    async def start_server(obj: Any, context: Dict) -> Optional[Callable]:
        if context.get("_http_server_started"):
            return None
        context["_http_server_started"] = True

        http_options = context.get("options", {}).get("http", {})

        server_header = http_options.get("server_header", "tomodachi")
        access_log = http_options.get("access_log", True)

        logger_handler = None
        if isinstance(access_log, str):
            try:
                wfh = WatchedFileHandler(filename=access_log)
            except FileNotFoundError as e:
                logging.getLogger("transport.http").warning(
                    'Unable to use file for access log - invalid path ("{}")'.format(access_log)
                )
                raise HttpException(str(e)) from e
            except PermissionError as e:
                logging.getLogger("transport.http").warning(
                    'Unable to use file for access log - invalid permissions ("{}")'.format(access_log)
                )
                raise HttpException(str(e)) from e
            wfh.setLevel(logging.DEBUG)
            logging.getLogger("transport.http").setLevel(logging.DEBUG)
            logging.getLogger("transport.http").info('Logging to "{}"'.format(access_log))
            logger_handler = wfh
            logging.getLogger("transport.http").addHandler(logger_handler)

        async def _start_server() -> None:
            loop = asyncio.get_event_loop()

            logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

            @web.middleware
            async def middleware(request: web.Request, handler: Callable) -> Union[web.Response, web.FileResponse]:
                async def func() -> Union[web.Response, web.FileResponse]:
                    response: Union[web.Response, web.FileResponse]
                    request_ip = RequestHandler.get_request_ip(request, context)

                    if not request_ip:
                        # Transport broken before request handling started, ignore request
                        response = web.Response(status=499, headers={hdrs.SERVER: server_header or ""})  # type: ignore
                        response._eof_sent = True
                        response.force_close()  # type: ignore

                        return response

                    if request.headers.get("Authorization"):
                        try:
                            request._cache["auth"] = BasicAuth.decode(request.headers.get("Authorization", ""))
                        except ValueError:
                            pass

                    if access_log:
                        timer = time.time()
                    response = web.Response(status=503, headers={})  # type: ignore
                    try:
                        response = await handler(request)
                    except web.HTTPException as e:
                        error_handler = context.get("_http_error_handler", {}).get(e.status, None)
                        if error_handler:
                            response = await error_handler(request)
                        else:
                            response = e
                            response.body = str(e).encode("utf-8")
                    except Exception as e:
                        error_handler = context.get("_http_error_handler", {}).get(500, None)
                        logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
                        if error_handler:
                            response = await error_handler(request)
                        else:
                            response = web.HTTPInternalServerError()  # type: ignore
                            response.body = b""
                    finally:
                        if not request.transport:
                            response = web.Response(status=499, headers={})  # type: ignore
                            response._eof_sent = True

                        request_version = (
                            (request.version.major, request.version.minor)
                            if isinstance(request.version, HttpVersion)
                            else (1, 0)
                        )

                        if access_log:
                            request_time = time.time() - timer
                            version_string = None
                            if isinstance(request.version, HttpVersion):
                                version_string = "HTTP/{}.{}".format(request_version[0], request_version[1])

                            if not request._cache.get("is_websocket"):
                                status_code = response.status if response is not None else 500
                                ignore_logging = getattr(handler, "ignore_logging", False)
                                if ignore_logging is True:
                                    pass
                                elif isinstance(ignore_logging, (list, tuple)) and status_code in ignore_logging:
                                    pass
                                else:
                                    logging.getLogger("transport.http").info(
                                        '[{}] [{}] {} {} "{} {}{}{}" {} {} "{}" {}'.format(
                                            RequestHandler.colorize_status("http", status_code),
                                            RequestHandler.colorize_status(status_code),
                                            request_ip,
                                            '"{}"'.format(request._cache["auth"].login.replace('"', ""))
                                            if request._cache.get("auth")
                                            and getattr(request._cache.get("auth"), "login", None)
                                            else "-",
                                            request.method,
                                            request.path,
                                            "?{}".format(request.query_string) if request.query_string else "",
                                            " {}".format(version_string) if version_string else "",
                                            response.content_length
                                            if response is not None and response.content_length is not None
                                            else "-",
                                            request.content_length if request.content_length is not None else "-",
                                            request.headers.get("User-Agent", "").replace('"', ""),
                                            "{0:.5f}s".format(round(request_time, 5)),
                                        )
                                    )
                            else:
                                logging.getLogger("transport.http").info(
                                    '[{}] {} {} "CLOSE {}{}" {} "{}" {}'.format(
                                        RequestHandler.colorize_status("websocket", 101),
                                        request_ip,
                                        '"{}"'.format(request._cache["auth"].login.replace('"', ""))
                                        if request._cache.get("auth")
                                        and getattr(request._cache.get("auth"), "login", None)
                                        else "-",
                                        request.path,
                                        "?{}".format(request.query_string) if request.query_string else "",
                                        request._cache.get("websocket_uuid", ""),
                                        request.headers.get("User-Agent", "").replace('"', ""),
                                        "{0:.5f}s".format(round(request_time, 5)),
                                    )
                                )

                        if response is not None:
                            response.headers[hdrs.SERVER] = server_header or ""

                            if request_version in ((1, 0), (1, 1)) and not request._cache.get("is_websocket"):
                                if context["_http_tcp_keepalive"] and request.keep_alive:
                                    response.headers[hdrs.CONNECTION] = "keep-alive"
                                    response.headers[hdrs.KEEP_ALIVE] = "timeout={}".format(
                                        context["_http_keepalive_timeout"]
                                    )
                                else:
                                    response.headers[hdrs.CONNECTION] = "close"

                        if not context["_http_tcp_keepalive"] and not request._cache.get("is_websocket"):
                            response.force_close()  # type: ignore

                        if isinstance(response, (web.HTTPException, web.HTTPInternalServerError)):
                            raise response

                        return response

                increase_execution_context_value("http_current_tasks")
                increase_execution_context_value("http_total_tasks")
                task = asyncio.ensure_future(func())
                context["_http_active_requests"] = context.get("_http_active_requests", set())
                context["_http_active_requests"].add(task)
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    try:
                        await task
                        decrease_execution_context_value("http_current_tasks")
                        context["_http_active_requests"].remove(task)
                        return task.result()
                    except Exception:
                        decrease_execution_context_value("http_current_tasks")
                        context["_http_active_requests"].remove(task)
                        raise
                except Exception:
                    decrease_execution_context_value("http_current_tasks")
                    context["_http_active_requests"].remove(task)
                    raise
                decrease_execution_context_value("http_current_tasks")
                context["_http_active_requests"].remove(task)

                return task.result()

            client_max_size_option = (
                http_options.get("client_max_size")
                or http_options.get("max_buffer_size")
                or http_options.get("max_upload_size")
                or "100M"
            )
            client_max_size = (1024 ** 2) * 100
            try:
                if (
                    client_max_size_option
                    and isinstance(client_max_size_option, str)
                    and (client_max_size_option.upper().endswith("G") or client_max_size_option.upper().endswith("GB"))
                ):
                    client_max_size = int(re.sub(r"^([0-9]+)GB?$", r"\1", client_max_size_option.upper())) * (1024 ** 3)
                elif (
                    client_max_size_option
                    and isinstance(client_max_size_option, str)
                    and (client_max_size_option.upper().endswith("M") or client_max_size_option.upper().endswith("MB"))
                ):
                    client_max_size = int(re.sub(r"^([0-9]+)MB?$", r"\1", client_max_size_option.upper())) * (1024 ** 2)
                elif (
                    client_max_size_option
                    and isinstance(client_max_size_option, str)
                    and (client_max_size_option.upper().endswith("K") or client_max_size_option.upper().endswith("KB"))
                ):
                    client_max_size = int(re.sub(r"^([0-9]+)KB?$", r"\1", client_max_size_option.upper())) * 1024
                elif (
                    client_max_size_option
                    and isinstance(client_max_size_option, str)
                    and (client_max_size_option.upper().endswith("B"))
                ):
                    client_max_size = int(re.sub(r"^([0-9]+)B?$", r"\1", client_max_size_option.upper()))
                elif client_max_size_option:
                    client_max_size = int(client_max_size_option)
            except Exception:
                raise ValueError(
                    "Bad value for http option client_max_size: {}".format(str(client_max_size_option))
                ) from None
            if client_max_size >= 0 and client_max_size < 1024:
                raise ValueError(
                    "Too low value for http option client_max_size: {} ({})".format(
                        str(client_max_size_option), client_max_size_option
                    )
                )
            if client_max_size > 1024 ** 3:
                raise ValueError(
                    "Too high value for http option client_max_size: {} ({})".format(
                        str(client_max_size_option), client_max_size_option
                    )
                )

            app = web.Application(
                middlewares=[middleware], client_max_size=(1024 ** 2) * 100  # type: ignore
            )  # type: web.Application
            app._set_loop(None)  # type: ignore
            for method, pattern, handler, route_context in context.get("_http_routes", []):
                try:
                    compiled_pattern = re.compile(pattern)
                except re.error as exc:
                    raise ValueError("Bad http route pattern '{}': {}".format(pattern, exc)) from None
                ignore_logging = route_context.get("ignore_logging", False)
                setattr(handler, "ignore_logging", ignore_logging)
                resource = DynamicResource(compiled_pattern)
                app.router.register_resource(resource)  # type: ignore
                if method.upper() == "GET":
                    resource.add_route("HEAD", handler, expect_handler=None)  # type: ignore
                resource.add_route(method.upper(), handler, expect_handler=None)  # type: ignore

            context["_http_accept_new_requests"] = True

            port = http_options.get("port", 9700)
            host = http_options.get("host", "0.0.0.0")
            if port is True:
                raise ValueError("Bad value for http option port: {}".format(str(port)))

            keepalive_timeout_option = http_options.get("keepalive_timeout", 0) or http_options.get(
                "keepalive_expiry", 0
            )
            keepalive_timeout = 0
            tcp_keepalive = False
            if keepalive_timeout_option is None or keepalive_timeout_option is False:
                keepalive_timeout = 0
            if keepalive_timeout_option is True:
                raise ValueError(
                    "Bad value for http option keepalive_timeout: {}".format(str(keepalive_timeout_option))
                )
            try:
                keepalive_timeout = int(keepalive_timeout_option)
            except Exception:
                raise ValueError(
                    "Bad value for http option keepalive_timeout: {}".format(str(keepalive_timeout_option))
                ) from None
            if keepalive_timeout > 0:
                tcp_keepalive = True
            else:
                tcp_keepalive = False
                keepalive_timeout = 0

            set_execution_context(
                {
                    "http_enabled": True,
                    "http_current_tasks": 0,
                    "http_total_tasks": 0,
                    "aiohttp_version": aiohttp_version,
                }
            )

            context["_http_tcp_keepalive"] = tcp_keepalive
            context["_http_keepalive_timeout"] = keepalive_timeout

            try:
                app.freeze()
                web_server = Server(
                    app._handle,
                    request_factory=app._make_request,
                    server_header=server_header or "",
                    access_log=access_log,
                    keepalive_timeout=keepalive_timeout,
                    tcp_keepalive=tcp_keepalive,
                )
                server_task = loop.create_server(web_server, host, port)  # type: ignore
                server = await server_task  # type: ignore
            except OSError as e:
                context["_http_accept_new_requests"] = False
                error_message = re.sub(".*: ", "", e.strerror)
                logging.getLogger("transport.http").warning(
                    "Unable to bind service [http] to http://{}:{}/ ({})".format(
                        "127.0.0.1" if host == "0.0.0.0" else host, port, error_message
                    )
                )
                raise HttpException(str(e), log_level=context.get("log_level")) from e

            if server.sockets:
                socket_address = server.sockets[0].getsockname()
                if socket_address:
                    port = int(socket_address[1])
            context["_http_port"] = port

            stop_method = getattr(obj, "_stop_service", None)

            async def stop_service(*args: Any, **kwargs: Any) -> None:
                context["_http_tcp_keepalive"] = False
                context["_http_accept_new_requests"] = False

                server.close()
                await server.wait_closed()

                if len(web_server.connections):
                    await asyncio.sleep(1)

                open_websockets = context.get("_http_open_websockets", [])[:]
                if open_websockets:
                    logging.getLogger("transport.http").info(
                        "Closing {} websocket connection(s)".format(len(open_websockets))
                    )
                    tasks = []
                    for websocket in open_websockets:
                        try:
                            tasks.append(asyncio.ensure_future(websocket.close()))
                        except Exception:
                            pass
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(asyncio.gather(*tasks, return_exceptions=True)), timeout=10
                        )
                        await asyncio.sleep(1)
                    except (Exception, asyncio.TimeoutError, asyncio.CancelledError):
                        pass
                    context["_http_open_websockets"] = []

                active_requests = context.get("_http_active_requests", set())
                if active_requests:
                    termination_grace_period_seconds = 30
                    try:
                        termination_grace_period_seconds = int(
                            http_options.get("termination_grace_period_seconds") or termination_grace_period_seconds
                        )
                    except Exception:
                        pass
                    logging.getLogger("transport.http").info(
                        "Waiting for {} active request(s) to complete - grace period of {} seconds".format(
                            len(active_requests), termination_grace_period_seconds
                        )
                    )
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(asyncio.gather(*active_requests, return_exceptions=True)),
                            timeout=termination_grace_period_seconds,
                        )
                        await asyncio.sleep(1)
                        active_requests = context.get("_http_active_requests", set())
                    except (Exception, asyncio.TimeoutError, asyncio.CancelledError):
                        active_requests = context.get("_http_active_requests", set())
                        if active_requests:
                            logging.getLogger("transport.http").warning(
                                "All requests did not gracefully finish execution - {} request(s) remaining".format(
                                    len(active_requests)
                                )
                            )
                    context["_http_active_requests"] = set()

                if len(web_server.connections):
                    await app.shutdown()
                    await asyncio.sleep(1)
                else:
                    await app.shutdown()

                if logger_handler:
                    logging.getLogger("transport.http").removeHandler(logger_handler)
                await app.cleanup()
                if stop_method:
                    await stop_method(*args, **kwargs)

            setattr(obj, "_stop_service", stop_service)

            for method, pattern, handler, route_context in context.get("_http_routes", []):
                for registry in getattr(obj, "discovery", []):
                    if getattr(registry, "add_http_endpoint", None):
                        await registry.add_http_endpoint(obj, host, port, method, pattern)

            logging.getLogger("transport.http").info(
                "Listening [http] on http://{}:{}/".format("127.0.0.1" if host == "0.0.0.0" else host, port)
            )

        return _start_server


async def resolve_response(
    value: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response],
    request: Optional[web.Request] = None,
    context: Dict = None,
    status_code: Optional[Union[str, int]] = None,
    default_content_type: Optional[str] = None,
    default_charset: Optional[str] = None,
) -> Union[web.Response, web.FileResponse]:
    if not context:
        context = {}
    if isinstance(value, Response):
        return value.get_aiohttp_response(
            context, default_content_type=default_content_type, default_charset=default_charset
        )
    if isinstance(value, web.FileResponse):
        return value

    status = (
        int(status_code)
        if status_code
        else (request is not None and request._cache.get("error_status_code", 200)) or 200
    )
    headers = None
    if isinstance(value, dict):
        body = value.get("body")
        _status = value.get("status")  # type: Optional[SupportsInt]
        if _status and isinstance(_status, (int, str, bytes)):
            status = int(_status)
        _returned_headers = value.get("headers")
        if _returned_headers:
            returned_headers = _returned_headers  # type: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]]
            headers = CIMultiDict(returned_headers)
    elif isinstance(value, list) or isinstance(value, tuple):
        _status = value[0]
        if _status and isinstance(_status, (int, str, bytes)):
            status = int(_status)
        body = value[1]
        if len(value) > 2:
            returned_headers = value[2]
            headers = CIMultiDict(returned_headers)
    elif isinstance(value, web.Response):
        return value
    else:
        if value is None:
            value = ""
        body = value

    return Response(
        body=body, status=status, headers=headers, content_type=default_content_type, charset=default_charset
    ).get_aiohttp_response(context)


async def get_http_response_status(
    value: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response, Exception],
    request: Optional[web.Request] = None,
    verify_transport: bool = True,
) -> Optional[int]:
    if isinstance(value, Exception) or isinstance(value, web.HTTPException):
        status_code = int(getattr(value, "status", 500)) if value is not None else 500
        return status_code
    else:
        response = await resolve_response(value, request=request)
        status_code = int(response.status) if response is not None else 500
        if verify_transport and request is not None and request.transport is None:
            return 499
        else:
            return status_code


http = HttpTransport.decorator(HttpTransport.request_handler)
http_error = HttpTransport.decorator(HttpTransport.error_handler)
http_static = HttpTransport.decorator(HttpTransport.static_request_handler)

websocket = HttpTransport.decorator(HttpTransport.websocket_handler)
ws = HttpTransport.decorator(HttpTransport.websocket_handler)
