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


http_logger = logging.getLogger("transport.http")


# Should be implemented as lazy load instead
class ColoramaCache:
    _is_colorama_installed: Optional[bool] = None
    _colorama: Any = None


class RequestHandler(web_protocol.RequestHandler):
    __slots__ = (
        *web_protocol.RequestHandler.__slots__,
        "_server_header",
        "_access_log",
        "_connection_start_time",
        "_keepalive",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._server_header = kwargs.pop("server_header", None) if kwargs else None
        self._access_log = kwargs.pop("access_log", None) if kwargs else None

        self._connection_start_time = time.time()

        super().__init__(*args, access_log=None, **kwargs)  # type: ignore

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
        if ColoramaCache._is_colorama_installed is None:
            try:
                import colorama  # noqa  # isort:skip

                ColoramaCache._is_colorama_installed = True
                ColoramaCache._colorama = colorama
            except Exception:
                ColoramaCache._is_colorama_installed = False

        if ColoramaCache._is_colorama_installed is False:
            return str(text) if text else ""

        if status is False:
            status = text
        status_code = str(status) if status else None
        if status_code and not http_logger.handlers:
            output_text = str(text) if text else ""
            color = None

            if status_code == "101":
                color = ColoramaCache._colorama.Fore.CYAN
            elif status_code[0] == "2":
                color = ColoramaCache._colorama.Fore.GREEN
            elif status_code[0] == "3" or status_code == "499":
                color = ColoramaCache._colorama.Fore.YELLOW
            elif status_code[0] == "4":
                color = ColoramaCache._colorama.Fore.RED
            elif status_code[0] == "5":
                color = ColoramaCache._colorama.Fore.WHITE + ColoramaCache._colorama.Back.RED

            if color:
                return "{}{}{}".format(color, output_text, ColoramaCache._colorama.Style.RESET_ALL)
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
                http_logger.info(
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

        headers: CIMultiDict = CIMultiDict({})
        headers[hdrs.CONTENT_TYPE] = "text/plain; charset=utf-8"

        msg = "" if status == 500 or not message else message

        headers[hdrs.CONTENT_LENGTH] = str(len(msg))
        headers[hdrs.SERVER] = self._server_header or ""

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
            if self._access_log:
                http_logger.info(
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
