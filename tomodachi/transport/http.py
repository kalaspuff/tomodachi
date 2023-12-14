from __future__ import annotations

import asyncio
import functools
import inspect
import ipaddress
import os
import pathlib
import platform
import re
import time
import uuid
import warnings
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, SupportsInt, Tuple, Union, cast

import yarl
from aiohttp import WSMsgType
from aiohttp import __version__ as aiohttp_version
from aiohttp import hdrs, web, web_protocol, web_server, web_urldispatcher
from aiohttp.helpers import BasicAuth
from aiohttp.http import HttpVersion
from aiohttp.streams import EofStream
from aiohttp.web_fileresponse import FileResponse
from multidict import CIMultiDict, CIMultiDictProxy

from tomodachi import get_contextvar, logging
from tomodachi._exception import limit_exception_traceback
from tomodachi.helpers.execution_context import (
    decrease_execution_context_value,
    increase_execution_context_value,
    set_execution_context,
)
from tomodachi.helpers.middleware import execute_middlewares
from tomodachi.invoker import Invoker
from tomodachi.options import Options


class HttpException(Exception):
    pass


def get_forwarded_remote_ip(request: web.BaseRequest) -> str:
    try:
        return cast(str, request._cache["forwarded_remote_ip"])
    except KeyError:
        return ""


class RequestHandler(web_protocol.RequestHandler):
    __slots__ = (
        *web_protocol.RequestHandler.__slots__,
        "_connection_start_time",
        "_keepalive",
    )

    _manager: Server

    @staticmethod
    def get_request_ip(request: web.Request, *a: Any, **kw: Any) -> str:
        warnings.warn(
            "Using the 'RequestHandler.get_request_ip()' function is deprecated. Use the 'tomodachi.get_forwarded_remote_ip()' function instead.",
            DeprecationWarning,
        )

        return get_forwarded_remote_ip(request)

    def _cache_remote_ip(self, request: web.BaseRequest) -> None:
        remote_ip: str = request.remote or ""

        if self._manager._real_ip_header and self._manager._real_ip_from:
            if any(
                [ipaddress.ip_address(remote_ip) in ipaddress.ip_network(cidr) for cidr in self._manager._real_ip_from]
            ):
                header_value = request.headers.get(self._manager._real_ip_header)
                if header_value:
                    remote_ip = header_value.split(",")[0].strip().split(" ")[0].strip()

        request._cache["forwarded_remote_ip"] = remote_ip
        request._cache["request_ip"] = remote_ip  # deprecated

    async def start(self) -> None:
        self._connection_start_time = time.time()
        await super().start()

    async def _handle_request(
        self,
        request: web.BaseRequest,
        start_time: float,
        *args: Any,
    ) -> Tuple[web.StreamResponse, bool]:
        self._cache_remote_ip(request)
        result: Tuple[web.StreamResponse, bool] = await super()._handle_request(request, start_time, *args)
        return result

    async def finish_response(self, request: web.BaseRequest, resp: web.StreamResponse, start_time: float) -> bool:
        result: bool = await super().finish_response(request, resp, start_time)
        return result

    def handle_error(
        self, request: Any, status: int = 500, exc: Any = None, message: Optional[str] = None
    ) -> web.Response:
        """Handle errors.

        Returns HTTP response with specific status code. Logs additional
        information. It always closes current connection."""
        if self.transport is None:
            # client has been disconnected during writing.
            if self._manager._access_log:
                request_ip = RequestHandler.get_request_ip(request, None)
                version_string = None
                if isinstance(request.version, HttpVersion):
                    version_string = "HTTP/{}.{}".format(request.version.major, request.version.minor)

                status_code = 499
                logging.getLogger("tomodachi.http.response").info(
                    "client disconnected during writing",
                    status_code=status_code,
                    remote_ip=request_ip or "",
                    auth_user=getattr(request._cache.get("auth") or {}, "login", None) or Ellipsis,
                    request_method=request.method,
                    request_path=request.path,
                    request_query_string=request.query_string or Ellipsis,
                    http_version=version_string,
                    request_content_length=request.content_length if request.content_length else Ellipsis,
                    user_agent=request.headers.get("User-Agent", ""),
                )

        headers: CIMultiDict = CIMultiDict({})
        headers[hdrs.CONTENT_TYPE] = "text/plain; charset=utf-8"

        msg = "" if status == 500 or not message else message

        headers[hdrs.CONTENT_LENGTH] = str(len(msg))
        headers[hdrs.SERVER] = self._manager._server_header

        if isinstance(request.version, HttpVersion) and (request.version.major, request.version.minor) in (
            (1, 0),
            (1, 1),
        ):
            headers[hdrs.CONNECTION] = "close"

        resp: web.Response = web.Response(status=status, text=msg, headers=headers)
        resp.force_close()

        # some data already got sent, connection is broken
        if request.writer.output_size > 0 or self.transport is None:
            self.force_close()
        elif self.transport is not None:
            request_ip = RequestHandler.get_request_ip(request, None)
            if not request_ip:
                peername = request.transport.get_extra_info("peername")
                if peername:
                    request_ip, _ = peername
            if self._manager._access_log:
                if not status or status >= 500:
                    logging.getLogger("tomodachi.http.response").warning(
                        "error in request handling",
                        status_code=status,
                        remote_ip=request_ip or "",
                        auth_user=getattr(request._cache.get("auth") or {}, "login", None) or Ellipsis,
                        response_content_length=len(msg),
                        request_content_length=(
                            request.content_length
                            if request.content_length
                            else (
                                len(request._read_bytes)
                                if request._read_bytes is not None and len(request._read_bytes)
                                else Ellipsis
                            )
                        ),
                        request_content_read_length=(
                            len(request._read_bytes)
                            if request._read_bytes is not None and len(request._read_bytes)
                            else ((request.content and getattr(request.content, "total_bytes", None)) or Ellipsis)
                        ),
                    )
                else:
                    logging.getLogger("tomodachi.http.response").info(
                        "bad http request",
                        status_code=status,
                        remote_ip=request_ip or "",
                        auth_user=getattr(request._cache.get("auth") or {}, "login", None) or Ellipsis,
                        response_content_length=len(msg),
                        request_content_length=(
                            request.content_length
                            if request.content_length
                            else (
                                len(request._read_bytes)
                                if request._read_bytes is not None and len(request._read_bytes)
                                else Ellipsis
                            )
                        ),
                        request_content_read_length=(
                            len(request._read_bytes)
                            if request._read_bytes is not None and len(request._read_bytes)
                            else ((request.content and getattr(request.content, "total_bytes", None)) or Ellipsis)
                        ),
                    )

        return resp


class Server(web_server.Server):
    __slots__ = (
        "_loop",
        "_connections",
        "_kwargs",
        "requests_count",
        "request_handler",
        "request_factory",
        "_server_header",
        "_access_log",
        "_real_ip_header",
        "_real_ip_from",
    )

    _loop: asyncio.AbstractEventLoop
    _kwargs: Dict[str, Any]

    _server_header: str
    _access_log: Union[bool, str]
    _real_ip_header: str
    _real_ip_from: List[str]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._server_header = cast(str, kwargs.pop("server_header", "") if kwargs else "")
        self._access_log = cast(Union[bool, str], kwargs.pop("access_log", False) if kwargs else False)
        self._real_ip_header = cast(str, kwargs.pop("real_ip_header", "") if kwargs else "")
        self._real_ip_from = cast(List[str], kwargs.pop("real_ip_from", []) if kwargs else [])

        kwargs["access_log"] = None

        super().__init__(*args, **kwargs)

    def __call__(self) -> RequestHandler:
        return RequestHandler(self, loop=self._loop, **self._kwargs)


class DynamicResource(web_urldispatcher.DynamicResource):
    def __init__(self, pattern: Any, *, name: Optional[str] = None) -> None:
        self._routes: List = []
        self._name = name
        self._pattern = pattern
        self._formatter = ""

        simplified = re.compile(r"^\^?(.+?)\$?$").match(pattern.pattern)
        self._simplified_pattern = simplified.group(1) if simplified else pattern.pattern


class Response(object):
    __slots__ = ("_body", "_status", "_reason", "_headers", "content_type", "charset", "missing_content_type")

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
                logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))
                raise web.HTTPInternalServerError() from e
        elif self._body:
            body_value = self._body.encode() if not isinstance(self._body, bytes) else self._body
        else:
            body_value = b""

        response: web.Response = web.Response(
            body=body_value,
            status=self._status,
            reason=self._reason,
            headers=self._headers,
            content_type=self.content_type,
            charset=self.charset,
        )
        return response


class HttpTransport(Invoker):
    server_port_mapping: Dict[Any, str] = {}

    @classmethod
    async def request_handler(
        cls,
        obj: Any,
        context: Dict,
        func: Any,
        method: Union[str, List[str], Tuple[str, ...]],
        url: str,
        *,
        ignore_logging: Union[bool, List[int], Tuple[int, ...]] = False,
        pre_handler_func: Optional[Callable] = None,
    ) -> Any:
        pattern = r"^{}$".format(re.sub(r"\$$", "", re.sub(r"^\^?(.*)$", r"\1", url)))
        compiled_pattern = re.compile(pattern)

        http_options: Options.HTTP = cls.options(context).http
        default_content_type = http_options.content_type
        default_charset = http_options.charset
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

        values = inspect.getfullargspec(func)
        original_kwargs = (
            {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults) :])}
            if values.defaults
            else {}
        )
        args_list = values.args[1 : len(values.args) - len(values.defaults or ())]
        args_set = (set(values.args[1:]) | set(values.kwonlyargs)) - set(["self"])

        middlewares = context.get("http_middleware", [])

        async def handler(request: web.Request) -> Union[web.Response, web.FileResponse]:
            logger = logging.getLogger("tomodachi.http.handler").bind(handler=func.__name__, type="tomodachi.http")

            kwargs = dict(original_kwargs)
            arg_matches: Dict[str, Any] = {}

            if "(" in pattern:
                result = compiled_pattern.match(request.path)
                if result:
                    for k, v in result.groupdict().items():
                        if k in args_set:
                            kwargs[k] = v
                            if k in values.args:
                                arg_matches[k] = v

            if "request" in args_set:
                kwargs["request"] = request
                if "request" in values.args:
                    arg_matches["request"] = request

            if not context.get("_http_accept_new_requests"):
                raise web.HTTPServiceUnavailable()

            if pre_handler_func:
                await pre_handler_func(obj, request)
                logger = logging.getLogger("tomodachi.http.handler")

            @functools.wraps(func)
            async def routine_func(
                *a: Any, **kw: Any
            ) -> Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]:
                logging.bind_logger(logger)
                get_contextvar("service.logger").set("tomodachi.http.handler")

                kw_values = {k: v for k, v in {**kwargs, **kw}.items() if values.varkw or k in args_set}
                args_values = [
                    kw_values.pop(key) if key in kw_values else a[i + 1]
                    for i, key in enumerate(values.args[1 : len(a) + 1])
                ]
                if values.varargs and not values.defaults and len(a) > len(args_values) + 1:
                    args_values += a[len(args_values) + 1 :]

                routine = func(*(obj, *args_values), **kw_values)
                return_value: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response] = (
                    (await routine) if inspect.isawaitable(routine) else routine
                )
                return return_value

            return_value: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]
            if middlewares:
                logging.bind_logger(
                    logging.getLogger("tomodachi.http.middleware").bind(
                        middleware=Ellipsis, handler=func.__name__, type="tomodachi.http"
                    )
                )
                return_value = await asyncio.create_task(
                    execute_middlewares(func, routine_func, middlewares, *(obj, request), request=request)
                )
            else:
                logging.bind_logger(logger)
                get_contextvar("service.logger").set("tomodachi.http.handler")

                a = [arg_matches[k] if k in arg_matches else (request,)[i] for i, k in enumerate(args_list)]
                args_values = [kwargs.pop(key) if key in kwargs else a[i] for i, key in enumerate(args_list)]

                if values.varargs and not values.defaults and len(a) > len(args_values) + 1:
                    args_values += a[len(args_values) + 1 :]

                routine = func(obj, *args_values, **kwargs)
                return_value = (await routine) if inspect.isawaitable(routine) else routine

            response = resolve_response_sync(
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
        elif isinstance(method, str):
            context["_http_routes"].append((method.upper(), pattern, handler, route_context))
        else:
            raise Exception("Invalid method '{}' for route".format(str(method)))

        start_func = cls.start_server(obj, context)
        return (await start_func) if start_func else None

    @classmethod
    async def static_request_handler(
        cls,
        obj: Any,
        context: Dict,
        func: Any,
        path: str,
        base_url: str,
        *,
        ignore_logging: Union[bool, List[int], Tuple[int, ...]] = False,
    ) -> Any:
        if "?P<filename>" not in base_url:
            pattern = r"^{}(?P<filename>.+?)$".format(re.sub(r"\$$", "", re.sub(r"^\^?(.*)$", r"\1", base_url)))
        else:
            pattern = r"^{}$".format(re.sub(r"\$$", "", re.sub(r"^\^?(.*)$", r"\1", base_url)))
        compiled_pattern = re.compile(pattern)

        if path in ("", "/"):
            # Hopefully noone wants to do this intentionally, and if anyone accidentally does we'll catch it here
            raise Exception("Invalid path '{}' for static route".format(path))

        if not path.startswith("/"):
            path = "{}/{}".format(os.path.dirname(context.get("context", {}).get("_service_file_path", "")), path)

        if not path.endswith("/"):
            path = "{}/".format(path)

        if os.path.realpath(path) == "/":
            raise Exception("Invalid path '{}' for static route resolves to '/'".format(path))

        async def handler(request: web.Request) -> Union[web.Response, web.FileResponse]:
            normalized_request_path = yarl.URL._normalize_path(request.path)
            if not normalized_request_path.startswith("/"):
                raise web.HTTPNotFound()

            result = compiled_pattern.match(normalized_request_path)
            filename = result.groupdict()["filename"] if result else ""

            basepath = os.path.realpath(path)
            realpath = os.path.realpath("{}/{}".format(basepath, filename))

            try:
                if any(
                    [
                        not realpath,
                        not basepath,
                        realpath == basepath,
                        os.path.commonprefix((realpath, basepath)) != basepath,
                        not os.path.exists(realpath),
                        not os.path.isdir(basepath),
                        basepath == "/",
                        os.path.isdir(realpath),
                    ]
                ):
                    raise web.HTTPNotFound()

                # deepcode ignore PT: Input data to pathlib.Path is sanitized
                pathlib.Path(realpath).open("r")

                response: Union[web.Response, web.FileResponse] = FileResponse(path=realpath, chunk_size=256 * 1024)
                return response
            except PermissionError:
                raise web.HTTPForbidden()

        route_context = {"ignore_logging": ignore_logging}
        context["_http_routes"] = context.get("_http_routes", [])
        context["_http_routes"].append(("GET", pattern, handler, route_context))

        start_func = cls.start_server(obj, context)
        return (await start_func) if start_func else None

    @classmethod
    async def error_handler(cls, obj: Any, context: Dict, func: Any, status_code: int) -> Any:
        http_options: Options.HTTP = cls.options(context).http
        default_content_type = http_options.content_type
        default_charset = http_options.charset
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

        values = inspect.getfullargspec(func)
        original_kwargs = (
            {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults) :])}
            if values.defaults
            else {}
        )
        args_list = values.args[1 : len(values.args) - len(values.defaults or ())]
        args_set = (set(values.args[1:]) | set(values.kwonlyargs)) - set(["self"])

        middlewares = context.get("http_middleware", [])

        async def handler(request: web.Request) -> Union[web.Response, web.FileResponse]:
            logger = logging.getLogger("tomodachi.http.handler").bind(
                handler=func.__name__, type="tomodachi.http_error", status_code=status_code
            )

            kwargs = dict(original_kwargs)
            arg_matches: Dict[str, Any] = {}

            if "request" in args_set:
                kwargs["request"] = request
                if "request" in values.args:
                    arg_matches["request"] = request

            if "status_code" in args_set:
                kwargs["status_code"] = status_code
                if "status_code" in values.args:
                    arg_matches["status_code"] = status_code

            request._cache["error_status_code"] = status_code

            @functools.wraps(func)
            async def routine_func(
                *a: Any, **kw: Any
            ) -> Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]:
                logging.bind_logger(logger)
                get_contextvar("service.logger").set("tomodachi.http.handler")

                kw_values = {k: v for k, v in {**kwargs, **kw}.items() if values.varkw or k in args_set}
                args_values = [
                    kw_values.pop(key) if key in kw_values else a[i + 1]
                    for i, key in enumerate(values.args[1 : len(a) + 1])
                ]
                if values.varargs and not values.defaults and len(a) > len(args_values) + 1:
                    args_values += a[len(args_values) + 1 :]

                routine = func(*(obj, *args_values), **kw_values)
                return_value: Union[str, bytes, Dict, List, Tuple, web.Response, Response] = (
                    (await routine) if inspect.isawaitable(routine) else routine
                )
                return return_value

            return_value: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]
            if middlewares:
                logging.bind_logger(
                    logging.getLogger("tomodachi.http.middleware").bind(
                        middleware=Ellipsis, handler=func.__name__, type="tomodachi.http_error", status_code=status_code
                    )
                )
                return_value = await asyncio.create_task(
                    execute_middlewares(
                        func, routine_func, middlewares, *(obj, request), request=request, status_code=status_code
                    )
                )
            else:
                logging.bind_logger(logger)
                get_contextvar("service.logger").set("tomodachi.http.handler")

                a = [arg_matches[k] if k in arg_matches else (request,)[i] for i, k in enumerate(args_list)]
                args_values = [kwargs.pop(key) if key in kwargs else a[i] for i, key in enumerate(args_list)]

                if values.varargs and not values.defaults and len(a) > len(args_values) + 1:
                    args_values += a[len(args_values) + 1 :]

                routine = func(obj, *args_values, **kwargs)
                return_value = (await routine) if inspect.isawaitable(routine) else routine

            response = resolve_response_sync(
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

    @classmethod
    async def websocket_handler(cls, obj: Any, context: Dict, func: Any, url: str) -> Any:
        response_logger = logging.getLogger("tomodachi.http.websocket")

        pattern = r"^{}$".format(re.sub(r"\$$", "", re.sub(r"^\^?(.*)$", r"\1", url)))
        compiled_pattern = re.compile(pattern)

        access_log = cls.options(context).http.access_log

        async def _pre_handler_func(_: Any, request: web.Request) -> None:
            request._cache["is_websocket"] = True
            request._cache["websocket_uuid"] = str(uuid.uuid4())

            logging.getLogger("tomodachi.http.handler").bind(handler=func.__name__, type="tomodachi.websocket")

        values = inspect.getfullargspec(func)
        original_kwargs = (
            {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults) :])}
            if values.defaults
            else {}
        )
        args_list = values.args[1 : len(values.args) - len(values.defaults or ())]
        args_set = (set(values.args[1:]) | set(values.kwonlyargs)) - set(["self"])

        @functools.wraps(func)
        async def _func(obj: Any, request: web.Request, *_a: Any, **kw: Any) -> None:
            websocket = web.WebSocketResponse()

            request_ip = RequestHandler.get_request_ip(request, context)
            try:
                await websocket.prepare(request)
            except Exception:
                try:
                    await websocket.close()
                except Exception:
                    pass

                if access_log:
                    response_logger.info(
                        websocket_state="cancelled",
                        remote_ip=request_ip,
                        auth_user=getattr(request._cache.get("auth") or {}, "login", None) or Ellipsis,
                        request_path=request.path,
                        request_query_string=request.query_string or Ellipsis,
                        websocket_id=request._cache.get("websocket_uuid", ""),
                        user_agent=request.headers.get("User-Agent", ""),
                    )

                return

            context["_http_open_websockets"] = context.get("_http_open_websockets", [])
            context["_http_open_websockets"].append(websocket)

            if access_log:
                response_logger.info(
                    websocket_state="open",
                    remote_ip=request_ip,
                    auth_user=getattr(request._cache.get("auth") or {}, "login", None) or Ellipsis,
                    request_path=request.path,
                    request_query_string=request.query_string or Ellipsis,
                    websocket_id=request._cache.get("websocket_uuid", ""),
                    user_agent=request.headers.get("User-Agent", ""),
                )

            kwargs = dict(original_kwargs)
            arg_matches: Dict[str, Any] = {}

            if "(" in pattern:
                result = compiled_pattern.match(request.path)
                if result:
                    for k, v in result.groupdict().items():
                        if k in args_set:
                            kwargs[k] = v
                            if k in values.args:
                                arg_matches[k] = v

            if "request" in args_set:
                kwargs["request"] = request
                if "request" in values.args:
                    arg_matches["request"] = request

            if "websocket" in args_set:
                kwargs["websocket"] = websocket
                if "websocket" in values.args:
                    arg_matches["websocket"] = websocket

            try:
                kw_values = {k: v for k, v in {**kwargs, **kw}.items() if values.varkw or k in args_set}
                a = [arg_matches[k] if k in arg_matches else (websocket, request)[i] for i, k in enumerate(args_list)]
                args_values = [kw_values.pop(key) if key in kw_values else a[i] for i, key in enumerate(args_list)]

                if values.varargs and not values.defaults and len(a) > len(args_values) + 1:
                    args_values += a[len(args_values) + 1 :]

                routine = func(obj, *args_values, **kw_values)
                callback_functions: Optional[Union[Tuple[Callable, Callable], Tuple[Callable], Callable]] = (
                    (await routine) if inspect.isawaitable(routine) else routine
                )
            except Exception as e:
                limit_exception_traceback(e, ("tomodachi.transport.http", "tomodachi.helpers.middleware"))
                logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))
                try:
                    await websocket.close()
                except Exception:
                    pass

                try:
                    context["_http_open_websockets"].remove(websocket)
                except Exception:
                    pass

                if access_log:
                    response_logger.info(
                        websocket_state="error",
                        remote_ip=request_ip,
                        auth_user=getattr(request._cache.get("auth") or {}, "login", None) or Ellipsis,
                        request_path=request.path,
                        request_query_string=request.query_string or Ellipsis,
                        websocket_id=request._cache.get("websocket_uuid", ""),
                        user_agent=request.headers.get("User-Agent", ""),
                    )

                return

            _receive_func = None
            _close_func = None

            if callback_functions and isinstance(callback_functions, tuple):
                if len(callback_functions) == 2:
                    _receive_func, _close_func = callback_functions
                elif len(callback_functions) == 1:
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
                                limit_exception_traceback(e, ("tomodachi.transport.http",))
                                logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))
                    elif message.type == WSMsgType.ERROR:
                        if not context.get("log_level") or context.get("log_level") in ["DEBUG"]:
                            ws_exception = websocket.exception()
                            if isinstance(ws_exception, (EofStream, RuntimeError)):
                                pass
                            elif isinstance(ws_exception, Exception):
                                limit_exception_traceback(ws_exception, ("tomodachi.transport.http",))
                                logging.getLogger("exception").exception(
                                    "uncaught exception: {}".format(str(ws_exception)), exception=ws_exception
                                )
                            else:
                                response_logger.warning("websocket exception", websocket_exception=ws_exception)
                    elif message.type == WSMsgType.CLOSED:
                        break  # noqa
            except Exception:
                pass
            finally:
                if _close_func:
                    try:
                        await _close_func()
                    except Exception as e:
                        limit_exception_traceback(e, ("tomodachi.transport.http",))
                        logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))
                try:
                    await websocket.close()
                except Exception:
                    pass

                try:
                    context["_http_open_websockets"].remove(websocket)
                except Exception:
                    pass

        return await cls.request_handler(obj, context, _func, "GET", url, pre_handler_func=_pre_handler_func)

    @staticmethod
    async def start_server(obj: Any, context: Dict) -> Optional[Callable]:
        if context.get("_http_server_started"):
            return None
        context["_http_server_started"] = True

        logger = logging.getLogger("tomodachi.http")
        logging.bind_logger(logger)

        http_options: Options.HTTP = HttpTransport.options(context).http

        server_header = http_options.server_header or ""
        access_log = http_options.access_log or False
        real_ip_header = http_options.real_ip_header or ""
        real_ip_from = (
            [http_options.real_ip_from]
            if http_options.real_ip_from and isinstance(http_options.real_ip_from, str)
            else http_options.real_ip_from or []
        )

        logger_handler = None
        if isinstance(access_log, str):
            from logging.handlers import WatchedFileHandler  # noqa  # isort:skip

            try:
                wfh = WatchedFileHandler(filename=access_log)
            except FileNotFoundError as e:
                logger.warning('Unable to use file for access log - invalid path ("{}")'.format(access_log))
                raise HttpException(str(e)) from e
            except PermissionError as e:
                logger.warning('Unable to use file for access log - invalid permissions ("{}")'.format(access_log))
                raise HttpException(str(e)) from e
            wfh.setLevel(logging.DEBUG)
            wfh.setFormatter(logging.JSONFormatter)
            logger_handler = wfh
            logger.info("logging requests to file", file_path=access_log)
            logging.getLogger("tomodachi.http.response").addHandler(logger_handler)

        async def _start_server() -> None:
            logger = logging.getLogger("tomodachi.http")
            logging.bind_logger(logger)
            response_logger = logging.getLogger("tomodachi.http.response")

            loop = asyncio.get_event_loop()

            logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

            async def request_handler_func(
                request: web.Request, handler: Callable, request_start_time: int = 0
            ) -> Union[web.Response, web.FileResponse]:
                response: Optional[Union[web.Response, web.FileResponse]] = None
                request_ip = RequestHandler.get_request_ip(request, context)

                # try to read body if it exists and can be read
                premature_eof = False
                if request.body_exists and request.can_read_body and (request.content_length or request.content):
                    try:
                        if (
                            request._read_bytes is None
                            and request.content
                            and request.content.is_eof()
                            and getattr(request.content, "_size", 0) > 0
                            and request.content.exception()
                        ):
                            request._read_bytes = request.content._read_nowait(-1)
                        else:
                            await request.read()
                    except web.HTTPException as exc:
                        # internal aiohttp exception raised (for example if entity too large)
                        response = exc
                    except Exception:
                        # failed to read body (for example if connection is closed before the entire body was sent)
                        premature_eof = True

                if request.headers.get("Authorization"):
                    try:
                        request._cache["auth"] = BasicAuth.decode(request.headers.get("Authorization", ""))
                    except ValueError:
                        pass

                if not request_ip or premature_eof:
                    # ignore request for broken transport before request handling and before entire body was sent
                    response = web.Response(status=499, headers={hdrs.SERVER: server_header})
                    response._eof_sent = True
                    response.force_close()

                    if access_log:
                        status_code = response.status if response is not None else 500
                        ignore_logging = getattr(handler, "ignore_logging", False)
                        if ignore_logging is True:
                            pass
                        elif isinstance(ignore_logging, (list, tuple)) and status_code in ignore_logging:
                            pass

                        request_version = (
                            (request.version.major, request.version.minor)
                            if isinstance(request.version, HttpVersion)
                            else (1, 0)
                        )
                        version_string = None
                        if isinstance(request.version, HttpVersion):
                            version_string = "HTTP/{}.{}".format(request_version[0], request_version[1])

                        msg = (
                            "ignored http request - connection closed before body was sent"
                            if premature_eof
                            else "ignored http request"
                        )
                        response_logger.info(
                            msg,
                            status_code=499,
                            remote_ip=request_ip or "",
                            auth_user=getattr(request._cache.get("auth") or {}, "login", None) or Ellipsis,
                            request_method=request.method,
                            request_path=request.path,
                            request_query_string=request.query_string or Ellipsis,
                            http_version=version_string,
                            response_content_length=(
                                response.content_length
                                if response is not None and response.content_length is not None
                                else Ellipsis
                            ),
                            request_content_length=(
                                request.content_length
                                if request.content_length
                                else (
                                    len(request._read_bytes)
                                    if not premature_eof
                                    and request._read_bytes is not None
                                    and len(request._read_bytes)
                                    else Ellipsis
                                )
                            ),
                            request_content_read_length=(
                                len(request._read_bytes)
                                if request._read_bytes is not None and len(request._read_bytes)
                                else ((request.content and getattr(request.content, "total_bytes", None)) or Ellipsis)
                            ),
                            user_agent=request.headers.get("User-Agent", ""),
                        )

                    return response

                handler_start_time: int = 0
                handler_stop_time: int = 0

                caught_exceptions: List[Exception] = []

                try:
                    if not response:
                        handler_start_time = time.perf_counter_ns() if access_log else 0
                        response = await handler(request)
                        handler_stop_time = time.perf_counter_ns() if access_log else 0
                except web.HTTPException as e:
                    handler_stop_time = time.perf_counter_ns() if access_log else 0
                    error_handler = context.get("_http_error_handler", {}).get(e.status, None)
                    if error_handler:
                        try:
                            response = await error_handler(request)
                        except Exception as error_handler_exception:
                            limit_exception_traceback(
                                error_handler_exception, ("tomodachi.transport.http", "tomodachi.helpers.middleware")
                            )
                            logging.getLogger("exception").exception(
                                "uncaught exception: {}".format(str(error_handler_exception))
                            )
                            caught_exceptions.append(error_handler_exception)
                            error_handler = context.get("_http_error_handler", {}).get(500, None)
                            if error_handler:
                                try:
                                    response = await error_handler(request)
                                except Exception as fallback_error_handler_exception:
                                    limit_exception_traceback(
                                        fallback_error_handler_exception,
                                        ("tomodachi.transport.http", "tomodachi.helpers.middleware"),
                                    )
                                    logging.getLogger("exception").exception(
                                        "uncaught exception: {}".format(str(fallback_error_handler_exception))
                                    )
                                    caught_exceptions.append(fallback_error_handler_exception)
                                    response = web.HTTPInternalServerError()
                                    response.body = b""
                            else:
                                response = web.HTTPInternalServerError()
                                response.body = b""
                    else:
                        response = e
                        response.body = str(e).encode("utf-8")
                except Exception as e:
                    handler_stop_time = time.perf_counter_ns() if access_log else 0
                    limit_exception_traceback(e, ("tomodachi.transport.http", "tomodachi.helpers.middleware"))
                    logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))
                    caught_exceptions.append(e)
                    error_handler = context.get("_http_error_handler", {}).get(500, None)
                    if error_handler:
                        try:
                            response = await error_handler(request)
                        except Exception as fallback_error_handler_exception:
                            limit_exception_traceback(
                                fallback_error_handler_exception,
                                ("tomodachi.transport.http", "tomodachi.helpers.middleware"),
                            )
                            logging.getLogger("exception").exception(
                                "uncaught exception: {}".format(str(fallback_error_handler_exception))
                            )
                            caught_exceptions.append(fallback_error_handler_exception)
                            response = web.HTTPInternalServerError()
                            response.body = b""

                    else:
                        response = web.HTTPInternalServerError()
                        response.body = b""
                finally:
                    replaced_status_code = None
                    replaced_response_content_length = None
                    if not request.transport:
                        replaced_status_code = response.status if response is not None else 500
                        replaced_response_content_length = (
                            response.content_length
                            if response is not None and response.content_length is not None
                            else None
                        )

                        response = web.Response(status=499, headers={})
                        response._eof_sent = True
                        setattr(response, "_replaced_status_code", replaced_status_code)
                        if replaced_response_content_length is not None:
                            setattr(response, "_replaced_response_content_length", replaced_response_content_length)

                    request_version = (
                        (request.version.major, request.version.minor)
                        if isinstance(request.version, HttpVersion)
                        else (1, 0)
                    )

                    if access_log:
                        total_request_time = ((time.perf_counter_ns() - request_start_time) / 1000000.0) / 1000.0
                        handler_elapsed_time = ((handler_stop_time - handler_start_time) / 1000000.0) / 1000.0

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
                                response_logger.info(
                                    status_code=status_code,
                                    replaced_status_code=replaced_status_code or Ellipsis,
                                    remote_ip=request_ip,
                                    auth_user=getattr(request._cache.get("auth") or {}, "login", None) or Ellipsis,
                                    request_method=request.method,
                                    request_path=request.path,
                                    request_query_string=request.query_string or Ellipsis,
                                    http_version=version_string,
                                    response_content_length=(
                                        response.content_length
                                        if response is not None and response.content_length is not None
                                        else Ellipsis
                                    ),
                                    replaced_response_content_length=replaced_response_content_length or Ellipsis,
                                    request_content_length=(
                                        request.content_length
                                        if request.content_length
                                        else (
                                            len(request._read_bytes)
                                            if request._read_bytes is not None and len(request._read_bytes)
                                            else Ellipsis
                                        )
                                    ),
                                    request_content_read_length=(
                                        len(request._read_bytes)
                                        if request._read_bytes is not None and len(request._read_bytes)
                                        else (
                                            (request.content and getattr(request.content, "total_bytes", None))
                                            or Ellipsis
                                        )
                                    ),
                                    user_agent=request.headers.get("User-Agent", ""),
                                    handler_elapsed_time=(
                                        "{0:.5f}s".format(round(handler_elapsed_time, 5))
                                        if handler_start_time and handler_stop_time
                                        else Ellipsis
                                    ),
                                    request_time="{0:.5f}s".format(round(total_request_time, 5)),
                                )
                        else:
                            response_logger.info(
                                websocket_state="closed",
                                remote_ip=request_ip,
                                auth_user=getattr(request._cache.get("auth") or {}, "login", None) or Ellipsis,
                                request_path=request.path,
                                request_query_string=request.query_string or Ellipsis,
                                websocket_id=request._cache.get("websocket_uuid", ""),
                                user_agent=request.headers.get("User-Agent", ""),
                                total_request_time="{0:.5f}s".format(round(total_request_time, 5)),
                            )

                    if response is not None:
                        response.headers[hdrs.SERVER] = server_header

                        if request_version in ((1, 0), (1, 1)) and not request._cache.get("is_websocket"):
                            use_keepalive = False
                            if context["_http_tcp_keepalive"] and request.keep_alive and request.protocol:
                                use_keepalive = True
                                if any(
                                    [
                                        # keep-alive timeout not set or is non-positive
                                        (
                                            not context["_http_keepalive_timeout"]
                                            or context["_http_keepalive_timeout"] <= 0
                                        ),
                                        # keep-alive request count has passed configured max for this connection
                                        (
                                            context["_http_max_keepalive_requests"]
                                            and request.protocol._request_count
                                            >= context["_http_max_keepalive_requests"]
                                        ),
                                        # keep-alive time has passed configured max for this connection
                                        (
                                            context["_http_max_keepalive_time"]
                                            and time.time()
                                            > getattr(request.protocol, "_connection_start_time", 0)
                                            + context["_http_max_keepalive_time"]
                                        ),
                                    ]
                                ):
                                    use_keepalive = False

                            if use_keepalive:
                                response.headers[hdrs.CONNECTION] = "keep-alive"
                                response.headers[hdrs.KEEP_ALIVE] = "timeout={}{}".format(
                                    request.protocol._keepalive_timeout,
                                    (
                                        ", max={}".format(context["_http_max_keepalive_requests"])
                                        if context["_http_max_keepalive_requests"]
                                        else ""
                                    ),
                                )
                            else:
                                response.headers[hdrs.CONNECTION] = "close"
                                response.force_close()

                        if not context["_http_tcp_keepalive"] and not request._cache.get("is_websocket"):
                            response.force_close()

                    if response is None:
                        try:
                            raise Exception("invalid response value")
                        except Exception as e:
                            limit_exception_traceback(e, ("tomodachi.transport.http",))
                            logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))

                        response = web.HTTPInternalServerError()
                        response.body = b""
                        response.headers[hdrs.CONNECTION] = "close"
                        response.force_close()

                    if caught_exceptions:
                        setattr(response, "_caught_exceptions", caught_exceptions)

                    if isinstance(response, (web.HTTPException, web.HTTPInternalServerError)):
                        raise response

                    return response

            @web.middleware
            async def middleware(request: web.Request, handler: Callable) -> Union[web.Response, web.FileResponse]:
                request_start_time = time.perf_counter_ns() if access_log else 0

                increase_execution_context_value("http_current_tasks")
                increase_execution_context_value("http_total_tasks")

                task = asyncio.ensure_future(
                    request_handler_func(request, handler, request_start_time=request_start_time)
                )
                context["_http_active_requests"] = context.get("_http_active_requests", set())
                context["_http_active_requests"].add(task)
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    try:
                        await task
                        decrease_execution_context_value("http_current_tasks")
                        try:
                            context["_http_active_requests"].remove(task)
                        except KeyError:
                            pass
                        return task.result()
                    except Exception:
                        decrease_execution_context_value("http_current_tasks")
                        try:
                            context["_http_active_requests"].remove(task)
                        except KeyError:
                            pass
                        raise
                except web.HTTPException:
                    decrease_execution_context_value("http_current_tasks")
                    try:
                        context["_http_active_requests"].remove(task)
                    except KeyError:
                        pass
                    raise
                except Exception as e:
                    decrease_execution_context_value("http_current_tasks")
                    try:
                        context["_http_active_requests"].remove(task)
                    except KeyError:
                        pass
                    limit_exception_traceback(e, ("tomodachi.transport.http",))
                    logging.getLogger("exception").exception("uncaught exception: {}".format(str(e)))
                    raise
                except BaseException:
                    decrease_execution_context_value("http_current_tasks")
                    try:
                        context["_http_active_requests"].remove(task)
                    except KeyError:
                        pass
                    raise
                decrease_execution_context_value("http_current_tasks")
                try:
                    context["_http_active_requests"].remove(task)
                except KeyError:
                    pass

                return task.result()

            client_max_size_option = http_options.client_max_size
            client_max_size_option_str = str(client_max_size_option).upper()
            client_max_size = (1024**2) * 100
            try:
                if (
                    client_max_size_option
                    and isinstance(client_max_size_option, str)
                    and (client_max_size_option_str.endswith("G") or client_max_size_option_str.endswith("GB"))
                ):
                    client_max_size = int(
                        re.sub(cast(str, r"^([0-9]+)GB?$"), cast(str, r"\1"), client_max_size_option_str)
                    ) * (1024**3)
                elif (
                    client_max_size_option
                    and isinstance(client_max_size_option, str)
                    and (client_max_size_option_str.endswith("M") or client_max_size_option_str.endswith("MB"))
                ):
                    client_max_size = int(re.sub(r"^([0-9]+)MB?$", r"\1", client_max_size_option_str)) * (1024**2)
                elif (
                    client_max_size_option
                    and isinstance(client_max_size_option, str)
                    and (client_max_size_option_str.endswith("K") or client_max_size_option_str.endswith("KB"))
                ):
                    client_max_size = int(re.sub(r"^([0-9]+)KB?$", r"\1", client_max_size_option_str)) * 1024
                elif (
                    client_max_size_option
                    and isinstance(client_max_size_option, str)
                    and (client_max_size_option_str.endswith("B"))
                ):
                    client_max_size = int(re.sub(r"^([0-9]+)B?$", r"\1", client_max_size_option_str))
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
            if client_max_size > 1024**3:
                raise ValueError(
                    "Too high value for http option client_max_size: {} ({})".format(
                        str(client_max_size_option), client_max_size_option
                    )
                )

            middlewares = context.get("_aiohttp_pre_middleware", []) + [middleware]
            app: web.Application = web.Application(middlewares=middlewares, client_max_size=client_max_size)
            app._set_loop(None)
            for method, pattern, handler, route_context in context.get("_http_routes", []):
                try:
                    compiled_pattern = re.compile(pattern)
                except re.error as exc:
                    raise ValueError("Bad http route pattern '{}': {}".format(pattern, exc)) from None
                ignore_logging = route_context.get("ignore_logging", False)
                setattr(handler, "ignore_logging", ignore_logging)
                resource = DynamicResource(compiled_pattern)
                app.router.register_resource(resource)
                if method.upper() == "GET":
                    resource.add_route("HEAD", handler, expect_handler=None)
                resource.add_route(method.upper(), handler, expect_handler=None)

            context["_http_accept_new_requests"] = True

            port = http_options.port
            host = http_options.host
            if port is True:
                raise ValueError("Bad value for http option port: {}".format(str(port)))

            # Configuration settings for keep-alive could use some refactoring

            keepalive_timeout_option = http_options.keepalive_timeout or http_options.keepalive_expiry
            keepalive_timeout = 0
            if keepalive_timeout_option is None or keepalive_timeout_option is False:
                keepalive_timeout_option = 0
            if keepalive_timeout_option is True:
                raise ValueError(
                    "Bad value for http option keepalive_timeout: {}".format(str(keepalive_timeout_option))
                )
            try:
                keepalive_timeout = int(keepalive_timeout_option) if keepalive_timeout_option is not None else 0
            except Exception:
                raise ValueError(
                    "Bad value for http option keepalive_timeout: {}".format(str(keepalive_timeout_option))
                ) from None

            tcp_keepalive = False
            if keepalive_timeout > 0:
                tcp_keepalive = True
            else:
                tcp_keepalive = False
                keepalive_timeout = 0

            max_keepalive_requests_option = http_options.max_keepalive_requests
            max_keepalive_requests = None
            if max_keepalive_requests_option is None or max_keepalive_requests_option is False:
                max_keepalive_requests_option = None
            if max_keepalive_requests_option is True:
                raise ValueError(
                    "Bad value for http option max_keepalive_requests: {}".format(str(max_keepalive_requests_option))
                )
            try:
                if max_keepalive_requests_option is not None:
                    max_keepalive_requests = int(max_keepalive_requests_option)
                if max_keepalive_requests == 0:
                    max_keepalive_requests = None
            except Exception:
                raise ValueError(
                    "Bad value for http option max_keepalive_requests: {}".format(str(max_keepalive_requests_option))
                ) from None
            if not tcp_keepalive and max_keepalive_requests:
                raise ValueError(
                    "HTTP keep-alive must be enabled to use http option max_keepalive_requests - a http.keepalive_timeout option value is required"
                ) from None

            max_keepalive_time_option = http_options.max_keepalive_time
            max_keepalive_time = None
            if max_keepalive_time_option is None or max_keepalive_time_option is False:
                max_keepalive_time_option = None
            if max_keepalive_time_option is True:
                raise ValueError(
                    "Bad value for http option max_keepalive_time: {}".format(str(max_keepalive_time_option))
                )
            try:
                if max_keepalive_time_option is not None:
                    max_keepalive_time = int(max_keepalive_time_option)
                if max_keepalive_time == 0:
                    max_keepalive_time = None
            except Exception:
                raise ValueError(
                    "Bad value for http option max_keepalive_time: {}".format(str(max_keepalive_time_option))
                ) from None
            if not tcp_keepalive and max_keepalive_time:
                raise ValueError(
                    "HTTP keep-alive must be enabled to use http option max_keepalive_time - a http.keepalive_timeout option value is required"
                ) from None

            reuse_port = True if http_options.reuse_port else False
            if reuse_port and platform.system() != "Linux":
                logger.warning(
                    "The http option reuse_port (socket.SO_REUSEPORT) can only enabled on Linux platforms - current "
                    f"platform is {platform.system()} - will revert option setting to not reuse ports"
                )
                reuse_port = False

            context["_http_tcp_keepalive"] = tcp_keepalive
            context["_http_keepalive_timeout"] = keepalive_timeout
            context["_http_max_keepalive_requests"] = max_keepalive_requests
            context["_http_max_keepalive_time"] = max_keepalive_time

            set_execution_context(
                {
                    "http_enabled": True,
                    "http_current_tasks": 0,
                    "http_total_tasks": 0,
                    "aiohttp_version": aiohttp_version,
                }
            )

            try:
                app.freeze()
                web_server = Server(
                    app._handle,
                    request_factory=app._make_request,
                    server_header=server_header,
                    access_log=access_log,
                    real_ip_header=real_ip_header,
                    real_ip_from=real_ip_from,
                    keepalive_timeout=keepalive_timeout,
                    tcp_keepalive=tcp_keepalive,
                )

                if reuse_port:
                    if not port:
                        logger.warning(
                            "The http option reuse_port (socket option SO_REUSEPORT) is enabled by default on Linux - "
                            "listening on random ports with SO_REUSEPORT is dangerous - please double check your intent"
                        )
                    elif str(port) in HttpTransport.server_port_mapping.values():
                        logger.warning(
                            "The http option reuse_port (socket option SO_REUSEPORT) is enabled by default on Linux - "
                            "different service classes should not use the same port ({})".format(port)
                        )

                if port:
                    HttpTransport.server_port_mapping[web_server] = str(port)

                server_task = loop.create_server(web_server, host, port, reuse_port=reuse_port)
                server = await server_task
            except OSError as e:
                context["_http_accept_new_requests"] = False
                error_message = re.sub(".*: ", "", e.strerror)
                logger.warning(
                    "unable to bind service [http] to http://{}:{}/".format(
                        "localhost" if host in ("0.0.0.0", "127.0.0.1") else host, port
                    ),
                    host=host,
                    port=port,
                    error_message=error_message,
                )

                try:
                    raise HttpException(str(e)).with_traceback(e.__traceback__) from None
                except Exception as exc:
                    exc.__traceback__ = e.__traceback__
                    raise

            if server.sockets:
                socket_address = server.sockets[0].getsockname()
                if socket_address:
                    port = int(socket_address[1])
                    HttpTransport.server_port_mapping[web_server] = str(port)
            context["_http_port"] = port

            stop_method = getattr(obj, "_stop_service", None)

            async def stop_service(*args: Any, **kwargs: Any) -> None:
                context["_http_tcp_keepalive"] = False

                server.close()
                await server.wait_closed()

                HttpTransport.server_port_mapping.pop(web_server, None)

                shutdown_sleep = 0
                if len(web_server.connections):
                    shutdown_sleep = 1
                    await asyncio.sleep(1)

                if not tcp_keepalive:
                    context["_http_accept_new_requests"] = False

                open_websockets = context.get("_http_open_websockets", [])[:]
                if open_websockets:
                    logger.info("closing websocket connections", connection_count=len(open_websockets))
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

                termination_grace_period_seconds = 30
                try:
                    termination_grace_period_seconds = int(
                        http_options.termination_grace_period_seconds or termination_grace_period_seconds
                    )
                except Exception:
                    pass

                log_wait_message = True if termination_grace_period_seconds >= 2 else False

                if tcp_keepalive and len(web_server.connections):
                    wait_start_time = time.time()

                    while wait_start_time + max(2, termination_grace_period_seconds) > time.time():
                        active_requests = context.get("_http_active_requests", set())
                        if not active_requests and not len(web_server.connections):
                            break

                        if log_wait_message:
                            log_wait_message = False
                            if len(web_server.connections) and len(web_server.connections) != len(active_requests):
                                logger.info(
                                    "awaiting keep-alive connections", connection_count=len(web_server.connections)
                                )
                            if active_requests:
                                logger.info(
                                    "awaiting requests to complete",
                                    request_count=len(active_requests),
                                    grace_period_seconds=termination_grace_period_seconds,
                                )

                        await asyncio.sleep(0.25)

                    termination_grace_period_seconds -= int(time.time() - wait_start_time)

                context["_http_accept_new_requests"] = False

                active_requests = context.get("_http_active_requests", set())
                if active_requests:
                    if log_wait_message:
                        logger.info(
                            "awaiting requests to complete",
                            request_count=len(active_requests),
                            grace_period_seconds=termination_grace_period_seconds,
                        )

                    try:
                        await asyncio.wait_for(
                            asyncio.shield(asyncio.gather(*active_requests, return_exceptions=True)),
                            timeout=max(2, termination_grace_period_seconds),
                        )
                        await asyncio.sleep(1)
                        active_requests = context.get("_http_active_requests", set())
                    except (Exception, asyncio.TimeoutError, asyncio.CancelledError):
                        active_requests = context.get("_http_active_requests", set())
                        if active_requests:
                            logger.warning(
                                "all requests did not gracefully finish execution",
                                remaining_request_count=len(active_requests),
                            )
                    context["_http_active_requests"] = set()

                if shutdown_sleep > 0:
                    await asyncio.sleep(shutdown_sleep)

                if len(web_server.connections):
                    logger.warning(
                        "forcefully closing open tcp connections", connection_count=len(web_server.connections)
                    )
                    await app.shutdown()
                    await asyncio.sleep(1)
                else:
                    await app.shutdown()

                if logger_handler:
                    response_logger = logging.getLogger("tomodachi.http.response")
                    response_logger.removeHandler(logger_handler)
                await app.cleanup()
                if stop_method:
                    await stop_method(*args, **kwargs)

            setattr(obj, "_stop_service", stop_service)

            for method, pattern, handler, route_context in context.get("_http_routes", []):
                for registry in getattr(obj, "discovery", []):
                    if getattr(registry, "add_http_endpoint", None):
                        await registry.add_http_endpoint(obj, host, port, method, pattern)

            listen_url = "http://{}:{}/".format("localhost" if host in ("0.0.0.0", "127.0.0.1") else host, port)
            logger.info("accepting http requests", listen_url=listen_url, listen_host=host, listen_port=port)

            if logger_handler:
                response_logger = logging.getLogger("tomodachi.http.response")
                response_logger._logger.propagate = False
                response_logger.info(
                    "accepting http requests", listen_url=listen_url, listen_host=host, listen_port=port
                )
                response_logger._logger.propagate = True

        return _start_server


async def resolve_response(
    value: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response],
    request: Optional[web.Request] = None,
    context: Optional[Dict] = None,
    status_code: Optional[Union[str, int]] = None,
    default_content_type: Optional[str] = None,
    default_charset: Optional[str] = None,
) -> Union[web.Response, web.FileResponse]:
    return resolve_response_sync(
        value=value,
        request=request,
        context=context,
        status_code=status_code,
        default_content_type=default_content_type,
        default_charset=default_charset,
    )


def resolve_response_sync(
    value: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response],
    request: Optional[web.Request] = None,
    context: Optional[Dict] = None,
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
        _status: Optional[SupportsInt] = value.get("status")
        if _status and isinstance(_status, (int, str, bytes)):
            status = int(_status)
        _returned_headers = value.get("headers")
        if _returned_headers:
            returned_headers: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]] = _returned_headers
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
            value = ""  # type: ignore
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
        response = resolve_response_sync(value, request=request)
        status_code = int(response.status) if response is not None else 500
        if verify_transport and request is not None and request.transport is None:
            return 499
        else:
            return status_code


def get_http_response_status_sync(
    value: Any, request: Optional[web.Request] = None, verify_transport: bool = True
) -> Optional[int]:
    if isinstance(value, Exception) or isinstance(value, web.HTTPException):
        status_code = int(getattr(value, "status", 500)) if value is not None else 500
        return status_code

    if verify_transport and request is not None and hasattr(request, "transport") and request.transport is None:
        return 499

    if isinstance(value, Response) and value._status:
        return int(value._status)
    elif isinstance(value, (web.Response, web.FileResponse)) and value.status:
        return int(value.status)
    elif isinstance(value, dict):
        _status: Optional[SupportsInt] = value.get("status")
        if _status and isinstance(_status, (int, str, bytes)):
            return int(_status)
    elif isinstance(value, list) or isinstance(value, tuple):
        _status = value[0]
        if _status and isinstance(_status, (int, str, bytes)):
            return int(_status)
    elif value and hasattr(value, "_status") and getattr(value, "_status", None):
        return int(getattr(value, "_status"))
    elif value and hasattr(value, "status") and getattr(value, "status", None):
        return int(getattr(value, "status"))

    return int((request is not None and request._cache.get("error_status_code", 200)) or 200)


__http = HttpTransport.decorator(HttpTransport.request_handler)
__http_error = HttpTransport.decorator(HttpTransport.error_handler)
__http_static = HttpTransport.decorator(HttpTransport.static_request_handler)

__websocket = HttpTransport.decorator(HttpTransport.websocket_handler)
__ws = HttpTransport.decorator(HttpTransport.websocket_handler)


def http(
    method: Union[str, List[str], Tuple[str, ...]],
    url: str,
    *,
    ignore_logging: Union[bool, List[int], Tuple[int, ...]] = False,
    pre_handler_func: Optional[Callable] = None,
) -> Callable:
    return cast(Callable, __http(method, url, ignore_logging=ignore_logging, pre_handler_func=pre_handler_func))


def http_error(status_code: int) -> Callable:
    return cast(Callable, __http_error(status_code))


def http_static(
    path: str, base_url: str, *, ignore_logging: Union[bool, List[int], Tuple[int, ...]] = False
) -> Callable:
    return cast(Callable, __http_static(path, base_url, ignore_logging=ignore_logging))


def websocket(url: str) -> Callable:
    return cast(Callable, __websocket(url))


def ws(url: str) -> Callable:
    return cast(Callable, __ws(url))
