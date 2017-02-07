import re
import asyncio
import types
import logging
import traceback
import time
import http.server
from html import escape as html_escape
from aiohttp import web, web_server, web_urldispatcher, hdrs, protocol
from tomodachi.invoker import Invoker


RESPONSES = http.server.BaseHTTPRequestHandler.responses


class HttpException(Exception):
    def __init__(self, *args, **kwargs):
        if kwargs and kwargs.get('log_level'):
            self._log_level = kwargs.get('log_level')
        else:
            self._log_level = 'INFO'


class RequestHandler(web_server.RequestHandler):
    def __init__(self, *args, **kwargs):
        self._server_header = kwargs.pop('server_header', None) if kwargs else None
        self._access_log = kwargs.pop('access_log', None) if kwargs else None
        super().__init__(*args, **kwargs)

    def handle_error(self, status=500, message=None,
                     payload=None, exc=None, headers=None, reason=None):
        """Handle errors.

        Returns HTTP response with specific status code. Logs additional
        information. It always closes current connection."""
        now = self._loop.time()
        try:
            if self.transport is None:
                # client has been disconnected during writing.
                if self._access_log is True:
                    logging.getLogger('transport.http').info('[http] [499] "DISCONNECT" - - -')
                return ()

            if status == 500:
                self.log_exception("Error handling request")

            try:
                if reason is None or reason == '':
                    reason, msg = RESPONSES[status]
                else:
                    msg = reason
            except KeyError:
                status = 500
                reason, msg = '???', ''

            if self.debug and exc is not None:
                try:
                    tb = traceback.format_exc()
                    tb = html_escape(tb)
                    msg += '<br><h2>Traceback:</h2>\n<pre>{}</pre>'.format(tb)
                except:
                    pass

            if status == 400:
                body = 'Your client has issued a malformed or illegal request'.encode('utf-8')
            else:
                body = 'Invalid request'.encode('utf-8')

            response = Response(self.writer, status, close=True, server_header=self._server_header)
            if len(body) != 0:
                response.add_header(hdrs.CONTENT_TYPE, 'text/plain; charset=utf-8')
            response.add_header(hdrs.CONTENT_LENGTH, str(len(body)))
            if headers is not None:
                for name, value in headers:
                    response.add_header(name, value)
            response.send_headers()

            response.write(body)
            # disable CORK, enable NODELAY if needed
            self.writer.set_tcp_nodelay(True)
            drain = response.write_eof()

            self.log_access(message, None, response, self._loop.time() - now)

            if self._access_log is True:
                logging.getLogger('transport.http').info('[http] [{}] "INVALID" {} - -'.format(
                    status,
                    len(body)
                ))

            return drain
        finally:
            self.keep_alive(False)


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
        self._reg_resource(resource)
        if method == 'GET':
            resource.add_route('HEAD', handler, expect_handler=expect_handler)
        return resource.add_route(method, handler, expect_handler=expect_handler)


class Response(protocol.Response):
    def __init__(self, *args, **kwargs):
        self._server_header = kwargs.pop('server_header', None) if kwargs else None
        super().__init__(*args, **kwargs)

    def _add_default_headers(self):
        if self._server_header is not None:
            self.headers.setdefault(hdrs.SERVER, self._server_header)

        super()._add_default_headers()

        if self._server_header is None:
            self.headers.pop(hdrs.SERVER, None)


class HttpTransport(Invoker):
    async def request_handler(cls, obj, context, func, method, url):
        pattern = r'^{}$'.format(re.sub(r'\$$', '', re.sub(r'^\^?(.*)$', r'\1', url)))
        compiled_pattern = re.compile(pattern)

        async def handler(request):
            result = compiled_pattern.match(request.path)
            routine = func(*(obj, request,), **(result.groupdict() if result else {}))
            if isinstance(routine, types.GeneratorType) or isinstance(routine, types.CoroutineType):
                return_value = await routine
            else:
                return_value = routine

            status = 200
            headers = {
                hdrs.CONTENT_TYPE: 'text/plain; charset=utf-8',
            }

            if isinstance(return_value, dict):
                body = return_value.get('body')
                if return_value.get('status'):
                    status = int(return_value.get('status'))
                if return_value.get('headers'):
                    headers = return_value.get('headers')
            elif isinstance(return_value, list) or isinstance(return_value, tuple):
                status = return_value[0]
                body = return_value[1]
                if len(return_value) > 2:
                    headers = return_value[2]
            else:
                body = return_value

            return web.Response(body=body.encode('utf-8'), status=status, headers=headers)

        context['_http_routes'] = context.get('_http_routes', [])
        context['_http_routes'].append((method.upper(), pattern, handler))

        return await cls.start_server(obj, context)

    async def error_handler(cls, obj, context, func, status_code):
        async def handler(request):
            routine = func(*(obj, request,), **{})
            if isinstance(routine, types.GeneratorType) or isinstance(routine, types.CoroutineType):
                return_value = await routine
            else:
                return_value = routine

            status = int(status_code)
            headers = {
                hdrs.CONTENT_TYPE: 'text/plain; charset=utf-8',
            }

            if isinstance(return_value, dict):
                body = return_value.get('body')
                if return_value.get('status'):
                    status = int(return_value.get('status'))
                if return_value.get('headers'):
                    headers = return_value.get('headers')
            elif isinstance(return_value, list) or isinstance(return_value, tuple):
                status = return_value[0]
                body = return_value[1]
                if len(return_value) > 2:
                    headers = return_value[2]
            else:
                body = return_value

            return web.Response(body=body.encode('utf-8'), status=status, headers=headers)

        context['_http_error_handler'] = context.get('_http_error_handler', {})
        context['_http_error_handler'][int(status_code)] = handler

        return await cls.start_server(obj, context)

    async def start_server(obj, context):
        if context.get('_http_server_started'):
            return None
        context['_http_server_started'] = True

        server_header = context.get('options', {}).get('http', {}).get('server_header', 'tomodachi')
        access_log = context.get('options', {}).get('http', {}).get('access_log')

        async def _start_server():
            loop = asyncio.get_event_loop()

            logging.getLogger('aiohttp.access').setLevel(logging.WARN)

            async def middleware(app, handler):
                async def middleware_handler(request):
                    if access_log:
                        timer = time.time()
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
                        if access_log is True:
                            request_time = time.time() - timer
                            logging.getLogger('transport.http').info('[http] [{}] "{} {}{}" {} {} {}'.format(
                                response.status,
                                request.method,
                                request.path,
                                '?{}'.format(request.query_string) if request.query_string else '',
                                response.content_length if response.content_length is not None else '-',
                                request.content_length if request.content_length is not None else '-',
                                '{0:.5f}s'.format(round(request_time, 5))
                            ))

                        return response

                return middleware_handler

            app = web.Application(loop=loop, router=UrlDispatcher(), middlewares=[middleware])
            for method, pattern, handler in context.get('_http_routes', []):
                app.router.add_pattern_route(method.upper(), pattern, handler)

            port = context.get('options', {}).get('http', {}).get('port')
            host = context.get('options', {}).get('http', {}).get('host', '0.0.0.0')

            try:
                app.freeze()
                server = await loop.create_server(Server(app._handle, server_header=server_header or '', access_log=access_log), host, port)
            except OSError as e:
                error_message = re.sub('.*: ', '', e.strerror)
                logging.getLogger('transport.http').warn('Unable to bind service [http] to http://{}:{}/ ({})'.format('127.0.0.1' if host == '0.0.0.0' else host, port, error_message))
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
