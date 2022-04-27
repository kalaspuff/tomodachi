import asyncio
import functools
import inspect
import ipaddress
import logging
import os
import pathlib
import platform
import re
import time
import uuid
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
from contextvars import ContextVar

from tomodachi.helpers.dict import merge_dicts
from tomodachi.helpers.execution_context import (
    decrease_execution_context_value,
    increase_execution_context_value,
    set_execution_context,
)
from tomodachi.helpers.middleware import execute_middlewares
from tomodachi.invoker import Invoker

from .middlewares import request_middleware
from .handlers import RequestHandler

http_logger = logging.getLogger("transport.http")


class HttpException(Exception):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._log_level = kwargs.get("log_level") if kwargs and kwargs.get("log_level") else "INFO"


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
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._server_header = kwargs.pop("server_header", None) if kwargs else None
        self._access_log = kwargs.pop("access_log", None) if kwargs else None

        super().__init__(*args, **kwargs)

    def __call__(self) -> RequestHandler:
        return RequestHandler(
            self, loop=self._loop, server_header=self._server_header, access_log=self._access_log, **self._kwargs
        )


class DynamicResource(web_urldispatcher.DynamicResource):
    def __init__(self, pattern: Any, *, name: Optional[str] = None) -> None:
        self._routes: List = []
        self._name = name
        self._pattern = pattern
        self._formatter = ""


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
                logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))
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

        values = inspect.getfullargspec(func)
        original_kwargs = (
            {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults) :])}
            if values.defaults
            else {}
        )

        middlewares = context.get("http_middleware", [])

        async def handler(request: web.Request) -> Union[web.Response, web.FileResponse]:
            kwargs = dict(original_kwargs)
            if "(" in pattern:
                result = compiled_pattern.match(request.path)
                if result:
                    for k, v in result.groupdict().items():
                        kwargs[k] = v

            @functools.wraps(func)
            async def routine_func(
                *a: Any, **kw: Any
            ) -> Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]:
                routine = func(*(obj, request, *a), **merge_dicts(kwargs, kw))
                return_value: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response] = (
                    (await routine) if inspect.isawaitable(routine) else routine
                )
                return return_value

            if not context.get("_http_accept_new_requests"):
                raise web.HTTPServiceUnavailable()

            if pre_handler_func:
                await pre_handler_func(obj, request)

            return_value: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]
            if middlewares:
                return_value = await execute_middlewares(func, routine_func, middlewares, *(obj, request))
            else:
                routine = func(obj, request, **kwargs)
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

        values = inspect.getfullargspec(func)
        kwargs = (
            {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults) :])}
            if values.defaults
            else {}
        )

        middlewares = context.get("http_middleware", [])

        async def handler(request: web.Request) -> Union[web.Response, web.FileResponse]:
            request._cache["error_status_code"] = status_code

            @functools.wraps(func)
            async def routine_func(
                *a: Any, **kw: Any
            ) -> Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]:
                routine = func(*(obj, request, *a), **merge_dicts(kwargs, kw))
                return_value: Union[str, bytes, Dict, List, Tuple, web.Response, Response] = (
                    (await routine) if inspect.isawaitable(routine) else routine
                )
                return return_value

            return_value: Union[str, bytes, Dict, List, Tuple, web.Response, web.FileResponse, Response]
            if middlewares:
                return_value = await execute_middlewares(func, routine_func, middlewares, *(obj, request))
            else:
                routine = func(obj, request, **kwargs)
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
        pattern = r"^{}$".format(re.sub(r"\$$", "", re.sub(r"^\^?(.*)$", r"\1", url)))
        compiled_pattern = re.compile(pattern)

        access_log = context.get("options", {}).get("http", {}).get("access_log", True)

        async def _pre_handler_func(_: Any, request: web.Request) -> None:
            request._cache["is_websocket"] = True
            request._cache["websocket_uuid"] = str(uuid.uuid4())

        values = inspect.getfullargspec(func)
        original_kwargs = (
            {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults) :])}
            if values.defaults
            else {}
        )

        @functools.wraps(func)
        async def _func(obj: Any, request: web.Request, *a: Any, **kw: Any) -> None:
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
                    http_logger.info(
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
                http_logger.info(
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

            kwargs = dict(original_kwargs)
            if "(" in pattern:
                result = compiled_pattern.match(request.path)
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
                callback_functions: Optional[Union[Tuple[Callable, Callable], Tuple[Callable], Callable]] = (
                    (await routine) if inspect.isawaitable(routine) else routine
                )
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
                    http_logger.info(
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
                if len(callback_functions) == 2:
                    _receive_func, _close_func = cast(Tuple[Callable, Callable], callback_functions)
                elif len(callback_functions) == 1:
                    (_receive_func,) = cast(Tuple[Callable], callback_functions)
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
                                http_logger.warning('Websocket exception: "{}"'.format(ws_exception))
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

        return await cls.request_handler(obj, context, _func, "GET", url, pre_handler_func=_pre_handler_func)

    @classmethod
    async def get_server(cls, context) -> Server:
        http_options = context.get("options", {}).get("http", {})

        client_max_size_option = (
            http_options.get("client_max_size")
            or http_options.get("max_buffer_size")
            or http_options.get("max_upload_size")
            or "100M"
        )
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

        app: web.Application = web.Application(middlewares=[request_middleware], client_max_size=client_max_size)
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

        # Configuration settings for keep-alive could use some refactoring

        keepalive_timeout_option = http_options.get("keepalive_timeout", 0) or http_options.get(
            "keepalive_expiry", 0
        )
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

        max_keepalive_requests_option = http_options.get("max_keepalive_requests", None)
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

        max_keepalive_time_option = http_options.get("max_keepalive_time", None)
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

        # Set application context
        app["context"] = context

        app.freeze()
        return app, Server(
            app._handle,
            request_factory=app._make_request,
            server_header=http_options.get("server_header", "tomodachi"),
            access_log=http_options.get("access_log", True),
            keepalive_timeout=keepalive_timeout,
            tcp_keepalive=tcp_keepalive,
        )

    @classmethod
    async def start_server(cls, obj: Any, context: Dict) -> Optional[Callable]:
        if context.get("_http_server_started"):
            return None
        context["_http_server_started"] = True

        http_options = context.get("options", {}).get("http", {})

        server_header = http_options.get("server_header", "tomodachi")
        access_log = http_options.get("access_log", True)

        logger_handler = None
        if isinstance(access_log, str):
            from logging.handlers import WatchedFileHandler  # noqa  # isort:skip

            try:
                wfh = WatchedFileHandler(filename=access_log)
            except FileNotFoundError as e:
                http_logger.warning('Unable to use file for access log - invalid path ("{}")'.format(access_log))
                raise HttpException(str(e)) from e
            except PermissionError as e:
                http_logger.warning('Unable to use file for access log - invalid permissions ("{}")'.format(access_log))
                raise HttpException(str(e)) from e
            wfh.setLevel(logging.DEBUG)
            http_logger.setLevel(logging.DEBUG)
            http_logger.info('Logging to "{}"'.format(access_log))
            logger_handler = wfh
            http_logger.addHandler(logger_handler)

        async def _start_server() -> None:
            loop = asyncio.get_event_loop()
            logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

            try:
                app, web_server = await cls.get_server(context)
                port = http_options.get("port", 9700)
                host = http_options.get("host", "0.0.0.0")
                if port is True:
                    raise ValueError("Bad value for http option port: {}".format(str(port)))

                reuse_port_default = True if platform.system() == "Linux" else False
                reuse_port = True if http_options.get("reuse_port", reuse_port_default) else False
                if reuse_port and platform.system() != "Linux":
                    http_logger.warning(
                        "The http option reuse_port (socket.SO_REUSEPORT) can only enabled on Linux platforms - current "
                        f"platform is {platform.system()} - will revert option setting to not reuse ports"
                    )
                    reuse_port = False

                if reuse_port:
                    if not port:
                        http_logger.warning(
                            "The http option reuse_port (socket option SO_REUSEPORT) is enabled by default on Linux - "
                            "listening on random ports with SO_REUSEPORT is dangerous - please double check your intent"
                        )
                    elif str(port) in HttpTransport.server_port_mapping.values():
                        http_logger.warning(
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
                http_logger.warning(
                    "Unable to bind service [http] to http://{}:{}/ ({})".format(
                        "127.0.0.1" if host == "0.0.0.0" else host, port, error_message
                    )
                )
                raise HttpException(str(e), log_level=context.get("log_level")) from e

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

                tcp_keepalive = context["_http_tcp_keepalive"]
                if not tcp_keepalive:
                    context["_http_accept_new_requests"] = False

                open_websockets = context.get("_http_open_websockets", [])[:]
                if open_websockets:
                    http_logger.info("Closing {} websocket connection(s)".format(len(open_websockets)))
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
                        http_options.get("termination_grace_period_seconds") or termination_grace_period_seconds
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
                                http_logger.info(
                                    "Waiting for {} keep-alive connection(s) to close".format(
                                        len(web_server.connections)
                                    )
                                )
                            if active_requests:
                                http_logger.info(
                                    "Waiting for {} active request(s) to complete - grace period of {} seconds".format(
                                        len(active_requests), termination_grace_period_seconds
                                    )
                                )

                        await asyncio.sleep(0.25)

                    termination_grace_period_seconds -= int(time.time() - wait_start_time)

                context["_http_accept_new_requests"] = False

                active_requests = context.get("_http_active_requests", set())
                if active_requests:
                    if log_wait_message:
                        http_logger.info(
                            "Waiting for {} active request(s) to complete - grace period of {} seconds".format(
                                len(active_requests), termination_grace_period_seconds
                            )
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
                            http_logger.warning(
                                "All requests did not gracefully finish execution - {} request(s) remaining".format(
                                    len(active_requests)
                                )
                            )
                    context["_http_active_requests"] = set()

                if shutdown_sleep > 0:
                    await asyncio.sleep(shutdown_sleep)

                if len(web_server.connections):
                    http_logger.warning(
                        "The remaining {} open TCP connections will be forcefully closed".format(
                            len(web_server.connections)
                        )
                    )
                    await app.shutdown()
                    await asyncio.sleep(1)
                else:
                    await app.shutdown()

                if logger_handler:
                    http_logger.removeHandler(logger_handler)
                await app.cleanup()
                if stop_method:
                    await stop_method(*args, **kwargs)

            setattr(obj, "_stop_service", stop_service)

            for method, pattern, handler, route_context in context.get("_http_routes", []):
                for registry in getattr(obj, "discovery", []):
                    if getattr(registry, "add_http_endpoint", None):
                        await registry.add_http_endpoint(obj, host, port, method, pattern)

            http_logger.info(
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
