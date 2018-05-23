import os
import asyncio
import tomodachi
import uuid
from typing import Any
from aiohttp import web
from tomodachi import http, HttpResponse


@tomodachi.decorator
async def require_auth_token(instance: Any, request: web.Request) -> Any:
    post_body = await request.read() if request.body_exists else None
    if post_body.decode() != instance.allowed_token:
        return HttpResponse(body='Invalid token', status=403)


@tomodachi.service
class ExampleHttpAuthService(tomodachi.Service):
    name = 'example_http_auth_service'
    log_level = 'DEBUG'
    allowed_token = str(uuid.uuid4())
    uuid = os.environ.get('SERVICE_UUID')

    options = {
        'http': {
            'port': 4711,
            'content_type': 'text/plain',
            'charset': 'utf-8',
            'access_log': True
        }
    }

    @http('GET', r'/get-token/?')
    async def get_token(self, request: web.Request) -> str:
        return self.allowed_token

    @http('POST', r'/validate/?')
    @require_auth_token
    async def validate(self, request: web.Request) -> str:
        return 'Valid auth token!'
