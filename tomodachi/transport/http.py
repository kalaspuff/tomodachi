import re
import asyncio
import types
import logging
import traceback
import time
from multidict import CIMultiDict, CIMultiDictProxy
from html import escape as html_escape
from aiohttp import web, web_server, web_protocol, web_urldispatcher, hdrs
from aiohttp.http import HttpVersion
from tomodachi.invoker import Invoker


class HttpException(Exception):
    def __init__(self, *args, **kwargs):
        if kwargs and kwargs.get('log_level'):
            self._log_level = kwargs.get('log_level')
        else:
            self._log_level = 'INFO'


class RequestHandler(web_protocol.RequestHandler):
    def __init__(self, *args, **kwargs):
        self._server_header = kwargs.pop('server_header', None) if kwargs else None
        self._access_log = kwargs.pop('access_log', None) if kwargs else None
        super().__init__(*args, **kwargs)

    def handle_error(self, request, status=500, exc=None, message=None):
        """Handle errors.

        Returns HTTP response with specific status code. Logs additional
        information. It always closes current connection."""
        if self.transport is None:
            # client has been disconnected during writing.
            if self._access_log is True:
                version_string = None
                if isinstance(request.version, HttpVersion):
                    version_string = 'HTTP/{}.{}'.format(request.version.major, request.version.minor)
                logging.getLogger('transport.http').info('[http] [499] {} "{} {}{}{}" - {} -'.format(
                    request.request_ip,
                    request.method,
                    request.path,
                    '?{}'.format(request.query_string) if request.query_string else '',
                    ' {}'.format(version_string) if version_string else '',
                    request.content_length if request.content_length is not None else '-',
                ))

        self.log_exception("Error handling request", exc_info=exc)

        headers = {}
        headers[hdrs.CONTENT_TYPE] = 'text/plain; charset=utf-8'

        if status == 500:
            if self.debug:
                try:
                    tb = traceback.format_exc()
                    tb = html_escape(tb)
                    msg = "<h1>500 Internal Server Error</h1>"
                    msg += '<br><h2>Traceback:</h2>\n<pre>'
                    msg += tb
                    msg += '</pre>'

                    headers[hdrs.CONTENT_TYPE] = 'text/html; charset=utf-8'
                except:  # pragma: no cover
                    pass
            else:
                msg = ''
        else:
            msg = message

        headers[hdrs.CONTENT_LENGTH] = str(len(msg))
        headers[hdrs.SERVER] = self._server_header or ''
        resp = web.Response(status=status, text=msg, headers=headers)
        resp.force_close()

        # some data already got sent, connection is broken
        if request.writer.output_size > 0 or self.transport is None:
            self.force_close()
        elif self.transport is not None:
            if self._access_log is True:
                logging.getLogger('transport.http').info('[http] [{}] {} "INVALID" {} - -'.format(
                    status,
                    request.request_ip,
                    len(msg)
                ))

        return resp


class Server(web_server.Server):
    def __init__(self, *args, **kwargs):
        self._server_header = kwargs.pop('server_header', None) if kwargs else None
        self._access_log = kwargs.pop('access_log', None) if kwargs else None
        super().__init__(*args, **kwargs)

    def __call__(self):
        return RequestHandler(
            self, loop=self._loop, server_header=self._server_header, access_log=self._access_log,
            **self._kwargs)


class DynamicResource(web_urldispatcher.DynamicResource):
    def __init__(self, pattern, formatter, *, name=None):
        super().__init__(re.compile('\\/'), '/', name=name)
        self._pattern = pattern
        self._formatter = formatter


class UrlDispatcher(web_urldispatcher.UrlDispatcher):
    def add_pattern_route(self, method, pattern, handler, *, name=None, expect_handler=None):
        try:
            compiled_pattern = re.compile(pattern)
        except re.error as exc:
            raise ValueError(
                "Bad pattern '{}': {}".format(pattern, exc)) from None
        formatter = ''
        resource = DynamicResource(compiled_pattern, formatter, name=name)
        self.register_resource(resource)
        if method == 'GET':
            resource.add_route('HEAD', handler, expect_handler=expect_handler)
        return resource.add_route(method, handler, expect_handler=expect_handler)


class Response(object):
    def __init__(self, *, body=None, status=200, reason=None, headers=None, content_type=None, charset=None):
        if headers is None:
            headers = CIMultiDict()
        elif not isinstance(headers, (CIMultiDict, CIMultiDictProxy)):
            headers = CIMultiDict(headers)

        self._body = body
        self._status = status
        self._reason = reason
        self._headers = headers
        self.content_type = content_type
        self.charset = charset

        self.missing_content_type = hdrs.CONTENT_TYPE not in headers and not content_type and not charset

    def get_aiohttp_response(self, context, default_charset=None, default_content_type=None):
        if self.missing_content_type:
            self.charset = default_charset
            self.content_type = default_content_type

        charset = self.charset
        if hdrs.CONTENT_TYPE in self._headers and ';' in self._headers[hdrs.CONTENT_TYPE]:
            try:
                charset = str([v for v in self._headers[hdrs.CONTENT_TYPE].split(';') if 'charset=' in v][0]).replace('charset=', '').strip()
            except IndexError:
                pass

        body_value = self._body

        if not isinstance(body_value, bytes) and charset:
            try:
                body_value = body_value.encode(charset.lower())
            except ValueError as e:
                if not context.get('log_level') or context.get('log_level') in ['DEBUG']:
                    traceback.print_exception(e.__class__, e, e.__traceback__)
                raise web.HTTPInternalServerError() from e
            except LookupError as e:
                if not context.get('log_level') or context.get('log_level') in ['DEBUG']:
                    traceback.print_exception(e.__class__, e, e.__traceback__)
                raise web.HTTPInternalServerError() from e

        return web.Response(body=body_value, status=self._status, reason=self._reason, headers=self._headers, content_type=self.content_type, charset=self.charset)


class HttpTransport(Invoker):
    async def request_handler(cls, obj, context, func, method, url):
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

        async def handler(request):
            result = compiled_pattern.match(request.path)
            routine = func(*(obj, request,), **(result.groupdict() if result else {}))
            if isinstance(routine, types.GeneratorType) or isinstance(routine, types.CoroutineType):
                return_value = await routine
            else:
                return_value = routine

            if isinstance(return_value, Response):
                return return_value.get_aiohttp_response(context, default_content_type=default_content_type, default_charset=default_charset)

            status = 200
            headers = None

            if isinstance(return_value, dict):
                body = return_value.get('body')
                if return_value.get('status'):
                    status = int(return_value.get('status'))
                if return_value.get('headers'):
                    headers = CIMultiDict(return_value.get('headers'))
            elif isinstance(return_value, list) or isinstance(return_value, tuple):
                status = int(return_value[0])
                body = return_value[1]
                if len(return_value) > 2:
                    headers = CIMultiDict(return_value[2])
            elif isinstance(return_value, web.Response):
                return return_value
            else:
                if return_value is None:
                    return_value = ''
                body = return_value

            return Response(body=body, status=status, headers=headers, content_type=default_content_type, charset=default_charset).get_aiohttp_response(context)

        context['_http_routes'] = context.get('_http_routes', [])
        if isinstance(method, list) or isinstance(method, tuple):
            for m in method:
                context['_http_routes'].append((m.upper(), pattern, handler))
        else:
            context['_http_routes'].append((method.upper(), pattern, handler))

        return await cls.start_server(obj, context)

    async def error_handler(cls, obj, context, func, status_code):
        default_content_type = context.get('options', {}).get('http', {}).get('content_type', 'text/plain')
        default_charset = context.get('options', {}).get('http', {}).get('charset', 'utf-8')

        if default_content_type is not None and ";" in default_content_type:
            # for backwards compability
            try:
                default_charset = str([v for v in default_content_type.split(';') if 'charset=' in v][0]).replace('charset=', '').strip()
                default_content_type = str([v for v in default_content_type.split(';')][0]).strip()
            except IndexError:
                pass

        async def handler(request):
            routine = func(*(obj, request,), **{})
            if isinstance(routine, types.GeneratorType) or isinstance(routine, types.CoroutineType):
                return_value = await routine
            else:
                return_value = routine

            if isinstance(return_value, Response):
                return return_value.get_aiohttp_response(context, default_content_type=default_content_type, default_charset=default_charset)

            status = int(status_code)
            headers = None

            if isinstance(return_value, dict):
                body = return_value.get('body')
                if return_value.get('status'):
                    status = int(return_value.get('status'))
                if return_value.get('headers'):
                    headers = CIMultiDict(return_value.get('headers'))
            elif isinstance(return_value, list) or isinstance(return_value, tuple):
                status = int(return_value[0])
                body = return_value[1]
                if len(return_value) > 2:
                    headers = CIMultiDict(return_value[2])
            elif isinstance(return_value, web.Response):
                return return_value
            else:
                if return_value is None:
                    return_value = ''
                body = return_value

            return Response(body=body, status=status, headers=headers, content_type=default_content_type, charset=default_charset).get_aiohttp_response(context)

        context['_http_error_handler'] = context.get('_http_error_handler', {})
        context['_http_error_handler'][int(status_code)] = handler

        return await cls.start_server(obj, context)

    async def start_server(obj, context):
        if context.get('_http_server_started'):
            return None
        context['_http_server_started'] = True

        server_header = context.get('options', {}).get('http', {}).get('server_header', 'tomodachi')
        access_log = context.get('options', {}).get('http', {}).get('access_log', True)

        async def _start_server():
            loop = asyncio.get_event_loop()

            logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

            async def middleware(app, handler):
                async def middleware_handler(request):
                    async def func():
                        if request.transport:
                            peername = request.transport.get_extra_info('peername')
                            request_ip = None
                            if peername:
                                request_ip, _ = peername
                            request.request_ip = request_ip

                        if access_log:
                            timer = time.time()
                        response = None
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
                        finally:
                            if not request.transport:
                                response = web.Response(status=499)
                                response._eof_sent = True

                            if access_log is True:
                                request_time = time.time() - timer
                                version_string = None
                                if isinstance(request.version, HttpVersion):
                                    version_string = 'HTTP/{}.{}'.format(request.version.major, request.version.minor)
                                logging.getLogger('transport.http').info('[http] [{}] {} "{} {}{}{}" {} {} {}'.format(
                                    response.status if response else 500,
                                    request.request_ip,
                                    request.method,
                                    request.path,
                                    '?{}'.format(request.query_string) if request.query_string else '',
                                    ' {}'.format(version_string) if version_string else '',
                                    response.content_length if response and response.content_length is not None else '-',
                                    request.content_length if request.content_length is not None else '-',
                                    '{0:.5f}s'.format(round(request_time, 5))
                                ))

                            return response

                    return await asyncio.shield(func())

                return middleware_handler

            app = web.Application(loop=loop, router=UrlDispatcher(), middlewares=[middleware], client_max_size=(1024 ** 2) * 100)
            for method, pattern, handler in context.get('_http_routes', []):
                app.router.add_pattern_route(method.upper(), pattern, handler)

            port = context.get('options', {}).get('http', {}).get('port', 9700)
            host = context.get('options', {}).get('http', {}).get('host', '0.0.0.0')

            try:
                app.freeze()
                server = await loop.create_server(Server(app._handle, request_factory=app._make_request, server_header=server_header or '', access_log=access_log, keepalive_timeout=0, tcp_keepalive=False), host, port)
            except OSError as e:
                error_message = re.sub('.*: ', '', e.strerror)
                logging.getLogger('transport.http').warning('Unable to bind service [http] to http://{}:{}/ ({})'.format('127.0.0.1' if host == '0.0.0.0' else host, port, error_message))
                raise HttpException(str(e), log_level=context.get('log_level')) from e

            port = server.sockets[0].getsockname()[1]
            context['_http_port'] = port

            try:
                stop_method = getattr(obj, '_stop_service')
            except AttributeError as e:
                stop_method = None
            async def stop_service(*args, **kwargs):
                if stop_method:
                    await stop_method(*args, **kwargs)
                server.close()
                await app.shutdown()
                await app.cleanup()

            setattr(obj, '_stop_service', stop_service)

            for method, pattern, handler in context.get('_http_routes', []):
                try:
                    for registry in obj.discovery:
                        try:
                            if getattr(registry, 'add_http_endpoint'):
                                await registry.add_http_endpoint(obj, host, port, method, pattern)
                        except AttributeError:
                            pass
                except AttributeError:
                    pass

            logging.getLogger('transport.http').info('Listening [http] on http://{}:{}/'.format('127.0.0.1' if host == '0.0.0.0' else host, port))

        return _start_server

http = HttpTransport.decorator(HttpTransport.request_handler)
http_error = HttpTransport.decorator(HttpTransport.error_handler)
