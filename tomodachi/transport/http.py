import re
import asyncio
import logging
import time
import ipaddress
import os
import pathlib
import inspect
import uuid
import colorama
import functools
from logging.handlers import WatchedFileHandler
from typing import Any, Dict, List, Tuple, Union, Optional, Callable, SupportsInt, Awaitable, Mapping, Iterable  # noqa
from multidict import CIMultiDict, CIMultiDictProxy
from aiohttp import web, web_server, web_protocol, web_urldispatcher, hdrs, WSMsgType
from aiohttp.web_fileresponse import FileResponse
from aiohttp.http import HttpVersion
from aiohttp.helpers import BasicAuth
from aiohttp.streams import EofStream
from tomodachi.invoker import Invoker
from tomodachi.helpers.dict import merge_dicts
from tomodachi.helpers.middleware import execute_middlewares


class HttpException(Exception):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._log_level = kwargs.get('log_level') if kwargs and kwargs.get('log_level') else 'INFO'


class RequestHandler(web_protocol.RequestHandler):  # type: ignore
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._server_header = kwargs.pop('server_header', None) if kwargs else None
        self._access_log = kwargs.pop('access_log', None) if kwargs else None
        super().__init__(*args, **kwargs)  # type: ignore

    @staticmethod
    def get_request_ip(request: Any, context: Optional[Dict] = None) -> Optional[str]:
        if request._cache.get('request_ip'):
            return str(request._cache.get('request_ip', ''))

        if request.transport:
            if not context:
                context = {}
            real_ip_header = context.get('options', {}).get('http', {}).get('real_ip_header', 'X-Forwarded-For')
            real_ip_from = context.get('options', {}).get('http', {}).get('real_ip_from', [])
            if isinstance(real_ip_from, str):
                real_ip_from = [real_ip_from]

            peername = request.transport.get_extra_info('peername')
            request_ip = None
            if peername:
                request_ip, _ = peername
            if real_ip_header and real_ip_from and request.headers.get(real_ip_header) and request_ip and len(real_ip_from):
                if any([ipaddress.ip_address(request_ip) in ipaddress.ip_network(cidr) for cidr in real_ip_from]):
                    request_ip = request.headers.get(real_ip_header).split(',')[0].strip().split(' ')[0].strip()

            request._cache['request_ip'] = request_ip
            return request_ip

        return None

    @staticmethod
    def colorize_status(text: Optional[Union[str, int]], status: Optional[Union[str, int, bool]] = False) -> str:
        if status is False:
            status = text
        status_code = str(status) if status else None
        if status_code and not logging.getLogger('transport.http').handlers:
            output_text = str(text) if text else ''
            color = None

            if status_code == '101':
                color = colorama.Fore.CYAN
            elif status_code[0] == '2':
                color = colorama.Fore.GREEN
            elif status_code[0] == '3' or status_code == '499':
                color = colorama.Fore.YELLOW
            elif status_code[0] == '4':
                color = colorama.Fore.RED
            elif status_code[0] == '5':
                color = colorama.Fore.WHITE + colorama.Back.RED

            if color:
                return '{}{}{}'.format(color, output_text, colorama.Style.RESET_ALL)
            return output_text

        return str(text) if text else ''

    def handle_error(self, request: Any, status: int = 500, exc: Any = None, message: Optional[str] = None) -> web.Response:
        """Handle errors.

        Returns HTTP response with specific status code. Logs additional
        information. It always closes current connection."""
        if self.transport is None:
            # client has been disconnected during writing.
            if self._access_log:
                request_ip = RequestHandler.get_request_ip(request, None)
                version_string = None
                if isinstance(request.version, HttpVersion):
                    version_string = 'HTTP/{}.{}'.format(request.version.major, request.version.minor)
                logging.getLogger('transport.http').info('[{}] [{}] {} {} "{} {}{}{}" - {} "{}" -'.format(
                    RequestHandler.colorize_status('http', 499),
                    RequestHandler.colorize_status(499),
                    request_ip or '',
                    '"{}"'.format(request._cache['auth'].login.replace('"', '')) if request._cache.get('auth') and getattr(request._cache.get('auth'), 'login', None) else '-',
                    request.method,
                    request.path,
                    '?{}'.format(request.query_string) if request.query_string else '',
                    ' {}'.format(version_string) if version_string else '',
                    request.content_length if request.content_length is not None else '-',
                    request.headers.get('User-Agent', '').replace('"', '')
                ))

        headers = {}
        headers[hdrs.CONTENT_TYPE] = 'text/plain; charset=utf-8'

        msg = '' if status == 500 or not message else message

        headers[hdrs.CONTENT_LENGTH] = str(len(msg))
        headers[hdrs.SERVER] = self._server_header or ''
        resp = web.Response(status=status,  # type: ignore
                            text=msg,
                            headers=headers)  # type: web.Response
        resp.force_close()  # type: ignore

        # some data already got sent, connection is broken
        if request.writer.output_size > 0 or self.transport is None:
            self.force_close()  # type: ignore
        elif self.transport is not None:
            request_ip = RequestHandler.get_request_ip(request, None)
            if not request_ip:
                peername = request.transport.get_extra_info('peername')
                if peername:
                    request_ip, _ = peername
            if self._access_log:
                logging.getLogger('transport.http').info('[{}] [{}] {} {} "INVALID" {} - "" -'.format(
                    RequestHandler.colorize_status('http', status),
                    RequestHandler.colorize_status(status),
                    request_ip or '',
                    '"{}"'.format(request._cache['auth'].login.replace('"', '')) if request._cache.get('auth') and getattr(request._cache.get('auth'), 'login', None) else '-',
                    len(msg)
                ))

        return resp


class Server(web_server.Server):  # type: ignore
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._server_header = kwargs.pop('server_header', None) if kwargs else None
        self._access_log = kwargs.pop('access_log', None) if kwargs else None
        super().__init__(*args, **kwargs)  # type: ignore

    def __call__(self) -> RequestHandler:
        return RequestHandler(
            self, loop=self._loop, server_header=self._server_header, access_log=self._access_log,
            **self._kwargs)


class DynamicResource(web_urldispatcher.DynamicResource):  # type: ignore
    def __init__(self, pattern: Any, *, name: Optional[str] = None) -> None:
        self._routes = []  # type: List
        self._name = name
        self._pattern = pattern
        self._formatter = ''


class Response(object):
    def __init__(self, *, body: Optional[Union[bytes, str]] = None, status: int = 200, reason: Optional[str] = None, headers: Optional[Union[Dict, CIMultiDict, CIMultiDictProxy]] = None, content_type: Optional[str] = None, charset: Optional[str] = None) -> None:
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

    def get_aiohttp_response(self, context: Dict, default_charset: Optional[str] = None, default_content_type: Optional[str] = None) -> web.Response:
        if self.missing_content_type:
            self.charset = default_charset
            self.content_type = default_content_type

        charset = self.charset
        if hdrs.CONTENT_TYPE in self._headers and ';' in self._headers[hdrs.CONTENT_TYPE]:
            try:
                charset = str([v for v in self._headers[hdrs.CONTENT_TYPE].split(';') if 'charset=' in v][0]).replace('charset=', '').strip()
            except IndexError:
                pass
        elif hdrs.CONTENT_TYPE in self._headers and ';' not in self._headers[hdrs.CONTENT_TYPE]:
            charset = None

        if self._body and not isinstance(self._body, bytes) and charset:
            body = self._body
            try:
                body_value = body.encode(charset.lower())
            except (ValueError, LookupError, UnicodeEncodeError) as e:
                logging.getLogger('exception').exception('Uncaught exception: {}'.format(str(e)))
                raise web.HTTPInternalServerError() from e  # type: ignore
        elif self._body:
            body_value = self._body.encode() if not isinstance(self._body, bytes) else self._body
        else:
            body_value = b''

        response = web.Response(body=body_value,  # type: ignore
                                status=self._status,
                                reason=self._reason,
                                headers=self._headers,
                                content_type=self.content_type,
                                charset=self.charset)   # type: web.Response
        return response


class HttpTransport(Invoker):
    async def request_handler(cls: Any, obj: Any, context: Dict, func: Any, method: str, url: str, ignore_logging: Union[bool, List[int], Tuple[int]] = False, pre_handler_func: Optional[Callable] = None) -> Any:
        pattern = r'^{}$'.format(re.sub(r'\$$', '', re.sub(r'^\^?(.*)$', r'\1', url)))
        compiled_pattern = re.compile(pattern)

        default_content_type = context.get('options', {}).get('http', {}).get('content_type', 'text/plain')
        default_charset = context.get('options', {}).get('http', {}).get('charset', 'utf-8')

        if default_content_type is not None and ";" in default_content_type:
            # for backwards compability
            try:
                default_charset = str([v for v in default_content_type.split(';') if 'charset=' in v][0]).replace('charset=', '').strip()
                default_content_type = str([v for v in default_content_type.split(';')][0]).strip()
            except IndexError:
                pass

        async def handler(request: web.Request) -> Union[web.Response, web.FileResponse]:
            result = compiled_pattern.match(request.path)
            values = inspect.getfullargspec(func)
            kwargs = {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults):])} if values.defaults else {}
            if result:
                for k, v in result.groupdict().items():
                    kwargs[k] = v

            @functools.wraps(func)
            async def routine_func(*a: Any, **kw: Any) -> Union[str, bytes, Dict, List, Tuple, web.Response, Response]:
                routine = func(*(obj, request, *a), **merge_dicts(kwargs, kw))
                return_value = (await routine) if isinstance(routine, Awaitable) else routine  # type: Union[str, bytes, Dict, List, Tuple, web.Response, Response]
                return return_value

            if pre_handler_func:
                await pre_handler_func(obj, request)

            return_value = await execute_middlewares(func, routine_func, context.get('http_middleware', []), *(obj, request))
            response = await resolve_response(return_value, request=request, context=context, default_content_type=default_content_type, default_charset=default_charset)
            return response

        context['_http_routes'] = context.get('_http_routes', [])
        route_context = {'ignore_logging': ignore_logging}
        if isinstance(method, list) or isinstance(method, tuple):
            for m in method:
                context['_http_routes'].append((m.upper(), pattern, handler, route_context))
        else:
            context['_http_routes'].append((method.upper(), pattern, handler, route_context))

        start_func = cls.start_server(obj, context)
        return (await start_func) if start_func else None

    async def static_request_handler(cls: Any, obj: Any, context: Dict, func: Any, path: str, base_url: str, ignore_logging: Union[bool, List[int], Tuple[int]] = False) -> Any:
        if '?P<filename>' not in base_url:
            pattern = r'^{}(?P<filename>.+?)$'.format(re.sub(r'\$$', '', re.sub(r'^\^?(.*)$', r'\1', base_url)))
        else:
            pattern = r'^{}$'.format(re.sub(r'\$$', '', re.sub(r'^\^?(.*)$', r'\1', base_url)))
        compiled_pattern = re.compile(pattern)

        if path.startswith('/'):
            path = os.path.dirname(path)
        else:
            path = '{}/{}'.format(os.path.dirname(context.get('context', {}).get('_service_file_path')), path)

        if not path.endswith('/'):
            path = '{}/'.format(path)

        async def handler(request: web.Request) -> web.Response:
            result = compiled_pattern.match(request.path)
            filename = result.groupdict()['filename'] if result else ''
            filepath = '{}{}'.format(path, filename)

            try:
                if os.path.commonprefix((os.path.realpath(filepath), os.path.realpath(path))) != os.path.realpath(path) or os.path.isdir(filepath) or not os.path.exists(filepath):
                    raise web.HTTPNotFound()  # type: ignore

                pathlib.Path(filepath).open('r')

                response = FileResponse(path=filepath,  # type: ignore
                                        chunk_size=256 * 1024)  # type: web.Response
                return response
            except PermissionError as e:
                raise web.HTTPForbidden()  # type: ignore

        route_context = {'ignore_logging': ignore_logging}
        context['_http_routes'] = context.get('_http_routes', [])
        context['_http_routes'].append(('GET', pattern, handler, route_context))

        start_func = cls.start_server(obj, context)
        return (await start_func) if start_func else None

    async def error_handler(cls: Any, obj: Any, context: Dict, func: Any, status_code: int) -> Any:
        default_content_type = context.get('options', {}).get('http', {}).get('content_type', 'text/plain')
        default_charset = context.get('options', {}).get('http', {}).get('charset', 'utf-8')

        if default_content_type is not None and ";" in default_content_type:
            # for backwards compability
            try:
                default_charset = str([v for v in default_content_type.split(';') if 'charset=' in v][0]).replace('charset=', '').strip()
                default_content_type = str([v for v in default_content_type.split(';')][0]).strip()
            except IndexError:
                pass

        async def handler(request: web.Request) -> web.Response:
            request._cache['error_status_code'] = status_code

            values = inspect.getfullargspec(func)
            kwargs = {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults):])} if values.defaults else {}

            @functools.wraps(func)
            async def routine_func(*a: Any, **kw: Any) -> Union[str, bytes, Dict, List, Tuple, web.Response, Response]:
                routine = func(*(obj, request, *a), **merge_dicts(kwargs, kw))
                return_value = (await routine) if isinstance(routine, Awaitable) else routine  # type: Union[str, bytes, Dict, List, Tuple, web.Response, Response]
                return return_value

            return_value = await execute_middlewares(func, routine_func, context.get('http_middleware', []), *(obj, request))
            response = await resolve_response(return_value, request=request, context=context, status_code=status_code, default_content_type=default_content_type, default_charset=default_charset)
            return response

        context['_http_error_handler'] = context.get('_http_error_handler', {})
        context['_http_error_handler'][int(status_code)] = handler

        start_func = cls.start_server(obj, context)
        return (await start_func) if start_func else None

    async def websocket_handler(cls: Any, obj: Any, context: Dict, func: Any, url: str) -> Any:
        pattern = r'^{}$'.format(re.sub(r'\$$', '', re.sub(r'^\^?(.*)$', r'\1', url)))
        compiled_pattern = re.compile(pattern)

        access_log = context.get('options', {}).get('http', {}).get('access_log', True)

        async def _pre_handler_func(obj: Any, request: web.Request) -> None:
            request._cache['is_websocket'] = True
            request._cache['websocket_uuid'] = str(uuid.uuid4())

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
                    logging.getLogger('transport.http').info('[{}] {} {} "CANCELLED {}{}" {} "{}" {}'.format(
                        RequestHandler.colorize_status('websocket', 101),
                        request_ip,
                        '"{}"'.format(request._cache['auth'].login.replace('"', '')) if request._cache.get('auth') and getattr(request._cache.get('auth'), 'login', None) else '-',
                        request.path,
                        '?{}'.format(request.query_string) if request.query_string else '',
                        request._cache.get('websocket_uuid', ''),
                        request.headers.get('User-Agent', '').replace('"', ''),
                        '-'
                    ))

                return

            context['_http_open_websockets'] = context.get('_http_open_websockets', [])
            context['_http_open_websockets'].append(websocket)

            if access_log:
                logging.getLogger('transport.http').info('[{}] {} {} "OPEN {}{}" {} "{}" {}'.format(
                    RequestHandler.colorize_status('websocket', 101),
                    request_ip,
                    '"{}"'.format(request._cache['auth'].login.replace('"', '')) if request._cache.get('auth') and getattr(request._cache.get('auth'), 'login', None) else '-',
                    request.path,
                    '?{}'.format(request.query_string) if request.query_string else '',
                    request._cache.get('websocket_uuid', ''),
                    request.headers.get('User-Agent', '').replace('"', ''),
                    '-'
                ))

            result = compiled_pattern.match(request.path)
            values = inspect.getfullargspec(func)
            kwargs = {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults):])} if values.defaults else {}
            if result:
                for k, v in result.groupdict().items():
                    kwargs[k] = v

            if len(values.args) - (len(values.defaults) if values.defaults else 0) >= 3:
                # If the function takes a third required argument the value will be filled with the request object
                a = a + (request,)
            if 'request' in values.args and (len(values.args) - (len(values.defaults) if values.defaults else 0) < 3 or values.args[2] != 'request'):
                kwargs['request'] = request

            try:
                routine = func(*(obj, websocket, *a), **merge_dicts(kwargs, kw))
                callback_functions = (await routine) if isinstance(routine, Awaitable) else routine  # type: Optional[Union[Tuple, Callable]]
            except Exception as e:
                logging.getLogger('exception').exception('Uncaught exception: {}'.format(str(e)))
                try:
                    await websocket.close()
                except Exception:
                    pass

                try:
                    context['_http_open_websockets'].remove(websocket)
                except Exception:
                    pass

                if access_log:
                    logging.getLogger('transport.http').info('[{}] {} {} "{} {}{}" {} "{}" {}'.format(
                        RequestHandler.colorize_status('websocket', 500),
                        request_ip,
                        '"{}"'.format(request._cache['auth'].login.replace('"', '')) if request._cache.get('auth') and getattr(request._cache.get('auth'), 'login', None) else '-',
                        RequestHandler.colorize_status('ERROR', 500),
                        request.path,
                        '?{}'.format(request.query_string) if request.query_string else '',
                        request._cache.get('websocket_uuid', ''),
                        request.headers.get('User-Agent', '').replace('"', ''),
                        '-'
                    ))

                return

            _receive_func = None
            _close_func = None

            if callback_functions and isinstance(callback_functions, tuple):
                try:
                    _receive_func, _close_func = callback_functions
                except ValueError:
                    _receive_func, = callback_functions
            elif callback_functions:
                _receive_func = callback_functions

            try:
                async for message in websocket:
                    if message.type == WSMsgType.TEXT:
                        if _receive_func:
                            try:
                                await _receive_func(message.data)
                            except Exception as e:
                                logging.getLogger('exception').exception('Uncaught exception: {}'.format(str(e)))
                    elif message.type == WSMsgType.ERROR:
                        if not context.get('log_level') or context.get('log_level') in ['DEBUG']:
                            ws_exception = websocket.exception()
                            if isinstance(ws_exception, (EofStream, RuntimeError)):
                                pass
                            elif isinstance(ws_exception, Exception):
                                logging.getLogger('exception').exception('Uncaught exception: {}'.format(str(ws_exception)))
                            else:
                                logging.getLogger('transport.http').warning('Websocket exception: "{}"'.format(ws_exception))
                    elif message.type == WSMsgType.CLOSED:
                        break  # noqa
            except Exception as e:
                pass
            finally:
                if _close_func:
                    try:
                        await _close_func()
                    except Exception as e:
                        logging.getLogger('exception').exception('Uncaught exception: {}'.format(str(e)))
                try:
                    await websocket.close()
                except Exception:
                    pass

                try:
                    context['_http_open_websockets'].remove(websocket)
                except Exception:
                    pass

        return await cls.request_handler(cls, obj, context, _func, 'GET', url, pre_handler_func=_pre_handler_func)

    async def start_server(obj: Any, context: Dict) -> Optional[Callable]:
        if context.get('_http_server_started'):
            return None
        context['_http_server_started'] = True

        server_header = context.get('options', {}).get('http', {}).get('server_header', 'tomodachi')
        access_log = context.get('options', {}).get('http', {}).get('access_log', True)

        logger_handler = None
        if isinstance(access_log, str):
            try:
                wfh = WatchedFileHandler(filename=access_log)
            except FileNotFoundError as e:
                logging.getLogger('transport.http').warning('Unable to use file for access log - invalid path ("{}")'.format(access_log))
                raise HttpException(str(e)) from e
            except PermissionError as e:
                logging.getLogger('transport.http').warning('Unable to use file for access log - invalid permissions ("{}")'.format(access_log))
                raise HttpException(str(e)) from e
            wfh.setLevel(logging.DEBUG)
            logging.getLogger('transport.http').setLevel(logging.DEBUG)
            logging.getLogger('transport.http').info('Logging to "{}"'.format(access_log))
            logger_handler = wfh
            logging.getLogger('transport.http').addHandler(logger_handler)

        async def _start_server() -> None:
            loop = asyncio.get_event_loop()

            logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

            @web.middleware
            async def middleware(request: web.Request, handler: Callable) -> web.Response:
                async def func() -> web.Response:
                    request_ip = RequestHandler.get_request_ip(request, context)
                    if request.headers.get('Authorization'):
                        try:
                            request._cache['auth'] = BasicAuth.decode(request.headers.get('Authorization'))
                        except ValueError:
                            pass

                    if access_log:
                        timer = time.time()
                    response = web.Response(status=503,  # type: ignore
                                            headers={})  # type: web.Response
                    try:
                        response = await handler(request)
                        response.headers[hdrs.SERVER] = server_header or ''
                    except web.HTTPException as e:
                        error_handler = context.get('_http_error_handler', {}).get(e.status, None)
                        if error_handler:
                            response = await error_handler(request)
                            response.headers[hdrs.SERVER] = server_header or ''
                        else:
                            response = e
                            response.headers[hdrs.SERVER] = server_header or ''
                            response.body = str(e).encode('utf-8')
                    except Exception as e:
                        error_handler = context.get('_http_error_handler', {}).get(500, None)
                        logging.getLogger('exception').exception('Uncaught exception: {}'.format(str(e)))
                        if error_handler:
                            response = await error_handler(request)
                            response.headers[hdrs.SERVER] = server_header or ''
                        else:
                            response = web.HTTPInternalServerError()  # type: ignore
                            response.headers[hdrs.SERVER] = server_header or ''
                            response.body = b''
                    finally:
                        if not request.transport:
                            response = web.Response(status=499,  # type: ignore
                                                    headers={})  # type: web.Response
                            response._eof_sent = True

                        if access_log:
                            request_time = time.time() - timer
                            version_string = None
                            if isinstance(request.version, HttpVersion):
                                version_string = 'HTTP/{}.{}'.format(request.version.major, request.version.minor)

                            if not request._cache.get('is_websocket'):
                                status_code = response.status if response is not None else 500
                                ignore_logging = getattr(handler, 'ignore_logging', False)
                                if ignore_logging is True:
                                    pass
                                elif isinstance(ignore_logging, (list, tuple)) and status_code in ignore_logging:
                                    pass
                                else:
                                    logging.getLogger('transport.http').info('[{}] [{}] {} {} "{} {}{}{}" {} {} "{}" {}'.format(
                                        RequestHandler.colorize_status('http', status_code),
                                        RequestHandler.colorize_status(status_code),
                                        request_ip,
                                        '"{}"'.format(request._cache['auth'].login.replace('"', '')) if request._cache.get('auth') and getattr(request._cache.get('auth'), 'login', None) else '-',
                                        request.method,
                                        request.path,
                                        '?{}'.format(request.query_string) if request.query_string else '',
                                        ' {}'.format(version_string) if version_string else '',
                                        response.content_length if response is not None and response.content_length is not None else '-',
                                        request.content_length if request.content_length is not None else '-',
                                        request.headers.get('User-Agent', '').replace('"', ''),
                                        '{0:.5f}s'.format(round(request_time, 5))
                                    ))
                            else:
                                logging.getLogger('transport.http').info('[{}] {} {} "CLOSE {}{}" {} "{}" {}'.format(
                                    RequestHandler.colorize_status('websocket', 101),
                                    request_ip,
                                    '"{}"'.format(request._cache['auth'].login.replace('"', '')) if request._cache.get('auth') and getattr(request._cache.get('auth'), 'login', None) else '-',
                                    request.path,
                                    '?{}'.format(request.query_string) if request.query_string else '',
                                    request._cache.get('websocket_uuid', ''),
                                    request.headers.get('User-Agent', '').replace('"', ''),
                                    '{0:.5f}s'.format(round(request_time, 5))
                                ))

                        if isinstance(response, (web.HTTPException, web.HTTPInternalServerError)):
                            raise response

                        return response

                return await asyncio.shield(func())

            app = web.Application(middlewares=[middleware],  # type: ignore
                                  client_max_size=(1024 ** 2) * 100)  # type: web.Application
            app._set_loop(None)  # type: ignore
            for method, pattern, handler, route_context in context.get('_http_routes', []):
                try:
                    compiled_pattern = re.compile(pattern)
                except re.error as exc:
                    raise ValueError(
                        "Bad pattern '{}': {}".format(pattern, exc)) from None
                ignore_logging = route_context.get('ignore_logging', False)
                setattr(handler, 'ignore_logging', ignore_logging)
                resource = DynamicResource(compiled_pattern)
                app.router.register_resource(resource)  # type: ignore
                if method.upper() == 'GET':
                    resource.add_route('HEAD', handler, expect_handler=None)  # type: ignore
                resource.add_route(method.upper(), handler, expect_handler=None)  # type: ignore

            port = context.get('options', {}).get('http', {}).get('port', 9700)
            host = context.get('options', {}).get('http', {}).get('host', '0.0.0.0')

            try:
                app.freeze()
                server_task = loop.create_server(Server(app._handle, request_factory=app._make_request, server_header=server_header or '', access_log=access_log, keepalive_timeout=0, tcp_keepalive=False), host, port)  # type: ignore
                server = await server_task  # type: ignore
            except OSError as e:
                error_message = re.sub('.*: ', '', e.strerror)
                logging.getLogger('transport.http').warning('Unable to bind service [http] to http://{}:{}/ ({})'.format('127.0.0.1' if host == '0.0.0.0' else host, port, error_message))
                raise HttpException(str(e), log_level=context.get('log_level')) from e

            port = int(server.sockets[0].getsockname()[1])
            context['_http_port'] = port

            stop_method = getattr(obj, '_stop_service', None)

            async def stop_service(*args: Any, **kwargs: Any) -> None:
                if stop_method:
                    await stop_method(*args, **kwargs)
                open_websockets = context.get('_http_open_websockets', [])[:]
                for websocket in open_websockets:
                    try:
                        await websocket.close()
                    except Exception:
                        pass
                server.close()
                await app.shutdown()
                if logger_handler:
                    logging.getLogger('transport.http').removeHandler(logger_handler)
                await app.cleanup()

            setattr(obj, '_stop_service', stop_service)

            for method, pattern, handler, route_context in context.get('_http_routes', []):
                for registry in getattr(obj, 'discovery', []):
                    if getattr(registry, 'add_http_endpoint', None):
                        await registry.add_http_endpoint(obj, host, port, method, pattern)

            logging.getLogger('transport.http').info('Listening [http] on http://{}:{}/'.format('127.0.0.1' if host == '0.0.0.0' else host, port))

        return _start_server


async def resolve_response(value: Union[str, bytes, Dict, List, Tuple, web.Response, Response], request: Optional[web.Request] = None, context: Dict = None, status_code: Optional[Union[str, int]] = None, default_content_type: Optional[str] = None, default_charset: Optional[str] = None) -> web.Response:
    if not context:
        context = {}
    if isinstance(value, Response):
        return value.get_aiohttp_response(context, default_content_type=default_content_type, default_charset=default_charset)
    if isinstance(value, web.FileResponse):
        return value

    status = int(status_code) if status_code else (request is not None and request._cache.get('error_status_code', 200)) or 200
    headers = None
    if isinstance(value, dict):
        body = value.get('body')
        _status = value.get('status')  # type: Optional[SupportsInt]
        if _status and isinstance(_status, (int, str, bytes)):
            status = int(_status)
        _returned_headers = value.get('headers')
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
            value = ''
        body = value

    return Response(body=body, status=status, headers=headers, content_type=default_content_type, charset=default_charset).get_aiohttp_response(context)


async def get_http_response_status(value: Union[str, bytes, Dict, List, Tuple, web.Response, Response, Exception], request: Optional[web.Request] = None, verify_transport: bool = True) -> Optional[int]:
    if isinstance(value, Exception) or isinstance(value, web.HTTPException):
        status_code = int(getattr(value, 'status', 500)) if value is not None else 500
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
