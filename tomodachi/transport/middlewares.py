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

from tomodachi.helpers.dict import merge_dicts
from tomodachi.helpers.execution_context import (
    decrease_execution_context_value,
    increase_execution_context_value,
    set_execution_context,
)
from tomodachi.helpers.middleware import execute_middlewares
from tomodachi.invoker import Invoker

from .handlers import RequestHandler


http_logger = logging.getLogger("transport.http")


@web.middleware
async def request_middleware(request: web.Request, handler: Callable) -> Union[web.Response, web.FileResponse]:

    context = request.app["context"]
    http_options = context.get("options", {}).get("http", {})
    access_log = context.get("options", {}).get("http", {}).get("access_log", True)
    server_header = http_options.get("server_header", "tomodachi")

    response: Union[web.Response, web.FileResponse]
    request_ip = RequestHandler.get_request_ip(request, context)

    if not request_ip:
        # Transport broken before request handling started, ignore request
        response = web.Response(status=499, headers={hdrs.SERVER: server_header or ""})
        response._eof_sent = True
        response.force_close()

        return response

    if request.headers.get("Authorization"):
        try:
            request._cache["auth"] = BasicAuth.decode(request.headers.get("Authorization", ""))
        except ValueError:
            pass

    timer = time.time() if access_log else 0
    response = web.Response(status=503, headers={})
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
            response = web.HTTPInternalServerError()
            response.body = b""
    finally:
        if not request.transport:
            response = web.Response(status=499, headers={})
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
                    http_logger.info(
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
                http_logger.info(
                    '[{}] {} {} "CLOSE {}{}" {} "{}" {}'.format(
                        RequestHandler.colorize_status("websocket", 101),
                        request_ip,
                        '"{}"'.format(request._cache["auth"].login.replace('"', ""))
                        if request._cache.get("auth") and getattr(request._cache.get("auth"), "login", None)
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
                        ", max={}".format(context["_http_max_keepalive_requests"])
                        if context["_http_max_keepalive_requests"]
                        else "",
                    )
                else:
                    response.headers[hdrs.CONNECTION] = "close"
                    response.force_close()

            if not context["_http_tcp_keepalive"] and not request._cache.get("is_websocket"):
                response.force_close()

        if isinstance(response, (web.HTTPException, web.HTTPInternalServerError)):
            raise response

        return response


# @web.middleware
# async def request_middleware(request: web.Request, handler: Callable) -> Union[web.Response, web.FileResponse]:
#     context = {}
#     increase_execution_context_value("http_current_tasks")
#     increase_execution_context_value("http_total_tasks")
#     task = asyncio.ensure_future(_handler(request, handler))
#     context["_http_active_requests"] = context.get("_http_active_requests", set())
#     context["_http_active_requests"].add(task)

#     try:
#         await asyncio.shield(task)
#     except asyncio.CancelledError:
#         try:
#             await task
#             decrease_execution_context_value("http_current_tasks")
#             try:
#                 context["_http_active_requests"].remove(task)
#             except KeyError:
#                 pass
#             return task.result()
#         except Exception:
#             decrease_execution_context_value("http_current_tasks")
#             try:
#                 context["_http_active_requests"].remove(task)
#             except KeyError:
#                 pass
#             raise
#     except Exception:
#         decrease_execution_context_value("http_current_tasks")
#         try:
#             context["_http_active_requests"].remove(task)
#         except KeyError:
#             pass
#         raise
#     except BaseException:
#         decrease_execution_context_value("http_current_tasks")
#         try:
#             context["_http_active_requests"].remove(task)
#         except KeyError:
#             pass
#         raise
#     decrease_execution_context_value("http_current_tasks")
#     try:
#         context["_http_active_requests"].remove(task)
#     except KeyError:
#         pass

#     return task.result()
