import os
import asyncio
import tomodachi
from typing import Tuple, Callable, Union, Any
from aiohttp import web
from tomodachi import http, http_error, http_static, websocket, HttpResponse
from tomodachi.discovery import DummyRegistry


async def middleware_function(func: Callable, service: Any, request: web.Request, *args: Any, **kwargs: Any) -> Any:
    # Functionality before function is called
    service.log('middleware before')

    return_value = await func(*args, **kwargs)

    # There's also the possibility to pass in extra arguments or keywords arguments, for example:
    # return_value = await func(*args, id='overridden', **kwargs)

    # Functinoality after function is called
    service.log('middleware after')

    return return_value


@tomodachi.service
class ExampleHttpMiddlewareService(tomodachi.Service):
    name = 'example_http_middleware_service'
    log_level = 'DEBUG'
    uuid = os.environ.get('SERVICE_UUID')

    # Adds a middleware function that is run on every HTTP call.
    # Several middlewares can be chained.
    http_middleware = [middleware_function]

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = {
        'http': {
            'port': 4711,
            'content_type': 'text/plain',
            'charset': 'utf-8',
            'access_log': True
        }
    }

    @http('GET', r'/example/?')
    async def example(self, request: web.Request, **kwargs: Any) -> str:
        await asyncio.sleep(1)
        return '友達'  # tomodachi

    @http('GET', r'/example/(?P<id>[^/]+?)/?')
    async def example_with_id(self, request: web.Request, id: str, **kwargs: Any) -> str:
        return '友達 (id: {})'.format(id)

    @http_error(status_code=404)
    async def error_404(self, request: web.Request, **kwargs: Any) -> str:
        return 'error 404'
